"""
app.py — WhatsApp webhook bot for Prepaid Label Automation (Render-hosted)
==========================================================================
Flow per session:
  1. User sends "start"  → bot asks for Biller ID (1/2/3)
  2. User replies 1/2/3  → biller confirmed, silent recording begins
  3. User forwards customer address blocks (each as one WhatsApp message)
  4. User sends "stop"   → bot generates DOCX→PDF and sends it back

Commands while recording:
  list   → show current address list
  undo   → remove last address
  stop   → finalize and send PDF
"""

import os
import sys
import copy
import logging
import requests
import subprocess
from flask import Flask, request, jsonify
from address_printer import (
    parse_address_block,
    create_address_document_multipage,
    BLOCKS_PER_PAGE,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Environment variables (set in Render dashboard)
# ---------------------------------------------------------------------------
VERIFY_TOKEN   = os.environ.get("VERIFY_TOKEN",   "cream_bot_123")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")

BILLER_OPTIONS = {
    "1": "1260357626",
    "2": "1264602129",
    "3": "1624036027",
}

# In-memory sessions keyed by phone number
# Structure: { phone: { biller_id, addresses, is_recording, is_choosing_biller } }
sessions: dict = {}


# ---------------------------------------------------------------------------
# WhatsApp API helpers
# ---------------------------------------------------------------------------

def send_whatsapp_message(to_number: str, text: str) -> None:
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    res = requests.post(url, headers=headers, json=data)
    if res.status_code != 200:
        logger.error(f"send_whatsapp_message error: {res.text}")


def send_whatsapp_document(
    to_number: str, document_path: str, filename: str, mime_type: str = "application/pdf"
) -> bool:
    """Upload a file to Meta then send as document message."""
    upload_url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    try:
        with open(document_path, "rb") as f:
            files = {
                "file": (filename, f, mime_type),
                "type": (None, mime_type),
                "messaging_product": (None, "whatsapp"),
            }
            upload_res = requests.post(upload_url, headers=headers, files=files)
    except Exception as e:
        logger.error(f"File open error: {e}")
        return False

    media_id = upload_res.json().get("id")
    if not media_id:
        logger.error(f"Media upload failed: {upload_res.text}")
        send_whatsapp_message(to_number, "Error uploading document to WhatsApp.")
        return False

    msg_url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    msg_headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "document",
        "document": {"id": media_id, "filename": filename},
    }
    res = requests.post(msg_url, headers=msg_headers, json=data)
    if res.status_code != 200:
        logger.error(f"send_whatsapp_document error: {res.text}")
        return False
    return True


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "cream-prepaid-bot"}), 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403
    return "Bad Request", 400


@app.route("/webhook", methods=["POST"])
def webhook_event():
    body = request.get_json()
    logger.info("Webhook POST received")

    if not body:
        return "OK", 200

    try:
        if body.get("object"):
            entry   = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value   = changes.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                if msg.get("type") == "text":
                    phone    = msg["from"]
                    msg_text = msg["text"]["body"].strip()
                    logger.info(f"Message from {phone}: {msg_text[:80]}")
                    handle_incoming_message(phone, msg_text)

            return "EVENT_RECEIVED", 200
        return "Not Found", 404
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return "OK", 200


# ---------------------------------------------------------------------------
# Session state machine
# ---------------------------------------------------------------------------

def get_session(phone: str) -> dict:
    if phone not in sessions:
        sessions[phone] = {
            "biller_id":        "1260357626",
            "addresses":        [],
            "is_recording":     False,
            "is_choosing_biller": False,
        }
    return sessions[phone]


