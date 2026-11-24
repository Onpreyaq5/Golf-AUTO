"""Tests for crosscheck, daily_report and notify (no network)."""
from __future__ import annotations

import pathlib
import sqlite3
import sys
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import crosscheck  # noqa: E402
import daily_report as dr  # noqa: E402
import notify  # noqa: E402
import pmweb  # noqa: E402

LINE_TEXT = """ไดรเวอร์ XXIO 9 Miyazaki Model (ออกปี 2016) Loft 10.5 Flex S

ราคา 2,500 บาท

รายละเอียดเพิ่มเติม
https://www.pmgolfclub.com/product/driver/xxio/133967

สอบถาม สั่งซื้อ"""


def web(pid: int = 133967, price: str = "2,500฿", n_images: int = 3,
        name: str = "ไดรเวอร์ XXIO 9 Miyazaki Model (ออกปี 2016) Loft 10.5 Flex S") -> pmweb.Product:
    return pmweb.Product(pid, "", name, price, "", "", "", "", (), tuple(f"i{n}" for n in range(n_images)))


# ---------- crosscheck ----------
def test_line_post_parsing() -> None:
    post = crosscheck.LinePost(LINE_TEXT, 3)
    assert post.product_id == 133967 and post.price_baht == 2500
    assert post.name.startswith("ไดรเวอร์ XXIO 9")


def test_matching_post_is_ok() -> None:
    item = crosscheck.compare(crosscheck.LinePost(LINE_TEXT, 3), web())
    assert item.status == crosscheck.OK and item.problems == ()


@pytest.mark.parametrize(("product", "photos", "expect"), [
    (web(price="2,900฿"), 3, "ราคาไม่ตรง"),
    (web(n_images=5), 3, "จำนวนรูปไม่ตรง"),
    (web(name="พัตเตอร์ Odyssey White Hot"), 3, "ชื่อไม่ตรง"),
])
def test_mismatches_are_reported(product: pmweb.Product, photos: int, expect: str) -> None:
    item = crosscheck.compare(crosscheck.LinePost(LINE_TEXT, photos), product)
    assert item.status == crosscheck.MISMATCH and any(expect in p for p in item.problems)


def test_missing_and_not_ready_and_no_link() -> None:
    assert crosscheck.compare(crosscheck.LinePost(LINE_TEXT), None).status == crosscheck.NOT_ON_WEB
    assert crosscheck.compare(crosscheck.LinePost(LINE_TEXT), web(price="0฿")).status == crosscheck.NOT_READY_ON_WEB
    assert crosscheck.compare(crosscheck.LinePost("ไม่มีลิงก์"), None).status == crosscheck.NO_LINK


def test_crosscheck_reports_web_only_and_caches_fetch() -> None:
    calls: list[int] = []
    posts = [crosscheck.LinePost(LINE_TEXT, 3), crosscheck.LinePost(LINE_TEXT, 3)]
    items = crosscheck.crosscheck(posts, fetch=lambda pid: calls.append(pid) or web(), web_ready_ids=[133967, 133970])
    assert calls == [133967]
    assert [i.status for i in items] == [crosscheck.OK, crosscheck.OK, crosscheck.WEB_ONLY]


def test_posts_from_unknown_bot_db_schema(tmp_path: pathlib.Path) -> None:
    db = tmp_path / "pmbot.db"
    with sqlite3.connect(db) as con:
        con.execute("create table meta(k text)")
        con.execute("create table items(id integer primary key, raw_text text, n_photos int, status text)")
        con.execute("insert into items(raw_text, n_photos, status) values(?, 3, 'POSTED')", (LINE_TEXT,))
    con.close()
    posts = crosscheck.posts_from_bot_db(db)
    assert len(posts) == 1 and posts[0].product_id == 133967 and posts[0].photo_count == 3


