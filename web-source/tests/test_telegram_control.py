"""Telegram control: who may do what. No network and no real bot."""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import telegram_control as tc  # noqa: E402

CHAT, ADMIN, OTHER, NOW = -100123, 111, 222, 1_800_000_000.0


class FakeBot:
    def __init__(self, mode: str = "dry-run", off: bool = True) -> None:
        self.mode, self.is_off, self.calls = mode, off, []

    def status(self) -> str:
        return (f"mode={self.mode} disabled={self.is_off} supervisor=False heartbeat_age=43s step=stopped\n"
                "line=ok fb=ok pause_until=0 slow=False counts={'NEW': 91, 'POSTED': 116, 'QUEUED': 3}\n"
                "  #128 2026-11-24 22:52:37 QUEUED      134057 photos=1 ")

    def off(self) -> str:
        self.calls.append("off")
        return "ok"

    def on(self) -> str:
        self.calls.append("on")
        return "ok"

    def skip(self, item: int) -> str:
        self.calls.append(f"skip {item}")
        return "ok"

    def speed(self, mode: str) -> str:
        self.calls.append(f"speed {mode}")
        return "ok"

    def report(self) -> str:
        self.calls.append("report")
        return "ok"


def make(bot: FakeBot | None = None, admins: tuple[int, ...] = (ADMIN,), live: bool = False) -> tc.Controller:
    return tc.Controller(tc.Settings("t", CHAT, frozenset(admins), live), bot or FakeBot(), clock=lambda: NOW)


def update(text: str, user: int = ADMIN, chat: int = CHAT, date: float = NOW, **extra) -> dict:
    return {"update_id": 1, "message": {"text": text, "date": date, "chat": {"id": chat},
                                        "from": {"id": user, "first_name": "x", "is_bot": False}, **extra}}


def say(control: tc.Controller, text: str, **kw) -> str | None:
    req = tc.parse_update(update(text, **kw), "PNGolfbot")
    return control.handle(req) if req else None


def code_of(reply: str | None) -> str:
    assert reply and "/confirm " in reply
    return reply.split("/confirm ")[1].split()[0]


# ---------- which messages count ----------
def test_plain_chat_is_ignored() -> None:
    assert tc.parse_update(update("ปิดบอท"), "PNGolfbot") is None


def test_command_for_another_bot_is_ignored() -> None:
    assert tc.parse_update(update("/off@OtherBot"), "PNGolfbot") is None


def test_command_addressed_to_us_works() -> None:
    req = tc.parse_update(update("/OFF@pngolfbot"), "PNGolfbot")
    assert req and req.command == "off"


@pytest.mark.parametrize("extra", [
    {"forward_origin": {"type": "user"}},
    {"sender_chat": {"id": CHAT}},                     # anonymous admin or channel
    {"from": {"id": ADMIN, "is_bot": True}},
    {"via_bot": {"id": 5}},
])
def test_forwarded_anonymous_and_bot_messages_are_ignored(extra: dict) -> None:
    assert tc.parse_update(update("/off", **extra), "PNGolfbot") is None


def test_edited_messages_are_ignored() -> None:
    edited = {"update_id": 1, "edited_message": update("/off")["message"]}
    assert tc.parse_update(edited, "PNGolfbot") is None


# ---------- who may command ----------
def test_other_chat_gets_no_reply_even_for_admin() -> None:
    bot = FakeBot()
    assert say(make(bot), "/off", chat=999) is None and bot.calls == []


@pytest.mark.parametrize("text", ["/off", "/on", "/skip 128", "/slow", "/normal", "/report", "/status", "/confirm 1234"])
def test_non_admin_cannot_do_anything(text: str) -> None:
    bot = FakeBot()
    reply = say(make(bot), text, user=OTHER)
    assert bot.calls == [] and "ไม่มีสิทธิ์" in (reply or "") and "134057" not in (reply or "")


def test_no_admins_configured_means_nobody() -> None:
    bot = FakeBot()
    say(make(bot, admins=()), "/off")
    assert bot.calls == []


def test_whoami_shows_only_the_callers_own_id() -> None:
    assert str(OTHER) in (say(make(), "/whoami", user=OTHER) or "")


def test_old_commands_are_not_replayed() -> None:
    bot = FakeBot()
    assert say(make(bot), "/off", date=NOW - 600) is None and bot.calls == []


# ---------- commands ----------
def test_off_is_immediate() -> None:
    bot = FakeBot(off=False)
    say(make(bot), "/off")
    assert bot.calls == ["off"]


