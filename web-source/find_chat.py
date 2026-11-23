"""Find the Telegram group id: send /start@PNGolfbot in the group first, then run this.
Saves the id of the only group seen (or lists them if several) into telegram.json."""
from __future__ import annotations

import json
import sys
import urllib.request

import notify


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = notify.load_config()
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/getUpdates"
    with urllib.request.urlopen(url, timeout=notify.TIMEOUT_SEC) as resp:
        updates = json.load(resp)["result"]
    groups: dict[str, str] = {}
    for update in updates:
        for key in ("message", "my_chat_member", "channel_post"):
            chat = update.get(key, {}).get("chat")
            if chat and chat.get("type") in ("group", "supergroup"):
                groups[str(chat["id"])] = chat.get("title", "")
    if not groups:
        print("ยังไม่เจอกลุ่ม: พิมพ์ /start@PNGolfbot ในกลุ่มก่อน แล้วรันใหม่")
        return 1
    if len(groups) > 1:
        print("เจอหลายกลุ่ม ใส่ chat_id เองใน", notify.config_path(), groups)
        return 1
    chat_id, title = next(iter(groups.items()))
    data = json.loads(notify.config_path().read_text(encoding="utf-8"))
    data["chat_id"] = chat_id
    notify.config_path().write_text(json.dumps(data), encoding="utf-8")
    print(f"บันทึกกลุ่ม {title} ({chat_id}) แล้ว")
    return 0


if __name__ == "__main__":
    sys.exit(main())
