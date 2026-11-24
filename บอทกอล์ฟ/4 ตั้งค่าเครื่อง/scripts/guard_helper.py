"""Guard helper for the golf bot: bot health, DB backup, Telegram alerts.

Runs with the bot's own venv python. Never writes to the bot's database:
it is opened read-only and copied with SQLite's online backup API.

Usage: python -I guard_helper.py <BOT_DIR> <command> [args]
Commands: bot | backup | hc | alert <key> [detail] | resolve <key> | log <text>
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from contextlib import closing

BACKUP_KEEP = 7
PMGOLF_KEY_FILE = pathlib.Path.home() / ".pmgolf" / "telegram.json"
DEFAULT_THROTTLE_SEC = 3600
DAILY_SEC = 86400
SILENT_MIN = 15  # the bot's own watchdog restarts it after 10 min; give it one try first
STATE_COLUMNS = ("state", "status")  # pmbot.db uses "state"
QUEUE_PROBLEMS = {"NEEDS_HUMAN": "needs_human", "FAILED": "failed"}

MESSAGES = {
    "locked": "⚠️ เครื่องบอทถูกล็อกหน้าจอ บอทอ่าน LINE และเซฟรูปไม่ได้ ต้องปลดล็อกเครื่อง",
    "rdp_disconnected": "⚠️ VPS: ปิด Remote Desktop ด้วยปุ่ม X ทำให้จอล็อก บอทอ่าน LINE ไม่ได้\n"
                        "แก้: RDP เข้าไปใหม่ แล้วออกด้วยปุ่ม 'ออกจาก RDP แบบจอไม่ล็อก'",
    "disk": "⚠️ ดิสก์เครื่องบอทใกล้เต็ม",
    "line_missing": "⚠️ ไม่เจอโปรแกรม LINE เปิดอยู่บนเครื่องบอท",
    "skipped": "⚠️ มีรายการถูกข้าม (SKIPPED) เพิ่มขึ้น อาจเพราะค้างคิวเกิน 72 ชม. ตรวจด้วย 03 ดูสถานะบอท",
    "bot_silent": "❌ บอทโพสต์เงียบ อาจค้างหรือล่ม\n"
                  "แก้: กด 03 ดูสถานะบอท เช็กว่าจอไม่ล็อก แล้วกด 02 ปิดบอท ตามด้วย 01 เปิดบอท",
    "needs_human": "❌ มีรายการรอคนแก้ (NEEDS_HUMAN)\n"
                   "แก้: กด 03 ดูสถานะบอท ดูเหตุผล แก้แล้วกด 04 ให้โพสต์ต่อ",
    "failed": "⚠️ มีรายการโพสต์ไม่สำเร็จ (FAILED) บอทจะลองใหม่เอง\nถ้ายังค้าง กด 03 ดูสถานะบอท",
    "db_unreadable": "⚠️ อ่านสถานะคิวจาก pmbot.db ไม่ได้ ตัวเฝ้าจะไม่เห็นปัญหาโพสต์",
    "no_hc": "ℹ️ ยังไม่ได้ตั้ง Healthchecks ใน config.toml ถ้าเครื่องดับหรือเน็ตหลุดจะไม่มีใครเตือน",
    "backup_fail": "❌ สำรองฐานข้อมูล pmbot.db ไม่สำเร็จ",
    "guard_error": "❌ ตัวเฝ้าเครื่องทำงานผิดพลาด",
}

RECOVERED = {
    "locked": "จอเครื่องบอทปลดล็อกแล้ว",
    "rdp_disconnected": "session ของ VPS กลับมาแล้ว",
    "disk": "พื้นที่ดิสก์กลับมาเพียงพอ",
    "line_missing": "LINE เปิดอยู่แล้ว",
    "bot_silent": "บอทโพสต์มีสัญญาณชีพแล้ว",
    "needs_human": "ไม่มีรายการรอคนแก้ (NEEDS_HUMAN) แล้ว",
    "failed": "ไม่มีรายการ FAILED ค้างแล้ว",
    "db_unreadable": "อ่านสถานะคิวจาก pmbot.db ได้แล้ว",
}

TOKEN_RE = re.compile(r"\b(\d{6,}:[A-Za-z0-9_-]{30,})\b")
CHAT_RE = re.compile(r"^\s*\w*chat\w*\s*=\s*\"?(-?\d{5,})\"?", re.IGNORECASE | re.MULTILINE)
HC_RE = re.compile(r"(https?://[^\s\"']*hc-ping[^\s\"']*)|^\s*\w*healthcheck\w*\s*=\s*\"https?://", re.IGNORECASE | re.MULTILINE)


class Guard:
    def __init__(self, bot_dir: pathlib.Path) -> None:
        self.bot = bot_dir
        self.dir = bot_dir / "guard"
        self.dir.mkdir(exist_ok=True)
        self.state_file = self.dir / "state.json"
        self.db = bot_dir / "data" / "pmbot.db"
        self.config = bot_dir / "config.toml"

    # ---------- state / log ----------
    def load_state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_state(self, state: dict) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.state_file)

    def log(self, text: str) -> None:
        line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {text}\n"
        log_file = self.dir / "guard.log"
        try:
            if log_file.exists() and log_file.stat().st_size > 1_000_000:
                log_file.replace(self.dir / "guard.old.log")
            with log_file.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    # ---------- alerts ----------
    def config_text(self) -> str:
        try:
            return self.config.read_text(encoding="utf-8")
        except OSError:
            return ""

    def telegram_target(self) -> tuple[str, str] | None:
        """Prefer %USERPROFILE%\\.pmgolf\\telegram.json (report group), else bot config.toml."""
        try:
            data = json.loads(PMGOLF_KEY_FILE.read_text(encoding="utf-8"))
            if data.get("bot_token") and data.get("chat_id"):
                return str(data["bot_token"]), str(data["chat_id"])
        except (OSError, ValueError):
            pass
        cfg = self.config_text()
        token, chat = TOKEN_RE.search(cfg), CHAT_RE.search(cfg)
        return (token.group(1), chat.group(1)) if token and chat else None

    def send_telegram(self, text: str) -> bool:
        target = self.telegram_target()
        if target is None:
            self.log("telegram: no token/chat_id (telegram.json or config.toml), alert only logged")
            return False
        url = f"https://api.telegram.org/bot{target[0]}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": target[1], "text": text}).encode()
        try:
            with urllib.request.urlopen(url, data=data, timeout=20) as resp:
                return resp.status == 200
        except OSError as exc:
            self.log(f"telegram: send failed: {exc.__class__.__name__}")
            return False

    def alert(self, key: str, detail: str = "", every: int = DEFAULT_THROTTLE_SEC) -> bool:
        """Send one alert. True only when Telegram accepted it."""
        state = self.load_state()
        last = state.get("last_alert", {})
        now = time.time()
        if now - last.get(key, 0) < every:
            self.log(f"alert {key} throttled {detail}")
            return False
        text = MESSAGES.get(key, key) + (f"\n{detail}" if detail else "")
        ok = self.send_telegram("[ตัวเฝ้าเครื่องบอทกอล์ฟ]\n" + text)
        self.log(f"alert {key} sent={ok} {detail}")
        if ok:
            opened = {**state.get("open", {}), key: True}
            self.save_state({**state, "last_alert": {**last, key: now}, "open": opened})
        return ok

    def resolve(self, key: str, quiet: bool = False) -> None:
        """Close an alert that was sent earlier; says so unless quiet."""
        state = self.load_state()
        if key not in state.get("open", {}):
            return
        if not quiet:
            text = f"[ตัวเฝ้าเครื่องบอทกอล์ฟ]\n✅ กลับมาปกติ: {RECOVERED.get(key, key)}"
            if not self.send_telegram(text):
                return  # still open, so the next run tries again
        self.log(f"resolved {key} quiet={quiet}")
        self.save_state({
            **state,
            "open": {k: v for k, v in state["open"].items() if k != key},
            # a new incident after this one must alert at once
            "last_alert": {k: v for k, v in state.get("last_alert", {}).items() if k != key},
        })

    # ---------- commands ----------
    def ro_connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True, timeout=30)

    def backup(self) -> None:
        backup_dir = self.bot / "backup"
        backup_dir.mkdir(exist_ok=True)
        dst = backup_dir / f"pmbot-{dt.date.today():%Y%m%d}.db"
        if dst.exists():
            return
        if not self.db.exists():
            self.alert("backup_fail", "ไม่เจอไฟล์ data\\pmbot.db", every=DAILY_SEC)
            return
        tmp = dst.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        try:
            # closing(): sqlite3's own context manager commits but does not close,
            # and Windows refuses to rename a file that is still open.
            with closing(self.ro_connect()) as src, closing(sqlite3.connect(tmp)) as out:
                src.backup(out)
                result = out.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise sqlite3.DatabaseError(f"integrity_check: {result}")
            tmp.replace(dst)
        except (sqlite3.Error, OSError) as exc:
            tmp.unlink(missing_ok=True)
            self.alert("backup_fail", str(exc), every=DAILY_SEC)
            return
        old = sorted(backup_dir.glob("pmbot-*.db"))[:-BACKUP_KEEP]
        for f in old:
            f.unlink(missing_ok=True)
        self.log(f"backup ok {dst.name}")

    def status_counts(self) -> dict[str, int] | None:
        """Rows per status, or None when the queue cannot be read."""
        if not self.db.exists():
            return None
        counts: dict[str, int] = {}
        found = False
        try:
            with closing(self.ro_connect()) as con:
                for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
                    column = next((c for c in STATE_COLUMNS if c in cols), None)
                    if column is None or table != "items":
                        continue
                    found = True
                    for status, n in con.execute(f'SELECT upper("{column}"), COUNT(*) FROM "{table}" GROUP BY 1'):
                        counts[str(status)] = counts.get(str(status), 0) + n
        except sqlite3.Error as exc:
            self.log(f"status_counts error: {exc!r}")
            return None
        return counts if found else None

    def announced(self, key: str, default: int | None = 0) -> int | None:
        return self.load_state().get("announced", {}).get(key, default)

    def set_announced(self, key: str, value: int) -> None:
        state = self.load_state()
        self.save_state({**state, "announced": {**state.get("announced", {}), key: value}})

    def check_silent(self) -> None:
        if (self.bot / "run" / "disabled.flag").exists():
            self.resolve("bot_silent", quiet=True)  # switched off on purpose, not recovered
            return
        beat = self.bot / "run" / "heartbeat.json"
        if not beat.exists():
            self.alert("bot_silent", "ไม่มีไฟล์ heartbeat.json")
            return
        age_min = (time.time() - beat.stat().st_mtime) / 60
        if age_min > SILENT_MIN:
            self.alert("bot_silent", f"สัญญาณชีพล่าสุด {age_min:.0f} นาทีที่แล้ว")
        else:
            self.resolve("bot_silent")

    def check_queue(self) -> None:
        counts = self.status_counts()
        if counts is None:
            self.alert("db_unreadable", every=DAILY_SEC)
            return
        self.resolve("db_unreadable")
        for status, key in QUEUE_PROBLEMS.items():
            self.check_increase(key, counts.get(status, 0))
            if not counts.get(status, 0):
                self.resolve(key)
        skipped = counts.get("SKIPPED", 0)
        if self.announced("skipped", None) is None:
            # first run: old SKIPPED items are history (older versions kept skipped_count)
            self.set_announced("skipped", self.load_state().get("skipped_count", skipped))
        self.check_increase("skipped", skipped)

    def check_increase(self, key: str, total: int) -> None:
        """Alert when the count grew. The baseline moves only after a successful send."""
        before = self.announced(key) or 0
        if total > before and not self.alert(key, f"เพิ่มขึ้น {total - before} รายการ (รวม {total})", every=0):
            return
        if total != before:
            self.set_announced(key, total)

    def bot_health(self) -> None:
        self.check_silent()
        self.check_queue()

    def healthchecks(self) -> None:
        if not HC_RE.search(self.config_text()):
            self.alert("no_hc", every=DAILY_SEC)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    guard = Guard(pathlib.Path(argv[1]))
    cmd, rest = argv[2], argv[3:]
    try:
        if cmd == "backup":
            guard.backup()
        elif cmd == "bot":
            guard.bot_health()
        elif cmd == "resolve" and rest:
            guard.resolve(rest[0])
        elif cmd == "hc":
            guard.healthchecks()
        elif cmd == "alert" and rest:
            guard.alert(rest[0], " ".join(rest[1:]))
        elif cmd == "log":
            guard.log(" ".join(rest))
        else:
            print(__doc__)
            return 2
    except Exception as exc:  # last-resort: never die silently
        guard.log(f"{cmd} error: {exc!r}")
        guard.alert("guard_error", f"{cmd}: {exc.__class__.__name__}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