def handle_incoming_message(phone: str, msg_text: str) -> None:
    lower = msg_text.lower().strip()
    session = get_session(phone)

    # ── "start" command ──────────────────────────────────────────────────────
    if lower == "start":
        session["addresses"]          = []
        session["is_recording"]       = False
        session["is_choosing_biller"] = True

        send_whatsapp_message(
            phone,
            "Started new batch!\n\n"
            "Choose a Biller ID:\n"
            "1 - 1260357626\n"
            "2 - 1264602129\n"
            "3 - 1624036027\n\n"
            "Reply with 1, 2, or 3.",
        )
        return

    # ── Biller selection ─────────────────────────────────────────────────────
    if session["is_choosing_biller"]:
        if msg_text.strip() in BILLER_OPTIONS:
            session["biller_id"]          = BILLER_OPTIONS[msg_text.strip()]
            session["is_choosing_biller"] = False
            session["is_recording"]       = True
            send_whatsapp_message(
                phone,
                f"Biller ID set to {session['biller_id']}.\n\n"
                "Paste addresses now (one per message). I'll be silent.\n"
                "Type 'stop' when done.",
            )
        else:
            send_whatsapp_message(phone, "Invalid option. Reply with 1, 2, or 3.")
        return

    # ── "stop" command ───────────────────────────────────────────────────────
    if lower == "stop":
        if not session["is_recording"]:
            send_whatsapp_message(phone, "You are not recording. Type 'start' to begin.")
            return

        if not session["addresses"]:
            send_whatsapp_message(phone, "No addresses were sent. Batch canceled.")
            session["is_recording"] = False
            return

        count = len(session["addresses"])
        send_whatsapp_message(phone, f"Generating label sheet with {count} address(es)...")

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # Sequential naming: prepaid1.pdf, prepaid2.pdf, …
        counter_file = os.path.join(output_dir, "batch_counter.txt")
        batch_num = 1
        if os.path.exists(counter_file):
            try:
                batch_num = int(open(counter_file).read().strip()) + 1
            except (ValueError, OSError):
                batch_num = 1
        with open(counter_file, "w") as cf:
            cf.write(str(batch_num))

        docx_filename = f"prepaid{batch_num}.docx"
        pdf_filename  = f"prepaid{batch_num}.pdf"
        docx_path     = os.path.join(output_dir, docx_filename)
        pdf_path      = os.path.join(output_dir, pdf_filename)

        # 1. Render DOCX using docxtpl (pixel-perfect template)
        try:
            create_address_document_multipage(
                session["addresses"], session["biller_id"], docx_path
            )
        except Exception as e:
            logger.error(f"DOCX generation error: {e}", exc_info=True)
            send_whatsapp_message(phone, f"Error generating document: {e}")
            return

        # 2. Convert to PDF via LibreOffice (Render/Docker) or docx2pdf (Windows)
        pdf_ok = _convert_to_pdf(docx_path, pdf_path)

        if pdf_ok and os.path.exists(pdf_path):
            send_path     = pdf_path
            send_filename = pdf_filename
            send_mime     = "application/pdf"
        else:
            # Fallback: send the DOCX
            logger.warning("PDF conversion failed — sending DOCX instead")
            send_path     = docx_path
            send_filename = docx_filename
            send_mime     = (
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            )

        success = send_whatsapp_document(phone, send_path, send_filename, send_mime)
        if not success:
            send_whatsapp_message(phone, "Could not send document. Check server logs.")

        session["is_recording"] = False
        session["addresses"]    = []
        return

    # ── "list" command ───────────────────────────────────────────────────────
    if lower == "list":
        addrs = session["addresses"]
        if not addrs:
            send_whatsapp_message(phone, "List is empty.")
        else:
            lines = [f"Current list ({len(addrs)} addresses):"]
            for i, a in enumerate(addrs, 1):
                lines.append(f"{i}. {a['name'] or 'No Name'} — Pin: {a['pincode'] or '?'}")
            send_whatsapp_message(phone, "\n".join(lines))
        return

    # ── "undo" command ───────────────────────────────────────────────────────
    if lower == "undo":
        if session["addresses"]:
            removed = session["addresses"].pop()
            send_whatsapp_message(phone, f"Removed: {removed['name'] or '(no name)'}")
        else:
            send_whatsapp_message(phone, "Nothing to undo.")
        return

    # ── Recording: parse as address block ────────────────────────────────────
    if session["is_recording"]:
        parsed = parse_address_block(msg_text)
        session["addresses"].append(parsed)
        # Stay silent during recording — WhatsApp chat stays clean
        return

    # Not in any active session — prompt user
    # (ignore silently or give a hint)


def _convert_to_pdf(docx_path: str, pdf_path: str) -> bool:
    """Try LibreOffice first (Render/Linux), then docx2pdf (Windows/macOS)."""
    outdir = os.path.dirname(os.path.abspath(docx_path)) or "."

    # --- LibreOffice (works on Render/Docker) ---
    try:
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and os.path.exists(pdf_path):
            return True
        logger.warning(f"LibreOffice failed: {result.stderr}")
    except FileNotFoundError:
        logger.info("LibreOffice not found — trying docx2pdf")
    except Exception as e:
        logger.warning(f"LibreOffice error: {e}")

    # --- docx2pdf (Windows / macOS with MS Word) ---
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    except Exception as e:
        logger.warning(f"docx2pdf failed: {e}")

    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
