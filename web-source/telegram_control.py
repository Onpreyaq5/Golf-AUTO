"""Control the golf bot from the Telegram group: easy to stop, hard to start, impossible to post.

Runs on the bot machine and long-polls Telegram. Settings live in
%USERPROFILE%\\.pmgolf\\telegram.json, outside the repo:

  {"bot_token": "...", "chat_id": "-100...", "admins": [123456], "allow_live_on": false}

Only people in "admins" may command, only in that one group. Find your id with
/whoami, then run:  python telegram_control.py --add-admin 123456

There is deliberately no command that posts, retries, requeues or changes mode.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import pathlib
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

import daily_report
import notify

POLL_SEC = 50
CONFIRM_SEC = 60
MAX_AGE_SEC = 120           # a command sent while we were offline is dropped, not replayed
COMMAND_TIMEOUT_SEC = 90
MAX_REPLY_CHARS = 1500
START_CODE = ("from pmbot import config, procs; config.DISABLED_FLAG.unlink(missing_ok=True); "
              "print('already running' if procs.supervisor_alive() else procs.start_supervisor())")
STATE_DIR = pathlib.Path.home() / ".pmgolf"
HELP = """คำสั่งบอทกอล์ฟ
/status ดูสถานะและคิว
/report ส่งรายงานสุขภาพระบบ
/off ปิดบอททันที
/on เปิดบอท (ต้องยืนยันรหัส)
/slow โพสต์ช้า  /normal จังหวะปกติ
/skip <เลขรายการ> ข้ามรายการ (ต้องยืนยันรหัส)
/whoami ดูเลขประจำตัวของคุณ
สั่งโพสต์ ลองใหม่ หรือเปลี่ยนโหมดผ่าน Telegram ไม่ได้ ต้องทำที่เครื่องบอท"""

log = logging.getLogger("control")


@dataclass(frozen=True)
class Settings:
    token: str
    chat_id: int
    admins: frozenset[int]
    allow_live_on: bool


@dataclass(frozen=True)
class Request:
    user_id: int
    chat_id: int
    command: str
    args: tuple[str, ...]
    date: float


@dataclass(frozen=True)
class Pending:
    code: str
    action: str
    item: int
    expires: float


def _admin_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    text = str(value)
    return int(text) if re.fullmatch(r"[1-9]\d{2,18}", text) else None


def load_settings(path: pathlib.Path) -> Settings:
    data = json.loads(path.read_text(encoding="utf-8"))
    admins = (_admin_id(a) for a in data.get("admins", []))
    return Settings(str(data["bot_token"]), int(data["chat_id"]),
                    frozenset(a for a in admins if a is not None), data.get("allow_live_on") is True)


def parse_update(update: dict, bot_username: str) -> Request | None:
    """A fresh command typed by a real person, or None. Edits, forwards, bots and anonymous admins are ignored."""
    msg = update.get("message")
    if not isinstance(msg, dict):
        return None
    sender = msg.get("from") or {}
    if sender.get("is_bot") or any(k in msg for k in ("forward_origin", "forward_date", "sender_chat", "via_bot")):
        return None
    words = str(msg.get("text", "")).split()
    match = re.fullmatch(r"/([A-Za-z_]+)(?:@(\w+))?", words[0]) if words else None
    if not match or (match.group(2) and match.group(2).lower() != bot_username.lower()):
        return None
    try:
        return Request(int(sender["id"]), int(msg["chat"]["id"]), match.group(1).lower(),
                       tuple(words[1:]), float(msg["date"]))
    except (KeyError, TypeError, ValueError):
        return None


class BotLink:
    """The only ways this program can touch the bot. Fixed commands, never a shell."""

    def __init__(self, bot_dir: pathlib.Path) -> None:
        self.dir = bot_dir
        self.python = bot_dir / "venv" / "Scripts" / "python.exe"
        self._report: subprocess.Popen[bytes] | None = None

    def _run(self, *args: str) -> str:
        done = subprocess.run([str(self.python), *args], cwd=self.dir / "app", capture_output=True,
                              timeout=COMMAND_TIMEOUT_SEC, check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if done.returncode != 0:
            raise OSError(f"คำสั่งของบอทล้มเหลว (code {done.returncode})")
        return done.stdout.decode("utf-8", errors="replace")

    def status(self) -> str:
        return self._run("-X", "utf8", "-m", "pmbot", "status", "-n", "5")

    def off(self) -> str:
        flag = self.dir / "run" / "disabled.flag"
        flag.write_text(time.strftime("%Y-%m-%d %H:%M:%S") + " telegram", encoding="utf-8")
        return "ปิดแล้ว บอทจะทำขั้นที่ค้างให้จบแล้วหยุด"

    def on(self) -> str:
        self._run("-c", START_CODE)
        return "ส่งคำสั่งเปิดแล้ว รอสักครู่แล้วใช้ /status"

    def skip(self, item: int) -> str:
        return self._run("-m", "pmbot", "skip", str(item)).strip()

    def speed(self, mode: str) -> str:
        return self._run("-m", "pmbot", "speed", mode).strip()

    def report(self) -> str:
        if self._report is not None and self._report.poll() is None:
            return "รายงานกำลังทำอยู่ รอสักครู่"
        script = pathlib.Path(__file__).with_name("daily_report.py")
        # this program runs under pythonw (no console); the report prints, so it needs python.exe
        python = pathlib.Path(sys.executable).with_name("python.exe")
        self._report = subprocess.Popen([str(python if python.exists() else sys.executable), str(script)],
                                        cwd=script.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "กำลังทำรายงาน ใช้เวลา 2-5 นาที"


def _field(status: str, name: str) -> str:
    match = re.search(rf"\b{name}=(\S+)", status)
    return match.group(1) if match else ""


def _count(status: str, *states: str) -> int:
    return sum(int(n) for s in states for n in re.findall(rf"'{s}': (\d+)", status))


def describe(status: str) -> str:
    power = {"True": "ปิด", "False": "เปิด"}.get(_field(status, "disabled"), "ไม่ทราบ")
    return (f"โหมด: {_field(status, 'mode') or 'ไม่ทราบ'} | สวิตช์: {power}\n"
            f"สัญญาณชีพ: {_field(status, 'heartbeat_age') or '-'} | LINE: {_field(status, 'line') or '-'} "
            f"| เฟส: {_field(status, 'fb') or '-'}\n"
            f"รอรูป {_count(status, 'NEW')} | พร้อมโพสต์ {_count(status, 'QUEUED', 'FAILED')} "
            f"| รอคนแก้ {_count(status, 'NEEDS_HUMAN')} | โพสต์แล้ว {_count(status, 'POSTED')}")


class Controller:
    def __init__(self, settings: Settings, bot: BotLink, clock: Callable[[], float] = time.time) -> None:
        self.settings, self.bot, self.clock = settings, bot, clock
        self.pending: dict[int, Pending] = {}

    def handle(self, req: Request) -> str | None:
        if req.chat_id != self.settings.chat_id or abs(self.clock() - req.date) > MAX_AGE_SEC:
            return None
        if req.command == "whoami":
            return f"เลขประจำตัวของคุณ: {req.user_id}"
        if req.user_id not in self.settings.admins:
            return "ไม่มีสิทธิ์สั่งบอท ใช้ /whoami แล้วส่งเลขให้ผู้ดูแลเพิ่ม"
        log.info("user %s: /%s %s", req.user_id, req.command, " ".join(req.args)[:40])
        try:
            return self._dispatch(req)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            log.error("/%s failed: %r", req.command, exc)
            return f"ทำไม่สำเร็จ: {str(exc)[:200] or exc.__class__.__name__}"

    def _dispatch(self, req: Request) -> str:
        simple: dict[str, Callable[[], str]] = {
            "help": lambda: HELP,
            "start": lambda: HELP,
            "status": lambda: describe(self.bot.status()),
            "off": self._off,
            "slow": lambda: self.bot.speed("slow"),
            "normal": lambda: self.bot.speed("normal"),
            "report": self.bot.report,
            "on": lambda: self._ask_on(req.user_id),
        }
        if req.command in simple:
            return simple[req.command]()
        if req.command == "skip":
            return self._ask_skip(req)
        if req.command == "confirm":
            return self._confirm(req)
        return "ไม่รู้จักคำสั่งนี้\n" + HELP

    def _off(self) -> str:
        self.pending.clear()  # nobody can finish an older /on after this
        return self.bot.off()

    # ---------- two-step commands ----------
    def _ask(self, user_id: int, action: str, item: int, text: str) -> str:
        code = f"{secrets.randbelow(90000) + 10000}"
        self.pending[user_id] = Pending(code, action, item, self.clock() + CONFIRM_SEC)
        return f"{text}\nยืนยันภายใน {CONFIRM_SEC} วินาที: /confirm {code}"

    def _why_not_on(self, status: str) -> str:
        mode = _field(status, "mode")
        if mode not in ("dry-run", "test", "live"):
            return "อ่านโหมดของบอทไม่ได้ จึงไม่เปิดให้"
        if mode == "live" and not self.settings.allow_live_on:
            return "บอทอยู่ในโหมด live (โพสต์กลุ่มจริง) เปิดผ่าน Telegram ไม่ได้ ต้องเปิดที่เครื่องบอท"
        return ""

    def _ask_on(self, user_id: int) -> str:
        status = self.bot.status()
        refused = self._why_not_on(status)
        if refused:
            return refused
        waiting = _count(status, "NEW", "QUEUED", "FAILED")
        where = {"live": "⚠️ จะโพสต์ลงกลุ่มจริง", "test": "จะโพสต์ลงกลุ่มทดสอบ"}.get(
            _field(status, "mode"), "dry-run ไม่โพสต์")
        return self._ask(user_id, "on", 0, f"เปิดบอท: {where} | รออยู่ {waiting} รายการ")

    def _ask_skip(self, req: Request) -> str:
        if len(req.args) != 1 or not re.fullmatch(r"[1-9]\d{0,8}", req.args[0]):
            return "ใช้แบบนี้: /skip 128 (เลขรายการหลัง #)"
        item = int(req.args[0])
        return self._ask(req.user_id, "skip", item, f"ข้ามรายการ #{item} บอทจะไม่โพสต์รายการนี้")

    def _confirm(self, req: Request) -> str:
        waiting = self.pending.pop(req.user_id, None)  # one try only, right or wrong
        if waiting is None or self.clock() > waiting.expires:
            return "ไม่มีคำสั่งที่รอยืนยัน หรือหมดเวลาแล้ว"
        if len(req.args) != 1 or not secrets.compare_digest(req.args[0].encode(), waiting.code.encode()):
            return "รหัสไม่ถูก ยกเลิกคำสั่งแล้ว"
        if waiting.action == "skip":
            return self.bot.skip(waiting.item)
        return self._why_not_on(self.bot.status()) or self.bot.on()


class OffsetStore:
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path

    def load(self) -> int | None:
        try:
            return int(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, offset: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(str(offset), encoding="utf-8")
        tmp.replace(self.path)


def process(updates: list[dict], control: Controller, username: str, store: OffsetStore,
            reply: Callable[[str], None]) -> None:
    for update in updates:
        store.save(int(update["update_id"]) + 1)  # before acting: a crash must not repeat a command
        req = parse_update(update, username)
        answer = control.handle(req) if req else None
        if not answer:
            continue
        try:
            reply(answer[:MAX_REPLY_CHARS])
        except (OSError, RuntimeError, ValueError) as exc:
            log.warning("reply failed: %s", exc.__class__.__name__)


def call(token: str, method: str, wait: float = 20, **params: object) -> object:
    """One Telegram API call. `wait` is our network limit; a `timeout` parameter is Telegram's long poll."""
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", data=data, timeout=wait) as resp:
        return json.load(resp)["result"]