# ---------- daily report ----------
def make_bot(tmp_path: pathlib.Path, beat_age_min: float = 1) -> pathlib.Path:
    bot = tmp_path / "bot"
    for d in ("run", "data", "logs"):
        (bot / d).mkdir(parents=True)
    beat = bot / "run" / "heartbeat.json"
    beat.write_text("{}")
    t = time.time() - beat_age_min * 60
    import os
    os.utime(beat, (t, t))
    return bot


def test_missing_bot_folder_is_fail_with_fix(tmp_path: pathlib.Path) -> None:
    [f] = dr.check_bot_alive(tmp_path / "nope", time.time())
    assert f.level == dr.FAIL and f.fix_key == "bot_missing"


def test_stale_heartbeat_fails(tmp_path: pathlib.Path) -> None:
    assert dr.check_bot_alive(make_bot(tmp_path, 5), time.time())[0].level == dr.OK
    stale = dr.check_bot_alive(make_bot(tmp_path / "b", 45), time.time())
    assert stale[0].level == dr.FAIL and stale[0].fix_key == "heartbeat"


def test_queue_flags_needs_human(tmp_path: pathlib.Path) -> None:
    bot = make_bot(tmp_path)
    with sqlite3.connect(bot / "data" / "pmbot.db") as con:
        con.execute("create table items(status text)")
        con.executemany("insert into items values(?)", [("POSTED",), ("NEEDS_HUMAN",), ("FAILED",)])
    con.close()
    keys = {f.fix_key for f in dr.check_queue(bot)}
    assert {"needs_human", "failed"} <= keys


def test_logs_are_grouped_by_component(tmp_path: pathlib.Path) -> None:
    bot = make_bot(tmp_path)
    (bot / "logs" / "bot.log").write_text(
        "10:00 INFO ok\n10:01 ERROR photo_grabber save dialog timeout\n"
        "10:02 ERROR fb_poster composer not page\n10:03 ERROR photo_grabber again\n", encoding="utf-8")
    found = {f.fix_key: f for f in dr.check_logs(bot, 0)}
    assert set(found) == {"photo_grabber", "fb_poster"}
    assert "2 ครั้ง" in found["photo_grabber"].detail


def test_report_lists_problem_location_and_fix() -> None:
    findings = [dr.Finding("ดิสก์", dr.OK, "เหลือ 50 GB"),
                dr.Finding("log: fb_poster", dr.FAIL, "ERROR 6 ครั้ง", "fb_poster")]
    text = dr.build_report(findings, dr.dt.datetime(2026, 11, 24, 21, 30))
    assert "มีจุดล่ม ต้องแก้" in text and "[log: fb_poster]" in text
    assert dr.PLAYBOOK["fb_poster"] in text and "✅ ดิสก์" in text


def test_all_ok_report() -> None:
    text = dr.build_report([dr.Finding("ดิสก์", dr.OK, "เหลือ 50 GB")], dr.dt.datetime(2026, 11, 24))
    assert "ระบบปกติ ไม่ล่ม" in text and "วิธีแก้" not in text


def test_broken_check_does_not_kill_report() -> None:
    def boom() -> list[dr.Finding]:
        raise RuntimeError("x")
    [f] = dr._safe(boom)
    assert f.level == dr.WARN


@pytest.mark.parametrize(("output", "level"), [(None, dr.WARN), ("", dr.OK), ("Event[0]:", dr.FAIL)])
def test_power_check_never_reports_ok_when_unreadable(
        monkeypatch: pytest.MonkeyPatch, output: str | None, level: str) -> None:
    monkeypatch.setattr(dr, "_run", lambda _cmd: output)
    assert dr.check_power()[0].level == level


def test_every_fix_key_has_playbook_entry() -> None:
    for key in (*dr.LOG_COMPONENTS, "other_error"):
        assert key in dr.PLAYBOOK


# ---------- notify ----------
def test_split_message_respects_limit() -> None:
    text = "\n".join(f"line {n} " + "x" * 50 for n in range(300))
    parts = notify.split_message(text, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(parts) == text


def test_split_message_cuts_very_long_line() -> None:
    parts = notify.split_message("a" * 2500, limit=1000)
    assert [len(p) for p in parts] == [1000, 1000, 500]
