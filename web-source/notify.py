"""Telegram sender. Secrets live outside the repo in %USERPROFILE%\\.pmgolf\\telegram.json:
{"bot_token": "...", "chat_id": "..."}  (override the path with env PMGOLF_TELEGRAM_FILE)."""
from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

MAX_MESSAGE_CHARS = 3900  # Telegram limit is 4096
TIMEOUT_SEC = 20


def config_path() -> pathlib.Path:
    default = pathlib.Path.home() / ".pmgolf" / "telegram.json"
    return pathlib.Path(os.environ.get("PMGOLF_TELEGRAM_FILE", default))


def load_config() -> dict[str, str]:
    data = json.loads(config_path().read_text(encoding="utf-8"))
    token, chat = str(data.get("bot_token", "")), str(data.get("chat_id", ""))
    if not token:
        raise ValueError(f"bot_token missing in {config_path()}")
    return {"bot_token": token, "chat_id": chat}


def split_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split on line boundaries so each part fits in one Telegram message."""
    parts: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:  # a single very long line: cut it hard
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        if current and len(current) + len(line) > limit:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    return parts


def send(text: str) -> None:
    cfg = load_config()
    if not cfg["chat_id"]:
        raise ValueError(f"chat_id missing in {config_path()} - run: python find_chat.py")
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    for part in split_message(text):
        body = urllib.parse.urlencode({"chat_id": cfg["chat_id"], "text": part,
                                       "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen(url, data=body, timeout=TIMEOUT_SEC) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            # never echo the URL: it contains the bot token
            raise RuntimeError(f"Telegram HTTP {exc.code}: {exc.read()[:200]!r}") from None
