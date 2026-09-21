"""Flask app: WhatsApp Cloud API webhook + a couple of helper endpoints."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request, send_file

from . import bot, config, store, woo
from .labels import render_pdf
from .parsing import parse_orders

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cream")

app = Flask(__name__)
store.init_db()


@app.get("/")
def health():
    return jsonify(
        status="ok",
        service="cream-prepaid-labels",
        whatsapp_configured=bool(config.WA_TOKEN and config.WA_PHONE_NUMBER_ID),
        woocommerce_configured=woo.configured(),
        billers=sorted(config.billers().keys()),
    )


@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and token == config.WA_VERIFY_TOKEN:
        return challenge, 200
    return "forbidden", 403


@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}
    try:
        _process(data)
    except Exception:  # noqa: BLE001 - never let Meta retry-storm us
        log.exception("webhook processing failed")
    return jsonify(status="received"), 200


def _process(data: dict) -> None:
    for entry in data.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                _handle_one(message)


def _handle_one(message: dict) -> None:
    msg_id = message.get("id", "")
    wa_id = message.get("from", "")
    if not wa_id or store.already_seen(msg_id):
        return
    if config.ALLOWED_SENDERS and wa_id not in config.ALLOWED_SENDERS:
        log.warning("ignoring message from %s (not allow-listed)", wa_id)
        return

    msg_type = message.get("type")
    if msg_type == "text":
        text = (message.get("text") or {}).get("body", "")
    elif msg_type == "interactive":
        inter = message.get("interactive") or {}
        text = ((inter.get("button_reply") or inter.get("list_reply") or {})
                .get("title", ""))
    elif msg_type == "button":
        text = (message.get("button") or {}).get("text", "")
    else:
        from . import whatsapp
        whatsapp.send_text(wa_id, "Please send addresses as text messages.")
        return

    from . import whatsapp
    whatsapp.mark_read(msg_id)
    log.info("in <%s>: %s", wa_id, text.replace("\n", " | ")[:200])
    bot.handle_message(wa_id, text)


# ------------------------------------------------------------ helper routes


@app.post("/render")
def render_endpoint():
    """POST {"text": "...pasted addresses...", "biller": "option1"} -> PDF."""
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    biller_key = str(payload.get("biller", "option1")).lower()
    biller_id = config.billers().get(biller_key, {}).get("id", "")
    orders = [o for o in parse_orders(text) if o.is_usable()]
    if not orders:
        return jsonify(error="no usable addresses found"), 400
    path = render_pdf(orders, biller_id, f"{config.OUTPUT_DIR}/api-labels.pdf")
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name="prepaid-labels.pdf")


@app.post("/parse")
def parse_endpoint():
    """Dry run: see exactly how a paste will be understood."""
    payload = request.get_json(silent=True) or {}
    orders = parse_orders(payload.get("text", ""))
    return jsonify(count=len(orders), orders=[o.to_dict() for o in orders])


if __name__ == "__main__":  # local dev only; Render uses gunicorn
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
