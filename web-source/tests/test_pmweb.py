"""Tests for pmweb using real pages saved from pmgolfclub.com (no network)."""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pmweb  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def product() -> pmweb.Product:
    result = pmweb.parse_product(load("product_133967.html"), 133967)
    assert result is not None
    return result


def test_parses_name_and_fields(product: pmweb.Product) -> None:
    assert product.name == "ไดรเวอร์ XXIO 9 Miyazaki Model (ออกปี 2016) Loft 10.5 Flex S"
    assert product.sku == "ka498b"
    assert product.category == "Driver"
    assert product.brand == "XXIO"
    assert product.condition == "80-85%"
    assert product.url == "https://www.pmgolfclub.com/product/x/x/133967"


def test_price_is_main_product_not_related(product: pmweb.Product) -> None:
    # related products further down the page show 1,900 / 6,800 / 5,500 / 900
    assert product.price == "2,500฿"


def test_details_stop_before_related_products(product: pmweb.Product) -> None:
    assert product.details[0] == "ไดรเวอร์ XXIO 9 Miyazaki Model"
    assert "Flex S" in product.details
    assert any("Miyazaki" in line and "โรงงาน" in line for line in product.details)
    assert all("฿" not in line for line in product.details)


def test_images_unique_full_size_and_skip_commented_out(product: pmweb.Product) -> None:
    assert product.images, "expected gallery images"
    assert len(product.images) == len(set(product.images))
    assert all(u.startswith("https://www.pmgolfclub.com/manage/product/product_picture/") for u in product.images)
    raw = load("product_133967.html")
    commented = set(pmweb.IMAGE_RE.findall("".join(pmweb.COMMENT_RE.findall(raw))))
    assert not commented & set(product.images)


def test_missing_product_returns_none() -> None:
    assert pmweb.parse_product(load("product_missing.html"), 999999) is None


def make(pid: int, price: str = "1,500฿", images: tuple[str, ...] = ("https://e.test/a.JPG",)) -> pmweb.Product:
    return pmweb.Product(pid, pmweb.product_url(pid), f"P{pid}", price, "", "", "", "", (), images)


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pmweb.time, "sleep", lambda _s: None)


@pytest.mark.parametrize(("price", "images", "ready"), [
    ("2,500฿", ("x",), True),
    ("0฿", ("x",), False),          # not ready for sale yet
    ("", ("x",), False),            # no price
    ("2,500฿", (), False),          # no photos
    ("1,234.50฿", ("x",), True),
])
def test_is_ready(price: str, images: tuple[str, ...], ready: bool) -> None:
    assert make(1, price, images).is_ready is ready


def test_scan_splits_ready_and_pending(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    # 103-104 are a gap that must not stop the scan; 102 is 0฿ (not ready)
    items = {101: make(101), 102: make(102, "0฿"), 105: make(105)}
    calls: list[int] = []
    monkeypatch.setattr(pmweb, "fetch_product", lambda pid: calls.append(pid) or items.get(pid))

    result = pmweb.scan_new(100, lookahead=3)

    assert [p.product_id for p in result.ready] == [101, 105]
    assert result.pending == (102,)
    assert result.last_id == 105
    assert calls == [101, 102, 103, 104, 105, 106, 107, 108]


def test_scan_with_nothing_new_keeps_since_id(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    monkeypatch.setattr(pmweb, "fetch_product", lambda _pid: None)
    assert pmweb.scan_new(500, lookahead=2).last_id == 500


def test_scan_respects_max_ids(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    monkeypatch.setattr(pmweb, "fetch_product", make)
    result = pmweb.scan_new(0, lookahead=3, max_ids=10)
    assert len(result.ready) == 10 and result.last_id == 10


def test_recheck_promotes_ready_and_drops_deleted(monkeypatch: pytest.MonkeyPatch, no_sleep: None) -> None:
    items = {7: make(7), 8: make(8, "0฿")}  # 9 was deleted
    monkeypatch.setattr(pmweb, "fetch_product", items.get)
    result = pmweb.recheck([7, 8, 9])
    assert [p.product_id for p in result.ready] == [7]
    assert result.pending == (8,)


def test_empty_field_does_not_take_next_label() -> None:
    page = ('<h1 class="view">Club</h1><div>ราคา</div><div>รายละเอียดเพิ่มเติม</div>'
            '<div>line one</div><div>สินค้าเกี่ยวข้อง</div>')
    item = pmweb.parse_product(page, 5)
    assert item is not None and item.price == "" and item.details == ("line one",)


def test_download_rejects_non_image(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    item = pmweb.Product(1, "", "x", "", "", "", "", "", (), ("https://e.test/a.JPG",))
    monkeypatch.setattr(pmweb, "http_get", lambda _u: b"<html>error page</html>")
    with pytest.raises(pmweb.FetchError):
        pmweb.download_images(item, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_names_files_and_skips_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    item = pmweb.Product(7, "", "x", "", "", "", "", "", (), ("https://e.test/a.JPG", "https://e.test/b.png"))
    got: list[str] = []
    monkeypatch.setattr(pmweb, "http_get", lambda u: got.append(u) or b"\xff\xd8fake")
    monkeypatch.setattr(pmweb.time, "sleep", lambda _s: None)
    paths = pmweb.download_images(item, tmp_path)
    assert [p.name for p in paths] == ["7_01.jpg", "7_02.png"]
    pmweb.download_images(item, tmp_path)
    assert len(got) == 2  # second run downloads nothing
