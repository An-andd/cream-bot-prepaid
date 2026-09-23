"""Central configuration. Everything comes from environment variables."""
from __future__ import annotations

import json
import os


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ---------------------------------------------------------------- sender block
SENDER_NAME = _env("SENDER_NAME", "CREAM X EMIRATES")
# Use "|" or "\n" to separate address lines.
SENDER_ADDRESS = _env("SENDER_ADDRESS", "PUTHUPALLY, KTM")
SENDER_PIN = _env("SENDER_PIN", "686011")
SENDER_PHONE = _env("SENDER_PHONE", "8129770502")


def sender_address_lines() -> list[str]:
    raw = SENDER_ADDRESS.replace("|", "\n")
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


# ---------------------------------------------------------------- biller ids
# BILLERS is a JSON object: {"option1": {"label": "Main", "id": "1260357626"}, ...}
_DEFAULT_BILLERS = {
    "option1": {"label": "default", "id": "1260357626"},
    "option2": {"label": "alternative 1", "id": "1264602129"},
    "option3": {"label": "alternative 2", "id": "1624036027"},
}


def billers() -> dict[str, dict[str, str]]:
    raw = _env("BILLERS")
    if not raw:
        # fall back to BILLER_ID_1..3 / BILLER_ID
        out = {}
        for i in (1, 2, 3):
            bid = _env(f"BILLER_ID_{i}")
            if bid:
                out[f"option{i}"] = {
                    "label": _env(f"BILLER_LABEL_{i}", f"Biller {i}"),
                    "id": bid,
                }
        single = _env("BILLER_ID")
        if single and not out:
            out["option1"] = {"label": _env("BILLER_LABEL_1", "Default"), "id": single}
        return out or dict(_DEFAULT_BILLERS)
    try:
        data = json.loads(raw)
        return {str(k).lower(): v for k, v in data.items()}
    except json.JSONDecodeError:
        return dict(_DEFAULT_BILLERS)


# ---------------------------------------------------------------- label layout
PAGE_SIZE = _env("PAGE_SIZE", "A4").upper()          # A4 | LETTER
LABELS_PER_ROW = int(_env("LABELS_PER_ROW", "2"))
LABEL_ROWS = int(_env("LABEL_ROWS", "3"))
LABELS_PER_PAGE = LABELS_PER_ROW * LABEL_ROWS         # 6
PAGE_MARGIN_MM = float(_env("PAGE_MARGIN_MM", "8"))
LABEL_PADDING_MM = float(_env("LABEL_PADDING_MM", "5"))
BASE_FONT_SIZE = float(_env("BASE_FONT_SIZE", "10"))
MIN_FONT_SIZE = float(_env("MIN_FONT_SIZE", "6.0"))
FONT_NAME = _env("FONT_NAME", "Helvetica")
FONT_NAME_BOLD = _env("FONT_NAME_BOLD", "Helvetica-Bold")
BORDER_WIDTH = float(_env("BORDER_WIDTH", "0.8"))
DRAW_BORDER = _env("DRAW_BORDER", "true").lower() != "false"
# Where the sender block sits inside each label box.
#   right = its own column on the right (matches the printed labels)
#   below = stacked under the customer block (old behaviour)
FROM_BLOCK_POSITION = _env("FROM_BLOCK_POSITION", "right").lower()
# Share of the label width given to the customer block when FROM is on the right.
TO_COLUMN_RATIO = float(_env("TO_COLUMN_RATIO", "0.58"))
# Vertical placement of the right-hand FROM block: top | middle | bottom
FROM_VALIGN = _env("FROM_VALIGN", "bottom").lower()
COLUMN_GAP_MM = float(_env("COLUMN_GAP_MM", "3"))
# Keep the exact field wording used on the existing labels.
PHONE_LABEL = _env("PHONE_LABEL", "Phone Number")

# ---------------------------------------------------------------- products
# Multi-word product names that should still be recognised without a "Product:"
# label, comma separated. Single-token codes like 1cxe are always recognised.
KNOWN_PRODUCTS = [
    p.strip().lower() for p in _env("KNOWN_PRODUCTS", "cxe").split(",") if p.strip()
]
NOTE_WORDS = [
    w.strip().lower()
    for w in _env(
        "NOTE_WORDS",
        "return,forgot,mistake,dtdc,urgent,replacement,exchange,repeat,free,gift,cancel,resend",
    ).split(",")
    if w.strip()
]

# ---------------------------------------------------------------- whatsapp
WA_TOKEN = _env("WHATSAPP_TOKEN")
WA_PHONE_NUMBER_ID = _env("WHATSAPP_PHONE_NUMBER_ID")
WA_VERIFY_TOKEN = _env("WHATSAPP_VERIFY_TOKEN", "cream-verify")
WA_API_VERSION = _env("WHATSAPP_API_VERSION", "v22.0")
# Only these WhatsApp numbers may drive the bot (comma separated, digits only).
ALLOWED_SENDERS = [
    "".join(ch for ch in n if ch.isdigit())
    for n in _env("ALLOWED_SENDERS").split(",")
    if n.strip()
]

# ---------------------------------------------------------------- woocommerce
WOO_URL = _env("WOO_URL").rstrip("/")
WOO_KEY = _env("WOO_CONSUMER_KEY")
WOO_SECRET = _env("WOO_CONSUMER_SECRET")
WOO_PAID_STATUSES = [
    s.strip() for s in _env("WOO_PAID_STATUSES", "processing,completed").split(",") if s.strip()
]
# Any payment method containing one of these is treated as COD (excluded).
WOO_COD_METHODS = [
    s.strip().lower() for s in _env("WOO_COD_METHODS", "cod,cash on delivery").split(",") if s.strip()
]

# ---------------------------------------------------------------- woocommerce
# ---------------------------------------------------------------- telegram

TELEGRAM_TOKEN = _env("TELEGRAM_TOKEN")

TELEGRAM_WEBHOOK_SECRET = _env(
    "TELEGRAM_WEBHOOK_SECRET",
    "cream-prepaid-telegram-secret"
)

TELEGRAM_ALLOWED_CHAT_IDS = [
    x.strip()
    for x in _env("TELEGRAM_ALLOWED_CHAT_IDS").split(",")
    if x.strip()
]
# ---------------------------------------------------------------- storage
DB_PATH = _env("DB_PATH", "/tmp/cream_prepaid.sqlite3")
OUTPUT_DIR = _env("OUTPUT_DIR", "/tmp/cream_labels")
OUTPUT_FORMAT = _env("OUTPUT_FORMAT", "pdf").lower()   # pdf | docx | both
DOCX_TEMPLATE = _env("DOCX_TEMPLATE", "")              # optional .docx master
