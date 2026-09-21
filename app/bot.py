"""The start -> biller -> paste addresses -> stop conversation flow."""
from __future__ import annotations

import datetime as dt
import logging
import os
import re

from . import config, store, whatsapp, woo
from .labels import render_pdf
from .parsing import Order, parse_orders

log = logging.getLogger(__name__)

HELP = (
    "Commands\n"
    "start - begin a new batch\n"
    "1 / 2 / 3 - choose the biller option\n"
    "(then paste addresses, any number of messages)\n"
    "woo [n] - pull the last n prepaid WooCommerce orders\n"
    "list - show what is in the batch\n"
    "undo - remove the last address\n"
    "clear - empty the batch, keep the biller\n"
    "stop - build the PDF and send it here\n"
    "cancel - throw the batch away\n"
    "help - this message"
)


def biller_menu() -> str:
    lines = ["Choose biller option:"]
    for key, value in sorted(config.billers().items()):
        num = key.replace("option", "")
        lines.append(f"{num} - {value.get('id', '')} ({value.get('label', key)})")
    lines.append("\nSend: 1 or 2 or 3")
    return "\n".join(lines)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").strip().lower()).strip()


def _match_biller(text: str) -> tuple[str, dict] | None:
    key = _norm(text).replace(" ", "")
    table = config.billers()
    if key in table:
        return key, table[key]
    if key.isdigit() and f"option{key}" in table:
        return f"option{key}", table[f"option{key}"]
    for name, value in table.items():              # allow the raw biller id
        if key == str(value.get("id", "")).lower():
            return name, value
    return None


def _orders(session: dict) -> list[Order]:
    return [Order.from_dict(d) for d in session.get("orders", [])]


def _store_orders(session: dict, orders: list[Order]) -> None:
    session["orders"] = [o.to_dict() for o in orders]


def _batch_list(orders: list[Order]) -> str:
    if not orders:
        return "The batch is empty."
    lines = [f"{i + 1}. {o.summary()}" for i, o in enumerate(orders)]
    pages = (len(orders) + config.LABELS_PER_PAGE - 1) // config.LABELS_PER_PAGE
    lines.append(f"\n{len(orders)} labels, {pages} page(s).")
    return "\n".join(lines)


