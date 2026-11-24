"""Rules taken from real posts in the LINE OpenChat (24 Nov 2026)."""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import crosscheck  # noqa: E402
import pmweb  # noqa: E402
import postfmt  # noqa: E402

NAME = "ชุดเหล็ก Callaway APEX TCB Forged (รุ่นปี 2022) มีเหล็ก 5-Pw (6 ชิ้น) ก้านเหล็ก NS Pro Modus 120 Flex S"
LINK = "https://www.pmgolfclub.com/product/iron_set/callaway/134140"
REAL_POST = f"""{NAME}

ราคา 13,900 บาท

รายละเอียดเพิ่มเติม
{LINK}

สอบถาม สั่งซื้อ คลิ้กด้านล่างตรงนี้ได้เลยครับ
https://lin.ee/wpRQTtx"""
ANNOUNCEMENT = """📌 📌 ประกาศ (ห้ามพิมพ์) 📌 📌
ห้องนี้เป็นห้องแสดงสินค้าของทางร้านเท่านั้น
https://lin.ee/wpRQTtx
https://www.pmgolfclub.com/product/product_search/
ขอบพระคุณมากครับ"""


def web(name: str = NAME, price: str = "13,900฿", photos: int = 12) -> pmweb.Product:
    return pmweb.Product(134140, "", name, price, "", "Iron set", "Callaway", "", (),
                         tuple(f"https://e.test/{n}.JPG" for n in range(1, photos + 1)))


def post(text: str = REAL_POST, photos: int | None = 1) -> crosscheck.LinePost:
    return crosscheck.LinePost(text, photos)


# ---------- cross-check ----------
def test_one_line_photo_and_twelve_web_photos_is_ok() -> None:
    assert crosscheck.compare(post(), web()).status == crosscheck.OK


@pytest.mark.parametrize(("photos", "expect"), [(0, "ไม่มีรูป"), (13, "มากกว่า")])
def test_impossible_photo_counts_are_reported(photos: int, expect: str) -> None:
    item = crosscheck.compare(post(photos=photos), web())
    assert item.status == crosscheck.MISMATCH and expect in item.problems[0]


def test_unknown_photo_count_is_not_a_problem() -> None:
    assert crosscheck.compare(post(photos=None), web()).status == crosscheck.OK


def test_announcement_is_skipped() -> None:
    item = crosscheck.compare(post(ANNOUNCEMENT), None)
    assert item.status == crosscheck.NOT_PRODUCT and not item.is_problem


def test_product_post_without_link_is_still_a_problem() -> None:
    item = crosscheck.compare(post(f"{NAME}\n\nราคา 13,900 บาท"), None)
    assert item.status == crosscheck.NO_LINK and item.is_problem


def test_product_link_without_price_is_a_problem() -> None:
    item = crosscheck.compare(post(f"{NAME}\n{LINK}"), web())
    assert item.status == crosscheck.MISMATCH and "ไม่มีราคา" in item.problems[0]


@pytest.mark.parametrize("wrong", [NAME.replace("Flex S", "Flex SR"), NAME.replace("5-Pw", "6-Pw"),
                                   NAME.replace("Modus 120", "Modus 105")])
def test_small_spec_differences_are_caught(wrong: str) -> None:
    item = crosscheck.compare(post(), web(name=wrong))
    assert item.status == crosscheck.MISMATCH and "ชื่อไม่ตรง" in item.problems[0]


def test_spacing_difference_is_ignored() -> None:
    assert crosscheck.compare(post(), web(name=NAME.replace(" ", "  "))).status == crosscheck.OK


def test_text_without_line_breaks_is_understood() -> None:
    # the manual says LINE drops line breaks when the bot reads it
    flat = post(REAL_POST.replace("\n", ""))
    assert flat.name == NAME and flat.price_baht == 13900 and flat.product_id == 134140
    assert crosscheck.compare(flat, web()).status == crosscheck.OK


# ---------- post format ----------
def test_format_matches_the_real_line_post_exactly() -> None:
    built = postfmt.build(post(), web())
    assert built.text == REAL_POST
    assert built.photos == ("https://e.test/1.JPG",)


def test_flat_text_is_rebuilt_to_the_same_post() -> None:
    assert postfmt.build(post(REAL_POST.replace("\n", "")), web()).text == REAL_POST


@pytest.mark.parametrize(("line", "product"), [
    (post(), web(price="14,900฿")),
    (post(), web(price="0฿")),
    (post(), None),
    (post(ANNOUNCEMENT), None),
    (post(photos=0), web()),
])
def test_never_builds_a_post_that_failed_the_check(
        line: crosscheck.LinePost, product: pmweb.Product | None) -> None:
    with pytest.raises(postfmt.NotPostable):
        postfmt.build(line, product)


def test_contact_link_must_be_the_shops_own() -> None:
    other = post(REAL_POST.replace("https://lin.ee/wpRQTtx", "https://lin.ee/other"))
    with pytest.raises(postfmt.NotPostable):
        postfmt.build(other, web())