def test_on_needs_the_code() -> None:
    bot = FakeBot()
    control = make(bot)
    reply = say(control, "/on")
    assert bot.calls == [] and "dry-run" in (reply or "")
    say(control, f"/confirm {code_of(reply)}")
    assert bot.calls == ["on"]


def test_code_works_once() -> None:
    bot = FakeBot()
    control = make(bot)
    code = code_of(say(control, "/on"))
    say(control, f"/confirm {code}")
    say(control, f"/confirm {code}")
    assert bot.calls == ["on"]


def test_wrong_code_cancels() -> None:
    bot = FakeBot()
    control = make(bot)
    code = code_of(say(control, "/on"))
    say(control, "/confirm 00000")
    say(control, f"/confirm {code}")
    assert bot.calls == []


def test_code_belongs_to_the_person_who_asked() -> None:
    bot = FakeBot()
    control = make(bot, admins=(ADMIN, OTHER))
    code = code_of(say(control, "/on"))
    say(control, f"/confirm {code}", user=OTHER)
    assert bot.calls == []


def test_code_expires() -> None:
    bot, now = FakeBot(), [NOW]
    control = tc.Controller(tc.Settings("t", CHAT, frozenset({ADMIN}), False), bot, clock=lambda: now[0])
    code = code_of(say(control, "/on"))
    now[0] = NOW + 61
    req = tc.parse_update(update(f"/confirm {code}", date=now[0]), "PNGolfbot")
    assert req is not None
    control.handle(req)
    assert bot.calls == []


def test_live_mode_cannot_be_started_by_default() -> None:
    bot = FakeBot(mode="live")
    reply = say(make(bot), "/on")
    assert "/confirm" not in (reply or "") and bot.calls == []


def test_live_is_checked_again_at_confirm() -> None:
    bot = FakeBot(mode="dry-run")
    control = make(bot)
    code = code_of(say(control, "/on"))
    bot.mode = "live"
    say(control, f"/confirm {code}")
    assert bot.calls == []


def test_live_start_when_allowed_warns_about_the_real_group() -> None:
    bot = FakeBot(mode="live")
    control = make(bot, live=True)
    reply = say(control, "/on")
    assert "กลุ่มจริง" in (reply or "") and "94" in (reply or "")
    say(control, f"/confirm {code_of(reply)}")
    assert bot.calls == ["on"]


def test_on_refuses_when_status_cannot_be_read() -> None:
    bot = FakeBot()
    bot.status = lambda: "boom"  # type: ignore[method-assign]
    reply = say(make(bot), "/on")
    assert "/confirm" not in (reply or "") and bot.calls == []


def test_skip_needs_a_number_and_a_code() -> None:
    bot = FakeBot()
    control = make(bot)
    for bad in ("/skip", "/skip abc", "/skip 1;calc", "/skip -1", "/skip 1 2", "/skip 99999999999"):
        say(control, bad)
    assert bot.calls == []
    say(control, f"/confirm {code_of(say(control, '/skip 128'))}")
    assert bot.calls == ["skip 128"]


@pytest.mark.parametrize("text", ["/post 128", "/retry 128", "/resume", "/live", "/prepare", "/startfrom 1", "/exec dir"])
def test_commands_that_could_post_do_not_exist(text: str) -> None:
    bot = FakeBot()
    assert "ไม่รู้จัก" in (say(make(bot), text) or "") and bot.calls == []


def test_speed_status_and_report() -> None:
    bot = FakeBot()
    control = make(bot)
    say(control, "/slow")
    say(control, "/normal")
    say(control, "/report")
    text = say(control, "/status") or ""
    assert bot.calls == ["speed slow", "speed normal", "report"]
    assert "dry-run" in text and "ปิด" in text and "91" in text


def test_bot_errors_become_a_reply_not_a_crash() -> None:
    bot = FakeBot()

    def boom() -> str:
        raise OSError("disk")
    bot.off = boom  # type: ignore[method-assign]
    assert "ไม่สำเร็จ" in (say(make(bot), "/off") or "")


# ---------- real link to the bot folder ----------
def test_off_writes_the_flag(tmp_path: pathlib.Path) -> None:
    (tmp_path / "run").mkdir()
    tc.BotLink(tmp_path).off()
    assert (tmp_path / "run" / "disabled.flag").exists()


