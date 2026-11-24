"""Daily health report for the golf bot -> Telegram.

Checks every part (bot alive, queue, logs, power cuts, scheduled tasks, disk,
website, LINE-vs-web cross-check) and for every problem says WHERE it broke
and HOW to fix it. Read-only: never changes the bot, its database or the site.

  python daily_report.py            build + send to Telegram
  python daily_report.py --dry-run  print only
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from contextlib import closing
from dataclasses import dataclass

import crosscheck
import notify
import pmweb

BOT_DIR = pathlib.Path(os.environ.get(
    "PMGOLF_BOT_DIR", pathlib.Path.home() / "Desktop" / "ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"))
STATE_FILE = pathlib.Path.home() / ".pmgolf" / "report_state.json"
HEARTBEAT_MAX_AGE_MIN = 20
DISK_MIN_GB = 2.0
LOOKBACK_HOURS = 24
TASK_NAMES = ("PMGolfBot", "PMGolfBot-Watchdog", "PMGolfBot-WeeklyReboot", "PMGolfBot-Guard")
ERROR_RE = re.compile(r"\b(ERROR|CRITICAL|Traceback|Exception)\b")

OK, WARN, FAIL = "OK", "WARN", "FAIL"
ICON = {OK: "✅", WARN: "⚠️", FAIL: "❌"}

# where it broke -> how to fix (shown under every WARN/FAIL)
PLAYBOOK: dict[str, str] = {
    "bot_missing": "วางโฟลเดอร์ 'ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ' บน Desktop ของเครื่องบอท ห้ามเปลี่ยนชื่อ",
    "bot_off": "กด 01 เปิดบอท (ถ้าตั้งใจปิดไว้ ไม่ต้องทำอะไร)",
    "heartbeat": "บอทเงียบ: 1) กด 03 ดูสถานะบอท 2) ดูว่าจอล็อก/เครื่อง sleep ไหม 3) กด 02 ปิด แล้ว 01 เปิดบอท 4) ยังไม่หาย ส่งโฟลเดอร์ logs ให้ผู้ดูแล",
    "needs_human": "กด 03 ดูสถานะบอท ดูเหตุผล แก้ตามนั้น แล้วกด 04 ให้โพสต์ต่อ หรือ retry/skip ทีละรายการ",
    "failed": "บอทลองใหม่เองได้ 5 ครั้ง ถ้ายังค้าง ดู log ของรายการนั้นแล้วกด retry",
    "skipped": "รายการค้างเกิน 72 ชม.ถูกข้าม: เช็กว่าควรโพสต์ไหม ถ้าควร ใช้ 'โพสต์รายการทันที'",
    "line_reader": "อ่าน LINE ไม่ได้: เปิด LINE PC ให้ล็อกอินอยู่ ห้ามย่อหน้าต่าง กด 'ตรวจหน้าตา LINE (probe)' ถ้า LINE เพิ่งอัปเดต",
    "photo_grabber": "เซฟรูปไม่ได้: อย่าขยับเมาส์ตอนบอทเซฟรูป ปิดป๊อปอัปที่บังจอ แล้วกด 'เซฟรูปรายการใหม่ทันที'",
    "fb_poster": "โพสต์เฟสไม่ได้: กด 'เช็กหน้ากลุ่มเฟส' ถ้าหลุดล็อกอินกด 'ล็อกอินเฟสใหม่' ถ้าโดนจำกัดใช้ 'โหมดช้า'",
    "verify": "เช็กผลไม่ผ่าน: เปิด 05 รายงาน เทียบกับกลุ่มเฟส ลบโพสต์ซ้ำด้วยมือถ้ามี",
    "textfmt": "จัดข้อความไม่ได้: ดูรูปแบบข้อความโพสต์ใน LINE ว่าเปลี่ยนไปจากเดิมไหม",
    "other_error": "เปิด 07 โฟลเดอร์ log ดูบรรทัด ERROR แล้วส่งให้ผู้ดูแล",
    "power": "เครื่องดับไม่ปกติ (ไฟดับ/ค้าง): ใส่ UPS และตั้ง BIOS ให้เปิดเครื่องเองเมื่อไฟกลับ",
    "task_missing": "งานใน Task Scheduler หาย: รัน install.ps1 แบบ Run as administrator / กด 02 ติดตั้งตัวเฝ้าเครื่อง",
    "task_failed": "งานใน Task Scheduler รันไม่สำเร็จ: เปิด Task Scheduler ดู History ของงานนั้น",
    "disk": "ดิสก์ใกล้เต็ม: ลบไฟล์ในโฟลเดอร์ shots/photos เก่า หรือขยายพื้นที่",
    "web_down": "เว็บ pmgolfclub.com เข้าไม่ได้: เช็กโฮสติ้ง/โดเมน ถ้าเว็บล่มบอทจะดึงข้อมูลไม่ได้",
    "web_pending": "สินค้าบนเว็บยังไม่พร้อมขาย (0฿) ใส่ราคาในหลังบ้าน /manage/ เมื่อพร้อม",
    "cross_mismatch": "ข้อมูล LINE กับเว็บไม่ตรง: แก้ให้ตรงกันที่หลังบ้านเว็บหรือโพสต์ LINE ก่อนบอทโพสต์ลงเฟส",
    "cross_web_only": "สินค้าพร้อมขายบนเว็บแต่ไม่มีใน LINE: โพสต์ลง LINE หรือให้บอทดึงจากเว็บแทน",
    "telegram": "ส่งรายงานไม่ได้: เช็ก bot_token/chat_id ใน %USERPROFILE%\\.pmgolf\\telegram.json",
}

LOG_COMPONENTS = ("line_reader", "photo_grabber", "fb_poster", "verify", "textfmt")


@dataclass(frozen=True)
class Finding:
    area: str
    level: str
    detail: str
    fix_key: str = ""


def _ok(area: str, detail: str) -> Finding:
    return Finding(area, OK, detail)


# ---------------- checks ----------------
def check_bot_alive(bot: pathlib.Path, now: float) -> list[Finding]:
    if not bot.exists():
        return [Finding("ตัวบอท", FAIL, f"ไม่เจอโฟลเดอร์ระบบบอทที่ {bot}", "bot_missing")]
    if (bot / "run" / "disabled.flag").exists():
        return [Finding("ตัวบอท", WARN, "บอทถูกสั่งปิดอยู่ (disabled.flag)", "bot_off")]
    out: list[Finding] = []
    beat = bot / "run" / "heartbeat.json"
    if not beat.exists():
        out.append(Finding("ตัวบอท", FAIL, "ไม่มีสัญญาณชีพ heartbeat.json", "heartbeat"))
    else:
        age_min = (now - beat.stat().st_mtime) / 60
        level = OK if age_min <= HEARTBEAT_MAX_AGE_MIN else FAIL
        out.append(Finding("ตัวบอท", level, f"สัญญาณชีพล่าสุด {age_min:.0f} นาทีที่แล้ว",
                           "" if level == OK else "heartbeat"))
    return out


def check_queue(bot: pathlib.Path) -> list[Finding]:
    db = bot / "data" / "pmbot.db"
    if not db.exists():
        return [Finding("คิวโพสต์", WARN, "ไม่เจอ data\\pmbot.db", "bot_missing")] if bot.exists() else []
    counts: Counter[str] = Counter()
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=30)) as con:
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
            if "status" in cols:
                for status, n in con.execute(f'SELECT upper(status), COUNT(*) FROM "{table}" GROUP BY 1'):
                    counts[str(status)] += n
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "ว่าง"
    out = [_ok("คิวโพสต์", f"สถานะทั้งหมด: {summary}")]
    for status, key, level in (("NEEDS_HUMAN", "needs_human", FAIL), ("FAILED", "failed", WARN)):
        if counts[status]:
            out.append(Finding("คิวโพสต์", level, f"{status} ค้าง {counts[status]} รายการ", key))
    return out


def check_logs(bot: pathlib.Path, since: float) -> list[Finding]:
    logs = bot / "logs"
    if not logs.exists():
        return []
    hits: Counter[str] = Counter()
    samples: dict[str, str] = {}
    for f in logs.glob("*.log*"):
        if f.stat().st_mtime < since:
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ERROR_RE.search(line):
                continue
            comp = next((c for c in LOG_COMPONENTS if c in line), "other_error")
            hits[comp] += 1
            samples.setdefault(comp, line.strip()[:160])
    if not hits:
        return [_ok("log", f"ไม่มี ERROR ใน {LOOKBACK_HOURS} ชม.")]
    return [Finding(f"log: {c}", FAIL if n >= 5 else WARN, f"ERROR {n} ครั้ง เช่น: {samples[c]}", c)
            for c, n in hits.most_common()]


def _run(cmd: list[str]) -> str | None:
    """Command output, or None when the command could not run or failed."""
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None


def check_power() -> list[Finding]:
    ms = LOOKBACK_HOURS * 3600 * 1000
    query = f"*[System[(EventID=41 or EventID=6008) and TimeCreated[timediff(@SystemTime) <= {ms}]]]"
    out = _run(["wevtutil", "qe", "System", f"/q:{query}", "/c:10", "/f:text"])
    if out is None:
        return [Finding("ไฟ/เครื่อง", WARN, "อ่าน Event Log ไม่ได้ ไม่รู้ว่าเครื่องดับหรือไม่", "other_error")]
    n = out.count("Event[")
    if n:
        return [Finding("ไฟ/เครื่อง", FAIL, f"เครื่องดับหรือรีสตาร์ตไม่ปกติ {n} ครั้ง", "power")]
    return [_ok("ไฟ/เครื่อง", "ไม่มีเครื่องดับผิดปกติ")]


def check_tasks() -> list[Finding]:
    out: list[Finding] = []
    for name in TASK_NAMES:
        text = _run(["schtasks", "/query", "/tn", name, "/v", "/fo", "csv"])
        rows = list(csv.reader(io.StringIO(text or "")))
        if len(rows) < 2:
            out.append(Finding(f"งาน {name}", WARN, "ไม่มีใน Task Scheduler", "task_missing"))
            continue
        row = dict(zip(rows[0], rows[1]))
        result = row.get("Last Result", "0").strip()
        if result not in ("0", "267009", "267011"):  # ok / running / never run yet
            out.append(Finding(f"งาน {name}", WARN, f"รันล่าสุดผิดพลาด (code {result})", "task_failed"))
    return out or [_ok("Task Scheduler", "งานครบ รันปกติ")]


def check_disk(path: pathlib.Path) -> list[Finding]:
    target = path if path.exists() else pathlib.Path.home()
    free_gb = shutil.disk_usage(target).free / 1024 ** 3
    if free_gb < DISK_MIN_GB:
        return [Finding("ดิสก์", FAIL, f"เหลือ {free_gb:.1f} GB", "disk")]
    return [_ok("ดิสก์", f"เหลือ {free_gb:.0f} GB")]


def check_web(state: dict) -> list[Finding]:
    since = int(state.get("web_last_id", 0))
    if not since:
        return [_ok("เว็บ", "ยังไม่มีจุดเริ่ม (ตั้งด้วย --web-since <เลขสินค้า>)")]
    try:
        result = pmweb.scan_new(since)
        pending = sorted(set(state.get("web_pending", [])) | set(result.pending))
        rechecked = pmweb.recheck(pending) if pending else pmweb.ScanResult((), (), since)
    except pmweb.FetchError as exc:
        return [Finding("เว็บ", FAIL, f"เข้าเว็บไม่ได้: {exc}", "web_down")]
    ready = len(result.ready) + len(rechecked.ready)
    state["web_last_id"] = result.last_id
    state["web_pending"] = list(rechecked.pending)
    sold = len(result.sold) + len(rechecked.sold)
    out = [_ok("เว็บ", f"เว็บปกติ สินค้าใหม่พร้อมขาย {ready} รายการ ขายแล้ว {sold} รายการ (ล่าสุด #{result.last_id})")]
    if rechecked.pending:
        out.append(Finding("เว็บ", WARN, f"ยังไม่พร้อมขาย (0฿ หรือไม่มีราคา/รูป) {len(rechecked.pending)} รายการ", "web_pending"))
    return out


def check_crosscheck(bot: pathlib.Path) -> list[Finding]:
    db = bot / "data" / "pmbot.db"
    if not db.exists():
        return []
    posts = crosscheck.posts_from_bot_db(db, limit=100)
    if not posts:
        return [Finding("LINE vs เว็บ", WARN, "อ่านโพสต์ LINE จากฐานข้อมูลบอทไม่ได้ (ต้องปรับชื่อคอลัมน์)",
                        "other_error")]
    items = crosscheck.crosscheck(posts)
    items = [i for i in items if i.status != crosscheck.NOT_PRODUCT]
    bad = [i for i in items if i.is_problem]
    if not bad:
        return [_ok("LINE vs เว็บ", f"ตรงกันทั้ง {len(items)} รายการ")]
    lines = "; ".join(f"#{i.product_id} {i.problems[0]}" for i in bad[:5])
    return [Finding("LINE vs เว็บ", WARN, f"ไม่ตรง {len(bad)}/{len(items)}: {lines}", "cross_mismatch")]


# ---------------- report ----------------
def build_report(findings: list[Finding], now: dt.datetime) -> str:
    worst = FAIL if any(f.level == FAIL for f in findings) else WARN if any(
        f.level == WARN for f in findings) else OK
    headline = {OK: "ระบบปกติ ไม่ล่ม", WARN: "ทำงานได้ แต่มีจุดต้องดู", FAIL: "มีจุดล่ม ต้องแก้"}[worst]
    lines = [f"📋 รายงานบอทกอล์ฟประจำวัน {now:%d/%m/%Y %H:%M}", f"{ICON[worst]} {headline}", ""]
    problems = [f for f in findings if f.level != OK]
    if problems:
        lines.append("🔧 จุดที่ล่ม / ต้องแก้ และวิธีแก้")
        for n, f in enumerate(sorted(problems, key=lambda x: x.level != FAIL), 1):
            lines.append(f"{n}. {ICON[f.level]} [{f.area}] {f.detail}")
            if f.fix_key:
                lines.append(f"   ➜ วิธีแก้: {PLAYBOOK.get(f.fix_key, PLAYBOOK['other_error'])}")
        lines.append("")
    lines.append("📊 สถานะทุกส่วน")
    lines += [f"{ICON[f.level]} {f.area}: {f.detail}" for f in findings if f.level == OK]
    return "\n".join(lines)


def _safe(check, *args) -> list[Finding]:
    try:
        return check(*args)
    except Exception as exc:  # one broken check must not kill the whole report
        return [Finding(check.__name__, WARN, f"ตรวจไม่ได้: {exc.__class__.__name__}: {exc}", "other_error")]


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--web-since", type=int, help="set the web product id to start from")
    args = parser.parse_args(argv)

    state = load_state()
    if args.web_since:
        state["web_last_id"] = args.web_since
    now = time.time()
    since = now - LOOKBACK_HOURS * 3600
    findings = (_safe(check_bot_alive, BOT_DIR, now) + _safe(check_queue, BOT_DIR)
                + _safe(check_logs, BOT_DIR, since) + _safe(check_power) + _safe(check_tasks)
                + _safe(check_disk, BOT_DIR) + _safe(check_web, state) + _safe(check_crosscheck, BOT_DIR))
    report = build_report(findings, dt.datetime.now())
    print(report)
    if args.dry_run:
        if args.web_since:
            save_state({**load_state(), "web_last_id": args.web_since})
        return 0
    save_state(state)
    try:
        notify.send(report)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"\n❌ ส่ง Telegram ไม่ได้: {exc}\n➜ {PLAYBOOK['telegram']}", file=sys.stderr)
        return 2
    return 1 if any(f.level == FAIL for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
