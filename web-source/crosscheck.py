"""Cross-check LINE OpenChat posts against pmgolfclub.com, product by product.

For every LINE post we find its product id (from the pmgolfclub.com link in the
text) and compare with the live web page: product exists, is ready (price > 0),
same name, same price. LINE shows one photo while the web has many, so the photo
count only has to be possible (at least 1, not more than the web). Announcements
are skipped. Pass web_ready_ids to also list products never seen in LINE.

LINE posts come from either:
  --line-json <file>  list of {"text": ..., "photo_count": n, "seen_at": ...}
  --bot-db <pmbot.db> the bot's database, opened READ-ONLY (columns auto-detected)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import asdict, dataclass

import pmweb

# the id ends the link; [^\s/] segments keep working when LINE drops line breaks
LINK_RE = re.compile(r"https?://(?:www\.)?pmgolfclub\.com/product/[\w-]+/[\w-]+/(\d{5,})", re.ASCII)
PRICE_RE = re.compile(r"ราคา\s*:?\s*([\d,]+)")
TEXT_COLUMNS = ("text", "raw_text", "message", "body", "line_text", "content")
PHOTO_COLUMNS = ("photo_count", "n_photos", "photos", "image_count", "num_photos")
SEEN_COLUMNS = ("seen_at", "line_time", "created_at", "first_seen")

OK = "OK"
MISMATCH = "MISMATCH"
NOT_ON_WEB = "NOT_ON_WEB"
NOT_READY_ON_WEB = "NOT_READY_ON_WEB"
NO_LINK = "NO_LINK"
WEB_ONLY = "WEB_ONLY"
NOT_PRODUCT = "NOT_PRODUCT"  # announcement, sticker, chat: nothing to check


@dataclass(frozen=True)
class LinePost:
    text: str
    photo_count: int | None = None
    seen_at: str = ""

    @property
    def product_id(self) -> int | None:
        match = LINK_RE.search(self.text)
        return int(match.group(1)) if match else None

    @property
    def link(self) -> str:
        match = LINK_RE.search(self.text)
        return match.group(0) if match else ""

    @property
    def name(self) -> str:
        """First line, or everything before the price when line breaks were dropped."""
        match = PRICE_RE.search(self.text)
        head = self.text[:match.start()] if match else self.text
        return next((line.strip() for line in head.splitlines() if line.strip()), "")

    @property
    def price_baht(self) -> int:
        match = PRICE_RE.search(self.text)
        return int(match.group(1).replace(",", "")) if match else 0


@dataclass(frozen=True)
class CheckItem:
    product_id: int | None
    status: str
    problems: tuple[str, ...]
    line_name: str = ""

    @property
    def is_problem(self) -> bool:
        return self.status not in (OK, NOT_PRODUCT)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def compare(post: LinePost, product: pmweb.Product | None) -> CheckItem:
    pid = post.product_id
    if pid is None and not post.price_baht:
        return CheckItem(None, NOT_PRODUCT, (), post.name)
    if pid is None:
        return CheckItem(None, NO_LINK, ("โพสต์ใน LINE ไม่มีลิงก์ pmgolfclub.com",), post.name)
    if product is None:
        return CheckItem(pid, NOT_ON_WEB, ("ไม่มีสินค้านี้บนเว็บ (ถูกลบ หรือเลขในลิงก์ผิด)",), post.name)
    if not product.is_ready:
        return CheckItem(pid, NOT_READY_ON_WEB, (f"บนเว็บยังไม่พร้อมขาย ราคา {product.price or 'ว่าง'}",), post.name)

    problems: list[str] = []
    # exact (except spacing and case): one letter can be a different club, e.g. Flex S / SR
    if _norm(post.name) != _norm(product.name):
        problems.append(f"ชื่อไม่ตรง: LINE '{post.name}' / เว็บ '{product.name}'")
    if post.price_baht and post.price_baht != product.price_baht:
        problems.append(f"ราคาไม่ตรง: LINE {post.price_baht:,} / เว็บ {product.price_baht:,}")
    if not post.price_baht:
        problems.append("โพสต์ใน LINE ไม่มีราคา")
    if post.photo_count is not None and post.photo_count < 1:
        problems.append("โพสต์ใน LINE ไม่มีรูป")
    elif post.photo_count is not None and post.photo_count > len(product.images):
        problems.append(f"รูปใน LINE ({post.photo_count}) มากกว่าบนเว็บ ({len(product.images)})")
    return CheckItem(pid, MISMATCH if problems else OK, tuple(problems), post.name)


def crosscheck(
    posts: Iterable[LinePost],
    fetch: Callable[[int], pmweb.Product | None] = pmweb.fetch_product,
    web_ready_ids: Iterable[int] = (),
) -> list[CheckItem]:
    items: list[CheckItem] = []
    seen: set[int] = set()
    cache: dict[int, pmweb.Product | None] = {}
    for post in posts:
        pid = post.product_id
        if pid is not None and pid not in cache:
            cache[pid] = fetch(pid)
        items.append(compare(post, cache.get(pid) if pid is not None else None))
        if pid is not None:
            seen.add(pid)
    for pid in sorted(set(web_ready_ids) - seen):
        items.append(CheckItem(pid, WEB_ONLY, ("พร้อมขายบนเว็บแล้ว แต่ไม่เจอโพสต์ใน LINE",)))
    return items


def _pick(columns: list[str], wanted: tuple[str, ...]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    return next((lowered[w] for w in wanted if w in lowered), None)


def posts_from_bot_db(db_path: pathlib.Path, limit: int = 500) -> list[LinePost]:
    """Read LINE posts from the bot's database without knowing its exact schema."""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as con:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
            text_col = _pick(cols, TEXT_COLUMNS)
            if not text_col:
                continue
            photo_col, seen_col = _pick(cols, PHOTO_COLUMNS), _pick(cols, SEEN_COLUMNS)
            select = ", ".join(f'"{c}"' if c else "NULL" for c in (text_col, photo_col, seen_col))
            rows = con.execute(f'SELECT {select} FROM "{table}" ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
            posts = [LinePost(str(t or ""), int(p) if isinstance(p, int) else None, str(s or ""))
                     for t, p, s in rows]
            if any(p.product_id for p in posts):
                return list(reversed(posts))
    return []


def summarize(items: list[CheckItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--line-json", type=pathlib.Path)
    src.add_argument("--bot-db", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.line_json:
        raw = json.loads(args.line_json.read_text(encoding="utf-8"))
        posts = [LinePost(r["text"], r.get("photo_count"), r.get("seen_at", "")) for r in raw]
    else:
        posts = posts_from_bot_db(args.bot_db)
    items = crosscheck(posts)
    print(json.dumps({"summary": summarize(items), "items": [asdict(i) for i in items]},
                     ensure_ascii=False, indent=2))
    return 1 if any(i.is_problem for i in items) else 0


if __name__ == "__main__":
    sys.exit(main())
