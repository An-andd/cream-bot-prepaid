"""Pull prepaid (non-COD, paid) orders straight from WooCommerce.

Optional: the WhatsApp paste flow works without this. When WOO_* env vars are
set, the operator can type `woo` (or `woo 20`) during collection and the last
N prepaid orders are converted into labels automatically.
"""
from __future__ import annotations

import logging

import requests

from . import config
from .parsing import Order, normalize_phones, normalize_pincode

log = logging.getLogger(__name__)


class WooNotConfigured(RuntimeError):
    pass


def configured() -> bool:
    return bool(config.WOO_URL and config.WOO_KEY and config.WOO_SECRET)


def _get(path: str, params: dict) -> list[dict]:
    if not configured():
        raise WooNotConfigured("WOO_URL / WOO_CONSUMER_KEY / WOO_CONSUMER_SECRET missing")
    r = requests.get(
        f"{config.WOO_URL}/wp-json/wc/v3/{path}",
        params=params,
        auth=(config.WOO_KEY, config.WOO_SECRET),
        timeout=45,
    )
    r.raise_for_status()
    return r.json()


def is_prepaid(order: dict) -> bool:
    """Paid and not cash-on-delivery."""
    status = (order.get("status") or "").lower()
    if status not in config.WOO_PAID_STATUSES:
        return False
    method = f"{order.get('payment_method', '')} {order.get('payment_method_title', '')}".lower()
    if any(cod in method for cod in config.WOO_COD_METHODS):
        return False
    # date_paid is the strongest signal that money actually arrived
    return bool(order.get("date_paid")) or status == "completed"


def _address_lines(addr: dict) -> list[str]:
    """Keep every meaningful component; never collapse to line 1 only."""
    lines: list[str] = []
    for key in ("company", "address_1", "address_2"):
        value = (addr.get(key) or "").strip()
        if value:
            lines.extend(p.strip() for p in value.splitlines() if p.strip())
    city = (addr.get("city") or "").strip()
    if city:
        lines.append(city)
    return lines


def _meta(order: dict, *keys: str) -> str:
    for item in order.get("meta_data") or []:
        if str(item.get("key", "")).lower().lstrip("_") in keys:
            value = item.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def order_from_woo(raw: dict) -> Order:
    ship = raw.get("shipping") or {}
    bill = raw.get("billing") or {}
    use = ship if (ship.get("address_1") or ship.get("city")) else bill

    name = " ".join(
        p for p in [(use.get("first_name") or "").strip(),
                    (use.get("last_name") or "").strip()] if p
    ).strip()
    if not name:
        name = " ".join(
            p for p in [(bill.get("first_name") or "").strip(),
                        (bill.get("last_name") or "").strip()] if p
        ).strip()

    phones = normalize_phones(bill.get("phone") or "")
    phones += [p for p in normalize_phones(use.get("phone") or "") if p not in phones]
    alt = _meta(raw, "alternate_phone", "alt_phone", "billing_phone_2", "phone_2")
    for p in normalize_phones(alt):
        if p not in phones:
            phones.append(p)

    items = []
    for li in raw.get("line_items") or []:
        qty = int(li.get("quantity") or 1)
        pname = (li.get("name") or "").strip()
        sku = (li.get("sku") or "").strip()
        code = sku or pname
        # "1cxe" style when the code is a single token, else "Kurti x 2"
        items.append(f"{qty}{code}" if code and " " not in code else f"{pname} x {qty}")

    note = (raw.get("customer_note") or "").strip()

    return Order(
        name=name,
        address_lines=_address_lines(use),
        place=_meta(raw, "landmark", "place"),
        district=_meta(raw, "district", "billing_district", "shipping_district"),
        state=(use.get("state") or bill.get("state") or "").strip(),
        pincode=normalize_pincode(use.get("postcode") or bill.get("postcode") or ""),
        phones=phones,
        items=items,
        note=note,
        source="woocommerce",
        ref=str(raw.get("number") or raw.get("id") or ""),
    )


def fetch_prepaid_orders(limit: int = 20, after: str | None = None) -> list[Order]:
    params = {
        "per_page": min(max(limit * 2, 10), 100),
        "orderby": "date",
        "order": "desc",
        "status": ",".join(config.WOO_PAID_STATUSES),
    }
    if after:
        params["after"] = after
    raws = _get("orders", params)
    out = [order_from_woo(r) for r in raws if is_prepaid(r)]
    out.reverse()  # oldest first, so labels print in order received
    return out[-limit:]
