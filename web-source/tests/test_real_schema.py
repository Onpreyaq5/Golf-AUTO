"""Uses the real pmbot.db columns read on the bot machine (24 Nov 2026)."""
from __future__ import annotations

import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(next(ROOT.rglob("guard_helper.py")).parent))
sys.path.insert(0, str(ROOT / "web-source"))
import crosscheck  # noqa: E402
import daily_report as dr  # noqa: E402
import guard_helper as g  # noqa: E402

ITEMS = ("id integer primary key, msg_key, product_id text, product_url, line_time, text_name, text_flat, "
         "text_post, format_ok, photo_total, photos_json, state, reason, attempts, photo_attempts, "
         "verify_attempts, next_attempt_at, first_seen, queued_at, posting_started_at, posted_at, target, "
         "verified, updated_at")
FLAT = ("ชุดเหล็ก Ping G430ราคา 20,800 บาทรายละเอียดเพิ่มเติม"
        "https://www.pmgolfclub.com/product/iron_set/ping/134104สอบถาม สั่งซื้อ https://lin.ee/wpRQTtx")


@pytest.fixture
def bot(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "run").mkdir()
    return tmp_path


def make_db(bot: pathlib.Path, states: list[str]) -> None:
    con = sqlite3.connect(bot / "data" / "pmbot.db")
    con.execute(f"create table items({ITEMS})")
    con.execute("create table events(id integer primary key, ts, item_id, kind, detail)")
    con.execute("create table outbox(id integer primary key, ts, text, photo, sent, tries)")
    con.execute("create table seen(key, first_seen, item_id)")
    con.execute("insert into outbox(text) values('https://www.pmgolfclub.com/product/a/b/999999 alert')")
    for state in states:
        con.execute("insert into items(product_id, text_name, text_flat, photo_total, state, first_seen) "
                    "values('134104', 'x', ?, 1, ?, 1795269906.5)", (FLAT, state))
    con.commit()
    con.close()


def test_guard_counts_the_state_column(bot: pathlib.Path) -> None:
    make_db(bot, ["POSTED", "POSTED", "NEEDS_HUMAN", "NEW"])
    assert g.Guard(bot).status_counts() == {"POSTED": 2, "NEEDS_HUMAN": 1, "NEW": 1}


def test_guard_alerts_on_needs_human(bot: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_db(bot, ["NEEDS_HUMAN"])
    guard = g.Guard(bot)
    sent: list[str] = []
    monkeypatch.setattr(guard, "send_telegram", lambda text: sent.append(text) or True)
    guard.check_queue()
    assert len(sent) == 1 and "NEEDS_HUMAN" in sent[0]


def test_report_shows_needs_human(bot: pathlib.Path) -> None:
    make_db(bot, ["POSTED", "NEEDS_HUMAN"])
    found = dr.check_queue(bot)
    assert "POSTED 1" in found[0].detail
    assert any(f.level == dr.FAIL and f.fix_key == "needs_human" for f in found)


def test_report_never_says_empty_when_the_queue_is_unreadable(bot: pathlib.Path) -> None:
    con = sqlite3.connect(bot / "data" / "pmbot.db")
    con.execute("create table other(x)")
    con.commit()
    con.close()
    assert [f.level for f in dr.check_queue(bot)] == [dr.WARN]


def test_line_posts_come_from_items_not_from_alerts(bot: pathlib.Path) -> None:
    make_db(bot, ["POSTED"])
    posts = crosscheck.posts_from_bot_db(bot / "data" / "pmbot.db")
    assert [(p.product_id, p.price_baht, p.photo_count, p.name) for p in posts] == [
        (134104, 20800, 1, "ชุดเหล็ก Ping G430")]


def test_report_waits_between_web_requests(bot: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_db(bot, ["POSTED"])
    waits: list[float] = []
    monkeypatch.setattr(dr.pmweb, "fetch_product", lambda _pid: None)
    monkeypatch.setattr(dr.time, "sleep", waits.append)
    dr.check_crosscheck(bot)
    assert waits == [dr.pmweb.REQUEST_GAP_SEC]
