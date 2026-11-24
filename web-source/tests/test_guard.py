"""Tests for the machine guard's alerts (Telegram is always mocked)."""
from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(next(ROOT.rglob("guard_helper.py")).parent))
sys.path.insert(0, str(ROOT / "web-source"))
import daily_report as dr  # noqa: E402
import guard_helper as g  # noqa: E402


class Box:
    """Fake Telegram: collects messages, can be switched to failing."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.up = True

    def send(self, text: str) -> bool:
        if self.up:
            self.sent.append(text)
        return self.up


@pytest.fixture
def box() -> Box:
    return Box()


@pytest.fixture
def guard(tmp_path: pathlib.Path, box: Box, monkeypatch: pytest.MonkeyPatch) -> g.Guard:
    for d in ("run", "data"):
        (tmp_path / d).mkdir()
    item = g.Guard(tmp_path)
    monkeypatch.setattr(item, "send_telegram", box.send)
    beat(item, 1)
    statuses(item, [])
    return item


def beat(guard: g.Guard, age_min: float) -> None:
    f = guard.bot / "run" / "heartbeat.json"
    f.write_text("{}")
    t = time.time() - age_min * 60
    os.utime(f, (t, t))


def statuses(guard: g.Guard, values: list[str]) -> None:
    con = sqlite3.connect(guard.db)
    con.execute("create table if not exists items(status text)")
    con.execute("delete from items")
    con.executemany("insert into items values(?)", [(v,) for v in values])
    con.commit()
    con.close()


def test_healthy_bot_sends_nothing(guard: g.Guard, box: Box) -> None:
    guard.bot_health()
    assert box.sent == []


def test_silent_bot_alerts_once_then_recovers(guard: g.Guard, box: Box) -> None:
    beat(guard, 30)
    guard.bot_health()
    guard.bot_health()
    assert len(box.sent) == 1 and "เงียบ" in box.sent[0]
    beat(guard, 1)
    guard.bot_health()
    guard.bot_health()
    assert len(box.sent) == 2 and "กลับมาปกติ" in box.sent[1]


def test_new_incident_after_recovery_is_not_throttled(guard: g.Guard, box: Box) -> None:
    for age in (30, 1, 30):
        beat(guard, age)
        guard.bot_health()
    assert len(box.sent) == 3


def test_intentionally_off_is_quiet(guard: g.Guard, box: Box) -> None:
    beat(guard, 300)
    (guard.bot / "run" / "disabled.flag").write_text("off")
    guard.bot_health()
    assert box.sent == []


def test_turning_bot_off_is_not_announced_as_recovery(guard: g.Guard, box: Box) -> None:
    beat(guard, 30)
    guard.bot_health()
    (guard.bot / "run" / "disabled.flag").write_text("off")
    guard.bot_health()
    assert len(box.sent) == 1


@pytest.mark.parametrize("status", ["NEEDS_HUMAN", "FAILED"])
def test_queue_problem_alerts_on_increase_and_recovers(guard: g.Guard, box: Box, status: str) -> None:
    statuses(guard, [status])
    guard.bot_health()
    guard.bot_health()
    assert len(box.sent) == 1 and status in box.sent[0]
    statuses(guard, [status, status])
    guard.bot_health()
    assert len(box.sent) == 2
    statuses(guard, ["POSTED"])
    guard.bot_health()
    assert len(box.sent) == 3 and "กลับมาปกติ" in box.sent[2]


@pytest.mark.parametrize("status", ["NEEDS_HUMAN", "SKIPPED"])
def test_failed_telegram_send_is_retried(guard: g.Guard, box: Box, status: str) -> None:
    guard.bot_health()
    box.up = False
    statuses(guard, [status])
    guard.bot_health()
    box.up = True
    guard.bot_health()
    guard.bot_health()
    assert len(box.sent) == 1 and status in box.sent[0]


def test_failed_recovery_message_is_retried(guard: g.Guard, box: Box) -> None:
    beat(guard, 30)
    guard.bot_health()
    box.up = False
    beat(guard, 1)
    guard.bot_health()
    box.up = True
    guard.bot_health()
    assert len(box.sent) == 2 and "กลับมาปกติ" in box.sent[1]


def test_existing_skipped_items_are_only_a_baseline(guard: g.Guard, box: Box) -> None:
    statuses(guard, ["SKIPPED"] * 5)
    guard.bot_health()
    assert box.sent == []
    statuses(guard, ["SKIPPED"] * 7)
    guard.bot_health()
    assert len(box.sent) == 1 and "2" in box.sent[0]


def test_unknown_schema_is_reported_instead_of_looking_healthy(guard: g.Guard, box: Box) -> None:
    con = sqlite3.connect(guard.db)
    con.execute("drop table items")
    con.execute("create table other(state text)")
    con.commit()
    con.close()
    guard.bot_health()
    assert len(box.sent) == 1 and "pmbot.db" in box.sent[0]


def test_resolve_without_open_alert_is_silent(guard: g.Guard, box: Box) -> None:
    guard.resolve("disk")
    assert box.sent == []


def test_old_state_file_is_accepted(guard: g.Guard, box: Box) -> None:
    guard.save_state({"last_alert": {"disk": 1.0}, "skipped_count": 2})
    statuses(guard, ["SKIPPED"] * 3)
    guard.bot_health()
    assert len(box.sent) == 1


def test_daily_report_does_not_fail_when_bot_is_switched_off(guard: g.Guard) -> None:
    beat(guard, 300)
    (guard.bot / "run" / "disabled.flag").write_text("off")
    found = dr.check_bot_alive(guard.bot, time.time())
    assert [f.level for f in found] == [dr.WARN] and found[0].fix_key == "bot_off"
