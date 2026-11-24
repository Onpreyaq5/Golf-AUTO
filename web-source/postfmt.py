"""Build one shop post in exactly the format used in the LINE OpenChat.

LINE decides what is posted and supplies the product link (the web page does not
reveal its own category link). The web supplies the photo: LINE shows one photo,
which is the first photo on the product page. A post that fails the cross-check
is never built.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import crosscheck
import pmweb

CONTACT_LINK = "https://lin.ee/wpRQTtx"
# LINE shows this on one line; the bot's manual splits it in two (shop to confirm)
CONTACT_TEXT = "สอบถาม สั่งซื้อ คลิ้กด้านล่างตรงนี้ได้เลยครับ"
CONTACT_RE = re.compile(r"https?://lin\.ee/[A-Za-z0-9]+")


class NotPostable(ValueError):
    """The LINE post does not match the web, so it must not be posted."""


@dataclass(frozen=True)
class Post:
    product_id: int
    text: str
    photos: tuple[str, ...]


def build(line: crosscheck.LinePost, product: pmweb.Product | None) -> Post:
    item = crosscheck.compare(line, product)
    if item.status != crosscheck.OK or product is None or item.product_id is None:
        raise NotPostable(f"{item.status}: {'; '.join(item.problems)}")
    contacts = set(CONTACT_RE.findall(line.text))
    if contacts != {CONTACT_LINK}:
        raise NotPostable(f"ลิงก์ติดต่อไม่ตรงกับของร้าน: {sorted(contacts) or 'ไม่มี'}")
    text = "\n".join((
        line.name, "",
        f"ราคา {line.price_baht:,} บาท", "",
        "รายละเอียดเพิ่มเติม", line.link, "",
        CONTACT_TEXT, CONTACT_LINK,
    ))
    return Post(item.product_id, text, product.images[:1])