def listen(settings: Settings) -> int:
    control = Controller(settings, BotLink(daily_report.BOT_DIR))
    store = OffsetStore(STATE_DIR / "control_offset.txt")
    username = ""
    while True:
        try:
            if not username:
                username = call(settings.token, "getMe")["username"]  # type: ignore[index]
                log.info("listening as %s, %d admins", username, len(settings.admins))
            if store.load() is None:  # first run: ignore everything sent before we existed
                last = call(settings.token, "getUpdates", offset=-1)
                store.save(int(last[-1]["update_id"]) + 1 if last else 0)  # type: ignore[index]
            updates = call(settings.token, "getUpdates", wait=POLL_SEC + 15, timeout=POLL_SEC, limit=20,
                           offset=store.load() or 0, allowed_updates='["message"]')
            process(updates, control, username, store, notify.send)  # type: ignore[arg-type]
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 404, 409):  # bad token, or another program is already listening
                log.error("Telegram refused (HTTP %s), stopping", exc.code)
                return 3
            log.warning("Telegram HTTP %s", exc.code)
            time.sleep(30)
        except OSError as exc:
            log.warning("network: %s", exc.__class__.__name__)
            time.sleep(15)


def add_admin(path: pathlib.Path, user_id: str) -> int:
    admin = _admin_id(user_id)
    if admin is None:
        print("เลขไม่ถูกต้อง")
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = {**data, "admins": sorted({*load_settings(path).admins, admin})}
    path.write_text(json.dumps(updated), encoding="utf-8")
    print("ผู้ดูแล:", updated["admins"])
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--add-admin", metavar="USER_ID")
    args = parser.parse_args(argv)
    if args.add_admin:
        return add_admin(notify.config_path(), args.add_admin)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[
        logging.handlers.RotatingFileHandler(STATE_DIR / "control.log", maxBytes=500_000, backupCount=2,
                                             encoding="utf-8")])
    return listen(load_settings(notify.config_path()))


if __name__ == "__main__":
    sys.exit(main())