def test_off_fails_loudly_without_a_bot(tmp_path: pathlib.Path) -> None:
    with pytest.raises(OSError):
        tc.BotLink(tmp_path / "nope").off()


def test_bot_commands_never_use_a_shell(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[list[str], dict]] = []

    def fake_run(cmd: list[str], **kw):
        seen.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, b"ok", b"")
    monkeypatch.setattr(tc.subprocess, "run", fake_run)
    tc.BotLink(tmp_path).skip(128)
    cmd, kw = seen[0]
    assert cmd[1:] == ["-m", "pmbot", "skip", "128"] and not kw.get("shell")


def test_failed_bot_command_is_an_error(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tc.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b"bad"))
    with pytest.raises(OSError):
        tc.BotLink(tmp_path).skip(1)


# ---------- polling ----------
def test_offset_is_saved_before_the_command_runs(tmp_path: pathlib.Path) -> None:
    store = tc.OffsetStore(tmp_path / "o.json")
    order: list[str] = []

    class Spy(tc.Controller):
        def handle(self, req: tc.Request) -> str | None:
            order.append(f"handled with offset {store.load()}")
            raise RuntimeError("crash while handling")

    control = Spy(tc.Settings("t", CHAT, frozenset({ADMIN}), False), FakeBot(), clock=lambda: NOW)
    with pytest.raises(RuntimeError):
        tc.process([{**update("/off"), "update_id": 7}], control, "PNGolfbot", store, lambda _t: None)
    assert order == ["handled with offset 8"] and store.load() == 8


def test_failed_reply_does_not_stop_the_listener(tmp_path: pathlib.Path) -> None:
    def broken(_text: str) -> None:
        raise OSError("offline")
    bot = FakeBot()
    tc.process([{**update("/off"), "update_id": 7}], make(bot), "PNGolfbot", tc.OffsetStore(tmp_path / "o"), broken)
    assert bot.calls == ["off"]


def test_settings_reject_bad_admins(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "t.json"
    f.write_text('{"bot_token":"t","chat_id":"-100123","admins":[111,"222","x",true,-5]}', encoding="utf-8")
    s = tc.load_settings(f)
    assert s.admins == frozenset({111, 222}) and s.allow_live_on is False


def test_off_cancels_a_waiting_on() -> None:
    bot = FakeBot()
    control = make(bot, admins=(ADMIN, OTHER))
    code = code_of(say(control, "/on"))
    say(control, "/off", user=OTHER)
    say(control, f"/confirm {code}")
    assert bot.calls == ["off"]


class FakeProc:
    def __init__(self) -> None:
        self.done: int | None = None

    def poll(self) -> int | None:
        return self.done


def test_report_runs_once_at_a_time_and_with_a_console_python(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    proc = FakeProc()
    monkeypatch.setattr(tc.sys, "executable", str(tmp_path / "pythonw.exe"))
    (tmp_path / "python.exe").write_text("")
    monkeypatch.setattr(tc.subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or proc)
    link = tc.BotLink(tmp_path)
    link.report()
    assert "กำลังทำอยู่" in link.report()
    proc.done = 0
    link.report()
    assert len(started) == 2 and started[0][0].endswith("python.exe")  # pythonw has no stdout and would crash


def test_polling_asks_telegram_to_wait(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    calls: list[tuple[str, dict]] = []

    class Stop(Exception):
        pass

    def fake_call(_token: str, method: str, wait: float = 20, **params: object) -> object:
        calls.append((method, {"wait": wait, **params}))
        if method == "getMe":
            return {"username": "PNGolfbot"}
        if params.get("offset") == -1:
            return [{"update_id": 41}]
        raise Stop
    monkeypatch.setattr(tc, "call", fake_call)
    monkeypatch.setattr(tc, "STATE_DIR", tmp_path)
    with pytest.raises(Stop):
        tc.listen(tc.Settings("t", CHAT, frozenset({ADMIN}), False))
    method, params = calls[-1]
    assert method == "getUpdates" and params["timeout"] == tc.POLL_SEC and params["wait"] > tc.POLL_SEC
    assert params["offset"] == 42  # messages from before the first start are skipped


def test_add_admin_keeps_other_settings(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "t.json"
    f.write_text('{"bot_token":"t","chat_id":"-1001","admins":[111]}', encoding="utf-8")
    assert tc.add_admin(f, "2222") == 0 and tc.add_admin(f, "2x") == 2
    s = tc.load_settings(f)
    assert s.admins == frozenset({111, 2222}) and s.token == "t"
