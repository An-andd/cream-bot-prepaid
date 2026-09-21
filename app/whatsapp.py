"""Thin WhatsApp Cloud API client (text + document sending)."""
from __future__ import annotations

import logging
import os

import requests

from . import config

log = logging.getLogger(__name__)
TIMEOUT = 60


def _base() -> str:
    return f"https://graph.facebook.com/{config.WA_API_VERSION}/{config.WA_PHONE_NUMBER_ID}"


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.WA_TOKEN}"}


def send_text(to: str, body: str) -> dict:
    if not config.WA_TOKEN or not config.WA_PHONE_NUMBER_ID:
        log.warning("WhatsApp not configured; would send to %s: %s", to, body[:80])
        return {}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4000]},
    }
    r = requests.post(f"{_base()}/messages", json=payload,
                      headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        log.error("send_text failed %s %s", r.status_code, r.text)
    return r.json() if r.content else {}


def upload_media(path: str, mime: str) -> str | None:
    with open(path, "rb") as fh:
        files = {
            "file": (os.path.basename(path), fh, mime),
            "messaging_product": (None, "whatsapp"),
            "type": (None, mime),
        }
        r = requests.post(f"{_base()}/media", files=files,
                          headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        log.error("upload_media failed %s %s", r.status_code, r.text)
        return None
    return r.json().get("id")


def send_document(to: str, path: str, caption: str = "",
                  mime: str = "application/pdf") -> bool:
    if not config.WA_TOKEN or not config.WA_PHONE_NUMBER_ID:
        log.warning("WhatsApp not configured; document left at %s", path)
        return False
    media_id = upload_media(path, mime)
    if not media_id:
        send_text(to, "Labels were generated but the upload to WhatsApp failed. "
                      "Try 'stop' again in a moment.")
        return False
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": os.path.basename(path),
            "caption": caption[:1000],
        },
    }
    r = requests.post(f"{_base()}/messages", json=payload,
                      headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        log.error("send_document failed %s %s", r.status_code, r.text)
        return False
    return True


def mark_read(message_id: str) -> None:
    if not (config.WA_TOKEN and config.WA_PHONE_NUMBER_ID and message_id):
        return
    try:
        requests.post(
            f"{_base()}/messages",
            json={"messaging_product": "whatsapp", "status": "read",
                  "message_id": message_id},
            headers=_headers(), timeout=15,
        )
    except requests.RequestException:  # pragma: no cover - best effort
        pass
