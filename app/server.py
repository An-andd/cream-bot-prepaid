"""Flask app: WhatsApp Cloud API webhook + a couple of helper endpoints."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request, send_file

from . import bot, config, store, woo
from .labels import render_pdf
from .parsing import parse_orders
from . import telegram

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
@app.post("/telegram-webhook")
def telegram_webhook():

    # Verify Telegram's secret header
    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        ""
    )

    if config.TELEGRAM_WEBHOOK_SECRET:
        if secret != config.TELEGRAM_WEBHOOK_SECRET:
            return "forbidden", 403

    data = request.get_json(silent=True) or {}

    try:
        message = data.get("message", {}) or {}

        chat = message.get("chat", {}) or {}
        chat_id = chat.get("id")

        if chat_id is None:
            return jsonify(status="ignored"), 200

        text = message.get("text", "")

        if not text:
            telegram.send_text(
                str(chat_id),
                "Please send the prepaid addresses as text messages."
            )
            return jsonify(status="received"), 200

        chat_id = str(chat_id)

        if (
            config.TELEGRAM_ALLOWED_CHAT_IDS
            and chat_id not in config.TELEGRAM_ALLOWED_CHAT_IDS
        ):
            log.warning(
                "Ignoring Telegram message from unauthorized chat %s",
                chat_id,
            )
            return jsonify(status="ignored"), 200

        log.info(
            "Telegram <%s>: %s",
            chat_id,
            text.replace("\n", " | ")[:200],
        )

        bot.handle_message(chat_id, text)

    except Exception:
        log.exception("Telegram webhook processing failed")

    return jsonify(status="received"), 200

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

@app.get("/telegram/setup")
def telegram_setup():

    if not config.TELEGRAM_TOKEN:
        return jsonify(
            error="TELEGRAM_TOKEN is not configured"
        ), 500

    webhook_url = (
        request.url_root.rstrip("/")
        + "/telegram-webhook"
    )

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/setWebhook"

    payload = {
        "url": webhook_url,
        "secret_token": config.TELEGRAM_WEBHOOK_SECRET,
        "drop_pending_updates": True,
        "allowed_updates": ["message"],
    }

    r = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    return jsonify(
        webhook_url=webhook_url,
        telegram_response=r.json(),
    )

@app.get("/telegram/status")
def telegram_status():

    if not config.TELEGRAM_TOKEN:
        return jsonify(
            error="TELEGRAM_TOKEN is not configured"
        ), 500

    url = (
        f"https://api.telegram.org/bot"
        f"{config.TELEGRAM_TOKEN}/getWebhookInfo"
    )

    r = requests.get(url, timeout=30)

    return jsonify(r.json())