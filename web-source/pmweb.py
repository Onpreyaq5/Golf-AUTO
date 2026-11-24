"""Read-only product source for pmgolfclub.com (replaces reading the LINE OpenChat).

Product ids are sequential and any product opens at /product/x/x/<id>, so new
products are found by walking ids upward from the last one seen. A missing id
still returns HTTP 200, just without a product name, so we check the name.

Stdlib only, so it runs in the bot's existing venv.

CLI:
  python pmweb.py fetch <id>                      -> product as JSON
  python pmweb.py scan <since_id> [--lookahead N] -> {ready, pending, last_id}
  python pmweb.py recheck <id> [<id> ...]         -> pending ids that became ready
Ready = not sold, price > 0฿ and has photos (0฿ means not ready for sale yet).
  python pmweb.py download <id> <out_dir>         -> save all full-size photos
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

BASE_URL = "https://www.pmgolfclub.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PremiumGolf-bot/1.0"
TIMEOUT_SEC = 30
RETRIES = 3
REQUEST_GAP_SEC = 1.5       # be gentle with our own server
DEFAULT_LOOKAHEAD = 15      # ids may have gaps (deleted / unpublished products)
MAX_SCAN_IDS = 50           # cap one scan so it never runs for many minutes

FIELD_LABELS = {
    "รหัสสินค้า": "sku",
    "หมวดหมู่": "category",
    "ยี่ห้อ": "brand",
    "สภาพสินค้า": "condition",
    "ราคา": "price",
}
DETAILS_LABEL = "รายละเอียดเพิ่มเติม"

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
NAME_RE = re.compile(r'<h1 class="view">(.*?)</h1>', re.S)
IMAGE_RE = re.compile(r'data-zoom-image="([^"]+)"')
BLOCK_END_RE = re.compile(r"<(br|/p|/div|/li|/h\d|/tr|/td)\b[^>]*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
# sale items show "ราคาพิเศษ" with the selling price and the struck-out old price
SALE_RE = re.compile(r'<span class="price_sale">\s*([\d,]+\s*฿)\s*</span>\s*'
                     r'(?:<span class="price_normal"[^>]*>\s*([\d,]+\s*฿)\s*</span>)?')
PRICE_TEXT_RE = re.compile(r"(\d[\d,]*)(?:\.\d+)?\s*฿?")
SOLD_MARK = "/image/new/sold_out.png"
RELATED_MARK = "สินค้าเกี่ยวข้อง"
PHP_ERROR_MARK = "PHP Error"
MAX_NAME_LEN = 300


@dataclass(frozen=True)
class Product:
    product_id: int
    url: str
    name: str
    price: str
    sku: str
    category: str
    brand: str
    condition: str
    details: tuple[str, ...]
    images: tuple[str, ...]
    old_price: str = ""     # struck-out price when the item is on sale
    sold: bool = False

    @property
    def price_baht(self) -> int:
        """'2,500฿' -> 2500; anything but one clear amount -> 0 (never guess)."""
        match = PRICE_TEXT_RE.fullmatch(self.price.strip())
        return int(match.group(1).replace(",", "")) if match else 0

    @property
    def is_ready(self) -> bool:
        """Ready to post: not sold, has a real price and at least one photo.
        A price of 0฿ / no price means the product is not ready for sale yet."""
        return not self.sold and self.price_baht > 0 and bool(self.images)


@dataclass(frozen=True)
class ScanResult:
    ready: tuple[Product, ...]      # post these
    pending: tuple[int, ...]        # exist but not ready yet: recheck later
    last_id: int                    # next scan continues after this id
    sold: tuple[int, ...] = ()      # already sold: nothing left to do


class FetchError(RuntimeError):
    """Network/HTTP problem after all retries (not 'product does not exist')."""


def product_url(product_id: int) -> str:
    return f"{BASE_URL}/product/x/x/{product_id}"


def _visible_lines(fragment: str) -> list[str]:
    text = SCRIPT_RE.sub("", fragment)
    text = BLOCK_END_RE.sub("\n", text)
    text = html.unescape(TAG_RE.sub("", text))
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.splitlines())
    return [line for line in lines if line]


def parse_product(page: str, product_id: int) -> Product | None:
    """Return the product on this page, or None when the id has no product."""
    page = COMMENT_RE.sub("", page)  # some galleries are left commented out
    name_match = NAME_RE.search(page)
    name = html.unescape(TAG_RE.sub("", name_match.group(1))).strip() if name_match else ""
    # A missing id renders a PHP error inside the <h1> instead of a name.
    if not name or PHP_ERROR_MARK in name or len(name) > MAX_NAME_LEN:
        return None

    # The product block ends at the visible "related products" heading.
    end = page.find(RELATED_MARK, name_match.end())
    main = page[name_match.end(): end if end != -1 else len(page)]

    images = tuple(dict.fromkeys(IMAGE_RE.findall(main)))  # unique, keep order

    lines = _visible_lines(main)
    fields = {key: "" for key in FIELD_LABELS.values()}
    details: list[str] = []
    for i, line in enumerate(lines):
        key = FIELD_LABELS.get(line)
        if key and not fields[key] and i + 1 < len(lines):
            value = lines[i + 1]
            # an empty field shows the next label instead of a value
            if value not in FIELD_LABELS and value != DETAILS_LABEL:
                fields[key] = value
        if line == DETAILS_LABEL:
            details = lines[i + 1:]
            break

    old_price = ""
    sale = SALE_RE.search(main)
    if sale:
        fields["price"], old_price = sale.group(1), sale.group(2) or ""

    return Product(
        product_id=product_id,
        url=product_url(product_id),
        name=name,
        old_price=old_price,
        sold=SOLD_MARK in main,
        details=tuple(details),
        images=images,
        **fields,
    )


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                raise FetchError(f"HTTP {exc.code} for {url}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(2 ** attempt * 5)
    raise FetchError(f"giving up on {url}: {last_error!r}")


def fetch_product(product_id: int) -> Product | None:
    page = http_get(product_url(product_id)).decode("utf-8", errors="replace")
    return parse_product(page, product_id)


def _result(products: list[Product], last_id: int) -> ScanResult:
    return ScanResult(
        ready=tuple(p for p in products if p.is_ready),
        pending=tuple(p.product_id for p in products if not p.is_ready and not p.sold),
        last_id=last_id,
        sold=tuple(p.product_id for p in products if p.sold),
    )


def scan_new(since_id: int, lookahead: int = DEFAULT_LOOKAHEAD, max_ids: int = MAX_SCAN_IDS) -> ScanResult:
    """Products with id > since_id. Stops after `lookahead` empty ids in a row,
    or after checking `max_ids` ids. Not-ready products come back in `pending`
    so the caller can recheck them; `last_id` is the highest id that exists."""
    found: list[Product] = []
    empty_run = 0
    product_id = since_id
    last_id = since_id
    while empty_run < lookahead and product_id - since_id < max_ids:
        product_id += 1
        product = fetch_product(product_id)
        if product is None:
            empty_run += 1
        else:
            empty_run = 0
            last_id = product_id
            found.append(product)
        time.sleep(REQUEST_GAP_SEC)
    return _result(found, last_id)


def recheck(product_ids: list[int]) -> ScanResult:
    """Re-fetch pending ids. Deleted and sold ones are dropped; still-not-ready stay pending."""
    found: list[Product] = []
    for product_id in product_ids:
        product = fetch_product(product_id)
        if product is not None:
            found.append(product)
        time.sleep(REQUEST_GAP_SEC)
    return _result(found, max(product_ids, default=0))


def download_images(product: Product, out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Save photos as <id>_<n>.<ext>; skip files already downloaded."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[pathlib.Path] = []
    for n, url in enumerate(product.images, start=1):
        ext = pathlib.Path(url.split("?")[0]).suffix.lower() or ".jpg"
        target = out_dir / f"{product.product_id}_{n:02d}{ext}"
        if not target.exists():
            data = http_get(url)
            if not data.startswith((b"\xff\xd8", b"\x89PNG", b"RIFF")):
                raise FetchError(f"not an image: {url}")
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
            time.sleep(REQUEST_GAP_SEC)
        saved.append(target)
    return saved


def _to_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("product_id", type=int)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("since_id", type=int)
    p_scan.add_argument("--lookahead", type=int, default=DEFAULT_LOOKAHEAD)
    p_re = sub.add_parser("recheck")
    p_re.add_argument("ids", type=int, nargs="+")
    p_dl = sub.add_parser("download")
    p_dl.add_argument("product_id", type=int)
    p_dl.add_argument("out_dir", type=pathlib.Path)
    args = parser.parse_args(argv)

    try:
        if args.cmd == "fetch":
            product = fetch_product(args.product_id)
            print(_to_json(asdict(product) if product else None))
            return 0 if product else 3
        if args.cmd in ("scan", "recheck"):
            result = scan_new(args.since_id, args.lookahead) if args.cmd == "scan" else recheck(args.ids)
            print(_to_json({
                "ready": [asdict(p) for p in result.ready],
                "pending": list(result.pending),
                "sold": list(result.sold),
                "last_id": result.last_id,
            }))
            return 0
        product = fetch_product(args.product_id)
        if product is None:
            print(f"no product {args.product_id}", file=sys.stderr)
            return 3
        for path in download_images(product, args.out_dir):
            print(path)
        return 0
    except FetchError as exc:
        print(f"fetch error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
