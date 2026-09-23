"""Telegram Bot API transport for the prepaid label bot."""
from __future__ import annotations

import logging
import os

import requests

from . import config

log = logging.getLogger(__name__)

TIMEOUT = 60


def _base() -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"


def send_text(chat_id: str, body: str) -> dict:
    if not config.TELEGRAM_TOKEN:
        log.warning("Telegram not configured; would send to %s: %s", chat_id, body[:80])
        return {}

    payload = {
        "chat_id": chat_id,
        "text": body[:4096],
    }

    r = requests.post(
        f"{_base()}/sendMessage",
        json=payload,
        timeout=TIMEOUT,
    )

    if r.status_code >= 400:
        log.error("Telegram send_text failed: %s %s", r.status_code, r.text)

    return r.json() if r.content else {}


def send_document(
    chat_id: str,
    path: str,
    caption: str = "",
    mime: str = "application/pdf",
) -> bool:

    if not config.TELEGRAM_TOKEN:
        log.warning("Telegram not configured; document left at %s", path)
        return False

    try:
        with open(path, "rb") as fh:
            files = {
                "document": (
                    os.path.basename(path),
                    fh,
                    mime,
                )
            }

            data = {
                "chat_id": chat_id,
                "caption": caption[:1024],
            }

            r = requests.post(
                f"{_base()}/sendDocument",
                data=data,
                files=files,
                timeout=TIMEOUT,
            )

        if r.status_code >= 400:
            log.error(
                "Telegram send_document failed: %s %s",
                r.status_code,
                r.text,
            )
            return False

        return True

    except Exception:
        log.exception("Telegram document upload failed")
        return False


def mark_read(message_id: str) -> None:
    # Telegram does not need the WhatsApp-style mark-as-read API.
    return