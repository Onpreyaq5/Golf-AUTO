"""Price states seen on the live site on 24 Nov 2026: normal, sale, sold, 0 baht."""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import crosscheck  # noqa: E402
import daily_report as dr  # noqa: E402
import pmweb  # noqa: E402
import postfmt  # noqa: E402

NAME = "ไดรเวอร์ Callaway Quantum Max Loft 10.5 Flex S"
CELL = '<div align="left" style="width: 50%;">'
NORMAL = f'<div>ราคา</div><div class="price_normal">26,800฿</div>'
SALE = (f'<div>ราคาพิเศษ</div>{CELL}<span class="price_sale"> 13,900฿</span> '
        '<span class="price_normal" style=\'text-decoration:line-through;\'>14,900฿</span></div>')
SOLD = f'<div>ราคา</div>{CELL}<img src="https://www.pmgolfclub.com/image/new/sold_out.png" alt="{NAME}"/></div>'
ZERO = '<div>ราคา</div><div class="price_normal">0฿</div>'
MENU = '<li id="list_sold_out"><a href="https://www.pmgolfclub.com/product/sold_out">Sold Out</a></li>'
LINK = "https://www.pmgolfclub.com/product/driver/callaway/134147"


def page(price: str) -> str:
    related = '<div>สินค้าเกี่ยวข้อง</div><img src="/image/new/sold_out.png"><div class="product_price price">900฿</div>'
    return (f'{MENU}<h1 class="view">{NAME}</h1><a data-zoom-image="https://e.test/1.JPG"></a>'
            f'<div>สภาพสินค้า</div><div>NEW</div>{price}<div>รายละเอียดเพิ่มเติม</div><div>ดี</div>{related}{MENU}')


def product(price: str, pid: int = 134147) -> pmweb.Product:
    result = pmweb.parse_product(page(price), pid)
    assert result is not None
    return result


def line(price: str) -> crosscheck.LinePost:
    return crosscheck.LinePost(f"{NAME}\n\nราคา {price} บาท\n\nรายละเอียดเพิ่มเติม\n{LINK}\n\n"
                               "สอบถาม สั่งซื้อ คลิ้กด้านล่างตรงนี้ได้เลยครับ\nhttps://lin.ee/wpRQTtx", 1)


# ---------- parsing ----------
def test_normal_price() -> None:
    p = product(NORMAL)
    assert (p.price_baht, p.old_price, p.sold, p.is_ready) == (26800, "", False, True)


def test_sale_price_is_the_price_to_sell_at() -> None:
    p = product(SALE)
    assert (p.price, p.price_baht, p.old_price, p.is_ready) == ("13,900฿", 13900, "14,900฿", True)


def test_sold_is_not_ready() -> None:
    p = product(SOLD)
    assert p.sold and not p.is_ready and p.price_baht == 0


def test_sold_links_in_menu_and_related_items_do_not_count() -> None:
    assert not product(NORMAL).sold


def test_zero_price_is_not_ready_and_not_sold() -> None:
    p = product(ZERO)
    assert not p.sold and not p.is_ready


@pytest.mark.parametrize("text", ["13,900฿ 14,900฿", "โทรถาม", "", "13,900-14,900฿"])
def test_unclear_price_is_never_guessed(text: str) -> None:
    p = pmweb.Product(1, "", "x", text, "", "", "", "", (), ("i",))
    assert p.price_baht == 0 and not p.is_ready


# ---------- scan ----------
def test_scan_separates_sold_from_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    items = {1: product(NORMAL, 1), 2: product(SOLD, 2), 3: product(ZERO, 3)}
    monkeypatch.setattr(pmweb, "fetch_product", items.get)
    monkeypatch.setattr(pmweb.time, "sleep", lambda _s: None)
    result = pmweb.scan_new(0, lookahead=2)
    assert [p.product_id for p in result.ready] == [1]
    assert (result.pending, result.sold) == ((3,), (2,))


def test_recheck_drops_items_sold_meanwhile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pmweb, "fetch_product", {2: product(SOLD, 2)}.get)
    monkeypatch.setattr(pmweb.time, "sleep", lambda _s: None)
    result = pmweb.recheck([2])
    assert result.pending == () and result.sold == (2,)


def test_daily_report_does_not_ask_for_a_price_on_sold_items(monkeypatch: pytest.MonkeyPatch) -> None:
    scans = pmweb.ScanResult((), (), 10, sold=(9,))
    monkeypatch.setattr(pmweb, "scan_new", lambda _since: scans)
    monkeypatch.setattr(pmweb, "recheck", lambda _ids: pmweb.ScanResult((), (), 8, sold=(8,)))
    state = {"web_last_id": 5, "web_pending": [8]}
    found = dr.check_web(state)
    assert all(f.level == dr.OK for f in found) and state["web_pending"] == []
    assert "ขายแล้ว 2" in found[0].detail


# ---------- cross-check and post ----------
def test_line_sale_price_matches_web_sale_price() -> None:
    assert crosscheck.compare(line("13,900"), product(SALE)).status == crosscheck.OK
    assert "ราคา 13,900 บาท" in postfmt.build(line("13,900"), product(SALE)).text


def test_line_with_old_price_is_reported() -> None:
    item = crosscheck.compare(line("14,900"), product(SALE))
    assert item.status == crosscheck.MISMATCH and "ราคาเดิม" in item.problems[0]


def test_sold_item_is_not_a_data_error_but_is_never_posted() -> None:
    item = crosscheck.compare(line("13,900"), product(SOLD))
    assert item.status == crosscheck.SOLD and not item.is_problem
    with pytest.raises(postfmt.NotPostable):
        postfmt.build(line("13,900"), product(SOLD))