def _output_path(wa_id: str, ext: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    return os.path.join(config.OUTPUT_DIR, f"prepaid-labels-{stamp}-{wa_id[-4:]}.{ext}")


# --------------------------------------------------------------- main handler


def handle_message(wa_id: str, text: str) -> None:
    """Process one inbound WhatsApp text and reply."""
    session = store.get_session(wa_id)
    state = session["state"]
    command = _norm(text)

    if command in ("help", "menu", "?"):
        whatsapp.send_text(wa_id, HELP)
        return

    if command in ("start", "begin", "new"):
        store.save_session(wa_id, {"state": store.AWAITING_BILLER, "biller": "",
                                   "biller_id": "", "orders": []})
        whatsapp.send_text(wa_id, "Started new batch setup.\n" + biller_menu())
        return

    if command in ("cancel", "abort", "quit"):
        store.reset_session(wa_id)
        whatsapp.send_text(wa_id, "Batch cancelled. Send 'start' when you are ready.")
        return

    if state == store.IDLE:
        whatsapp.send_text(wa_id, "Send 'start' to begin a prepaid label batch.")
        return

    # ------------------------------------------------------ choosing a biller
    if state == store.AWAITING_BILLER:
        match = _match_biller(text)
        if not match:
            whatsapp.send_text(wa_id, "I did not recognise that option.\n\n" + biller_menu())
            return
        key, value = match
        session.update({"state": store.COLLECTING, "biller": key,
                        "biller_id": str(value.get("id", ""))})
        store.save_session(wa_id, session)
        whatsapp.send_text(
            wa_id,
            f"Biller ID set: {value.get('id')} ({value.get('label', key)}).\n\n"
            "Now paste the prepaid addresses. One or many per message, as many "
            "messages as you like.\nSend 'stop' when you are done.",
        )
        return

    # ------------------------------------------------------------ collecting
    orders = _orders(session)

    if command == "list":
        whatsapp.send_text(wa_id, _batch_list(orders))
        return

    if command == "undo":
        if orders:
            removed = orders.pop()
            _store_orders(session, orders)
            store.save_session(wa_id, session)
            whatsapp.send_text(wa_id, f"Removed: {removed.summary()}\n{len(orders)} left.")
        else:
            whatsapp.send_text(wa_id, "Nothing to undo.")
        return

    if command == "clear":
        _store_orders(session, [])
        store.save_session(wa_id, session)
        whatsapp.send_text(wa_id, "Batch emptied. Biller ID kept.")
        return

    if command.startswith("biller"):
        session["state"] = store.AWAITING_BILLER
        store.save_session(wa_id, session)
        whatsapp.send_text(wa_id, biller_menu())
        return

    if command.startswith("woo"):
        _handle_woo(wa_id, session, orders, command)
        return

    if command == "stop":
        _finish(wa_id, session, orders)
        return

    # ---------------------------------------------- an actual address paste
    new_orders = parse_orders(text)
    usable = [o for o in new_orders if o.is_usable()]
    rejected = [o for o in new_orders if not o.is_usable()]

    if not usable:
        whatsapp.send_text(
            wa_id,
            "I could not read an address there. Each address needs at least a "
            "name and an address line. Send 'help' for commands.",
        )
        return

    orders.extend(usable)
    _store_orders(session, orders)
    store.save_session(wa_id, session)

    parts = [f"Added {len(usable)} address(es). Total: {len(orders)}."]
    for order in usable:
        missing = order.missing()
        if missing:
            parts.append(f"! {order.summary()} - missing {', '.join(missing)}")
    if rejected:
        parts.append(f"{len(rejected)} block(s) skipped: too little information.")
    whatsapp.send_text(wa_id, "\n".join(parts))


def _handle_woo(wa_id: str, session: dict, orders: list[Order], command: str) -> None:
    if not woo.configured():
        whatsapp.send_text(wa_id, "WooCommerce is not configured on this server.")
        return
    match = re.search(r"\d+", command)
    limit = int(match.group()) if match else 20
    try:
        pulled = woo.fetch_prepaid_orders(limit=limit)
    except Exception as exc:  # noqa: BLE001 - surface the reason to the operator
        log.exception("woo fetch failed")
        whatsapp.send_text(wa_id, f"WooCommerce fetch failed: {exc}")
        return
    if not pulled:
        whatsapp.send_text(wa_id, "No prepaid orders found.")
        return
    known = {(o.name.lower(), o.pincode, o.ref) for o in orders}
    fresh = [o for o in pulled if (o.name.lower(), o.pincode, o.ref) not in known]
    orders.extend(fresh)
    _store_orders(session, orders)
    store.save_session(wa_id, session)
    whatsapp.send_text(
        wa_id,
        f"Pulled {len(fresh)} prepaid order(s) from WooCommerce. Total: {len(orders)}.\n\n"
        + _batch_list(orders),
    )


def _finish(wa_id: str, session: dict, orders: list[Order]) -> None:
    if not orders:
        whatsapp.send_text(wa_id, "Nothing to print. Paste some addresses first.")
        return
    biller_id = session.get("biller_id", "")
    pages = (len(orders) + config.LABELS_PER_PAGE - 1) // config.LABELS_PER_PAGE
    whatsapp.send_text(wa_id, f"Building {len(orders)} labels on {pages} page(s)...")

    pdf_path = render_pdf(orders, biller_id, _output_path(wa_id, "pdf"))
    caption = (f"{len(orders)} prepaid labels, {pages} page(s), "
               f"Biller ID {biller_id}")
    whatsapp.send_document(wa_id, pdf_path, caption)

    if config.OUTPUT_FORMAT in ("docx", "both"):
        from .labels_docx import render_docx
        docx_path = render_docx(orders, biller_id, _output_path(wa_id, "docx"))
        whatsapp.send_document(
            wa_id, docx_path, "Editable Word version",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    store.reset_session(wa_id)
    whatsapp.send_text(wa_id, "Done. Send 'start' for the next batch.")
