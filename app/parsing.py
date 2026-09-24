"""Parse pasted, messy shipping addresses into structured orders.

The input is whatever the operator pastes into WhatsApp. Real samples look like:

    To:
    Name: Ilakkiya
    Address: 2/165 mpk valasai
    Kumparam (post)
    District: Ramanathapuram State: Tamilnadu
    Pincode: 623523
    Phone Number: 6374177133 , 8111013566
    1cxe

    Name-rekhavargeesh
    Address-12A29 williyambooth.
    Place- kanniyakumari.
    District -kanniyakumari. Pincode-629 702
    State-tamilnadu.
    Contact num -6374209162
    1cxe

Both must parse. Nothing may be silently dropped: any line we cannot classify
is kept as part of the address.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config

# --------------------------------------------------------------------- model


@dataclass
class Item:
    text: str                 # already-formatted, e.g. "1cxe" or "Kurti x 2"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.text


@dataclass
class Order:
    name: str = ""
    address_lines: list[str] = field(default_factory=list)
    place: str = ""
    district: str = ""
    state: str = ""
    pincode: str = ""
    phones: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    note: str = ""
    source: str = "whatsapp"
    ref: str = ""             # woo order number, if any

    # -------------------------------------------------- helpers
    def is_usable(self) -> bool:
        """A label is only worth printing when we know who and where."""
        has_where = bool(self.address_lines or self.pincode or self.district or self.place)
        return bool(self.name) and has_where

    def missing(self) -> list[str]:
        miss = []
        if not self.name:
            miss.append("name")
        if not self.address_lines:
            miss.append("address")
        if not self.pincode:
            miss.append("pincode")
        if not self.phones:
            miss.append("phone")
        return miss

    def summary(self) -> str:
        bits = [self.name or "(no name)"]
        if self.pincode:
            bits.append(self.pincode)
        if self.items:
            bits.append("/".join(self.items))
        return " - ".join(bits)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "address_lines": self.address_lines,
            "place": self.place,
            "district": self.district,
            "state": self.state,
            "pincode": self.pincode,
            "phones": self.phones,
            "items": self.items,
            "note": self.note,
            "source": self.source,
            "ref": self.ref,
        }

    @staticmethod
    def from_dict(d: dict) -> "Order":
        return Order(
            name=d.get("name", ""),
            address_lines=list(d.get("address_lines", [])),
            place=d.get("place", ""),
            district=d.get("district", ""),
            state=d.get("state", ""),
            pincode=d.get("pincode", ""),
            phones=list(d.get("phones", [])),
            items=list(d.get("items", [])),
            note=d.get("note", ""),
            source=d.get("source", "whatsapp"),
            ref=d.get("ref", ""),
        )


# ------------------------------------------------------------- label aliases
# Order matters: longer aliases first so "phone number" wins over "phone".
ALIASES: list[tuple[str, str]] = [
    ("name", "name"),
    ("customer name", "name"),
    ("customer", "name"),
    ("address", "address"),
    ("addres", "address"),
    ("adress", "address"),
    ("aadress", "address"),
    ("addr", "address"),
    ("add", "address"),
    ("street", "address"),
    ("house", "address"),
    ("district", "district"),
    ("dist", "district"),
    ("dt", "district"),
    ("place", "place"),
    ("landmark", "place"),
    ("land mark", "place"),
    ("area", "place"),
    ("village", "place"),
    ("post", "place"),
    ("city", "place"),
    ("town", "place"),
    ("state", "state"),
    ("pincode", "pincode"),
    ("pin code", "pincode"),
    ("pin no", "pincode"),
    ("pin", "pincode"),
    ("postcode", "pincode"),
    ("post code", "pincode"),
    ("zip", "pincode"),
    ("phone number", "phone"),
    ("phone no", "phone"),
    ("phone num", "phone"),
    ("phone", "phone"),
    ("mobile number", "phone"),
    ("mobile no", "phone"),
    ("mobile", "phone"),
    ("mob no", "phone"),
    ("mob", "phone"),
    ("contact number", "phone"),
    ("contact num", "phone"),
    ("contact no", "phone"),
    ("contact", "phone"),
    ("whatsapp number", "phone"),
    ("whatsapp", "phone"),
    ("number", "phone"),
    ("num", "phone"),
    ("ph", "phone"),
    ("cell", "phone"),
    ("product", "product"),
    ("products", "product"),
    ("item", "product"),
    ("items", "product"),
    ("qty", "product"),
    ("quantity", "product"),
    ("order", "product"),
    ("note", "note"),
    ("remark", "note"),
    ("remarks", "note"),
]

_ALIAS_SORTED = sorted(ALIASES, key=lambda kv: -len(kv[0]))
_ALIAS_MAP = dict(ALIASES)

# Separator between a label and its value: :  -  ;  .  /  =  or just spaces.
_SEP = r"[:\-;\.\u2013\u2014/=]"
_LABEL_ALT = "|".join(re.escape(a) for a, _ in _ALIAS_SORTED)
# A label occurrence anywhere in a line (used to split "District: X State: Y").
_LABEL_RE = re.compile(
    rf"(?<![A-Za-z0-9])({_LABEL_ALT})\s*{_SEP}\s*", re.IGNORECASE
)
_LABEL_AT_START_RE = re.compile(
    rf"^\s*({_LABEL_ALT})\s*{_SEP}?\s*(.*)$", re.IGNORECASE
)

_TO_RE = re.compile(r"^\s*to\s*[:\-]?\s*(.*)$", re.IGNORECASE)
_FROM_RE = re.compile(r"(?<![A-Za-z])from\s*[:\-]?\s*", re.IGNORECASE)
_BILLER_RE = re.compile(r"^\s*biller\s*id", re.IGNORECASE)
_SENDER_JUNK_RE = re.compile(
    r"^\s*(pin\s*[:\-]?\s*\d{6}\s*|mob\s*[:\-]?\s*\d{10}\s*)$", re.IGNORECASE
)

# "1cxe", "10 cxe", "2 x cxe", "3CXE.", optionally followed by a note word.
_PRODUCT_RE = re.compile(
    r"^\s*(\d{1,4})\s*(?:[x\u00d7*]\s*)?([A-Za-z][A-Za-z0-9\-]{0,19})\s*\.?\s*$"
)
# "cxe 2", "cxe x 2"
_PRODUCT_REV_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9\-]{0,19})\s*(?:[x\u00d7*]\s*)?(\d{1,4})\s*\.?\s*$"
)

# Labels safe enough to also accept a comma as their separator
# ("Pincode, 631207" / "State, Tamilnadu").
_STRONG_LABELS = (
    "pincode", "pin code", "pin", "state", "district", "dist", "name",
    "phone number", "phone", "mobile", "mob", "contact number", "contact",
    "number",
)
_STRONG_COMMA_RE = re.compile(
    rf"(?<![A-Za-z0-9])({'|'.join(re.escape(l) for l in _STRONG_LABELS)})\s*,\s*",
    re.IGNORECASE,
)

_PIN_RE = re.compile(r"(?<!\d)(\d{3}\s?\d{3})(?!\d)")
_BARE_PIN_RE = re.compile(r"^\s*(\d{3})\s?(\d{3})\s*[.,;]?\s*$")
_DIGITS_RE = re.compile(r"\d")

# Indian states/UTs. Used only when the customer sends the state without
# writing "State:". This prevents it from being swallowed into the address.
_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan",
    "sikkim", "tamil nadu", "tamilnadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal",
    "andaman and nicobar islands", "chandigarh", "dadra and nagar haveli",
    "daman and diu", "delhi", "jammu and kashmir", "ladakh",
    "lakshadweep", "puducherry", "pondicherry",
}


# ------------------------------------------------------------------ utilities


def _clean(value: str) -> str:
    value = value.replace("\u00a0", " ").strip()
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" \t,;")


def _strip_trailing_dot(value: str) -> str:
    v = value.strip()
    while v.endswith((".", ",", ";")) and not re.search(r"\d\.$", v):
        v = v[:-1].rstrip()
    return v


def normalize_phones(raw: str) -> list[str]:
    """Pull every plausible phone number out of a string, keeping order.

    Handles '+91 63741 77133', '6374177133 , 8111013566', 'Phone number: 74836'.
    """
    if not raw:
        return []
    raw = re.sub(r"[^\d+,/&]+", " ", raw)
    # Split on obvious separators first so two numbers never merge.
    chunks = re.split(r"[,/&]| {2,}", raw)
    out: list[str] = []
    for chunk in chunks:
        digits_groups = re.findall(r"\+?\d[\d ]*", chunk)
        for grp in digits_groups:
            d = re.sub(r"\D", "", grp)
            # A chunk may still hold two 10-digit numbers glued by a space.
            while len(d) >= 20 and len(d) % 10 == 0:
                out.append(_trim_cc(d[:10]))
                d = d[10:]
            if len(d) >= 10:
                out.append(_trim_cc(d))
            elif len(d) >= 6 and not out:
                out.append(d)  # keep short landlines rather than lose them
    seen, uniq = set(), []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _trim_cc(digits: str) -> str:
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 13 and digits.startswith("091"):
        return digits[3:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def normalize_pincode(raw: str) -> str:
    m = _PIN_RE.search(raw or "")
    return re.sub(r"\s", "", m.group(1)) if m else ""


def _bare_pincode(line: str) -> str:
    m = _BARE_PIN_RE.fullmatch(line)
    return f"{m.group(1)}{m.group(2)}" if m else ""

def _extract_pincode(line: str) -> tuple[str, str]:
    """Extract a six-digit pincode and return (pin, remaining text)."""
    m = _PIN_RE.search(line or "")
    if not m:
        return "", line
    pin = re.sub(r"\s", "", m.group(1))
    remaining = (line[:m.start()] + " " + line[m.end():]).strip(" ,;.-")
    return pin, _clean(remaining)

def _state_from_text(value: str) -> str:
    low = _clean(value).lower().replace(".", "")
    low = re.sub(r"\s+", " ", low)
    if low in _STATES:
        # Preserve the spelling used by the customer except for the common
        # Tamilnadu spelling, which is kept as-is for the label.
        return _clean(value)
    return ""


def _looks_like_product(line: str) -> tuple[str, str] | None:
    products, note = _looks_like_products(line)
    if not products:
        return None
    return products[0], note


def _looks_like_products(line: str) -> tuple[list[str], str]:
    """Parse one or multiple product/quantity entries."""

    text = line.strip().rstrip(".")
    if not text:
        return [], ""

    note = ""

    # Detect a trailing note such as:
    # 1 CXE Return
    # 1 CXE, 1 BL Dtdc
    note_match = re.search(
        r"(?:^|[\s,.;])("
        + "|".join(re.escape(w) for w in config.NOTE_WORDS)
        + r")\s*$",
        text,
        re.IGNORECASE,
    )

    if note_match:
        note = note_match.group(1)
        text = text[:note_match.start()].strip(" .,;")

    if not text:
        return [], note

    # Multiple products can be separated by commas.
    chunks = [
        c.strip()
        for c in re.split(r"[,;]+", text)
        if c.strip()
    ]

    if not chunks:
        return [], note

    parsed = []

    for chunk in chunks:

        # Examples:
        # 1cxe
        # 10cxe
        # 3*CXE
        m = _PRODUCT_RE.fullmatch(chunk)

        if m:
            qty, code = m.group(1), m.group(2)
            parsed.append(f"{qty}{code}")
            continue

        # Example:
        # CXE x 2
        m = _PRODUCT_REV_RE.fullmatch(chunk)

        if m and m.group(1).lower() in config.KNOWN_PRODUCTS:
            parsed.append(f"{m.group(2)}{m.group(1)}")
            continue

        # Known product names
        low = chunk.lower().strip()

        matched = False

        for prod in config.KNOWN_PRODUCTS:
            m = re.fullmatch(
                rf"(\d{{1,4}})\s*(?:x\s*)?{re.escape(prod)}s?",
                low,
            )

            if m:
                parsed.append(f"{m.group(1)}{prod}")
                matched = True
                break

        if matched:
            continue

        # Free-form product:
        # 1 Salicyclic Serum
        # 2 Vit C Gel
        #
        # Requiring a space after the quantity prevents
        # "1st floor" from becoming a product.
        m = re.fullmatch(
            r"(\d{1,4})\s+(?:x\s+)?(.+?)",
            chunk,
            re.IGNORECASE,
        )

        if m:
            qty, name = m.group(1), m.group(2).strip()

            if name and not re.search(r"[/:]", name):
                parsed.append(f"{qty} {name}")
                continue

        # If even one chunk isn't a product, don't steal
        # the entire line from the address.
        return [], note

    return parsed, note

def _normalize_line(line: str) -> str:
    """Repair the small typing quirks that break naive label matching."""
    line = line.strip()
    # ":Name: C. Vinodhini" -> "Name: C. Vinodhini"  (a stray leading separator)
    line = re.sub(r"^[:\-;/]+\s*", "", line)
    # "Pincode, 631207" -> "Pincode: 631207"
    line = _STRONG_COMMA_RE.sub(lambda m: f"{m.group(1)}: ", line)
    return line


def _split_labelled(line: str) -> list[tuple[str | None, str]]:
    """Split a line into (field, value) pieces.

    'District: Ramanathapuram State: Tamilnadu'
        -> [('district', 'Ramanathapuram'), ('state', 'Tamilnadu')]
    'Kumparam (post)' -> [(None, 'Kumparam (post)')]
    """
    matches = list(_LABEL_RE.finditer(line))
    # Only treat a match as a label if it starts the line or follows a boundary
    # that makes sense (start, or preceded by space/comma).
    good = []
    for m in matches:
        start = m.start()
        if start == 0 or line[start - 1] in " \t,;.-":
            good.append(m)
    if not good:
        return [(None, line)]
    pieces: list[tuple[str | None, str]] = []
    if good[0].start() > 0:
        lead = line[: good[0].start()].strip(" ,;.-")
        if lead:
            pieces.append((None, lead))
    for i, m in enumerate(good):
        end = good[i + 1].start() if i + 1 < len(good) else len(line)
        value = line[m.end(): end]
        pieces.append((_ALIAS_MAP[m.group(1).lower()], value.strip(" ,;")))

    # "Theni dist." -> the value sits *before* the label, not after it.
    fixed: list[tuple[str | None, str]] = []
    for fieldname, value in pieces:
        if (
            fieldname
            and not value
            and fixed
            and fixed[-1][0] is None
            and fixed[-1][1]
            and fieldname != "address"
            # only a short, comma-free lead is really a value, e.g. "Theni dist."
            and "," not in fixed[-1][1]
            and len(fixed[-1][1].split()) <= 3
        ):
            lead = fixed.pop()[1]
            fixed.append((fieldname, lead))
        else:
            fixed.append((fieldname, value))
    return fixed


# ------------------------------------------------------------ block splitting


def _pre_split_lines(text: str) -> list[str]:
    """Normalise newlines and break inline 'To:' / 'From:' markers apart."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    out: list[str] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        # break "1cxe From:" into two lines
        parts = _FROM_RE.split(line)
        if len(parts) > 1:
            if parts[0].strip():
                out.append(parts[0].rstrip())
            out.append("From:")
            rest = "From:".join([]) or " ".join(p for p in parts[1:] if p.strip())
            if rest.strip():
                out.append(rest.strip())
            continue
        out.append(line)
    return out


def _is_name_start(line: str) -> bool:
    m = _LABEL_AT_START_RE.match(line)
    return bool(m and _ALIAS_MAP[m.group(1).lower()] == "name")


def split_blocks(text: str) -> list[list[str]]:
    """Cut a paste into per-customer line groups."""
    lines = _pre_split_lines(text)
    blocks: list[list[str]] = []
    cur: list[str] = []
    skipping_sender = False

    def flush() -> None:
        nonlocal cur
        if any(l.strip() for l in cur):
            blocks.append(cur)
        cur = []

    for raw in lines:
        line = _normalize_line(raw)
        to_m = _TO_RE.match(line) if line.lower().startswith("to") else None
        if to_m and (not to_m.group(1) or _is_name_start(to_m.group(1))):
            skipping_sender = False
            flush()
            if to_m.group(1).strip():
                cur.append(to_m.group(1).strip())
            continue
        if _FROM_RE.match(line) or line.lower().rstrip(":").strip() == "from":
            skipping_sender = True
            continue
        if skipping_sender:
            # sender block ends at the next customer marker
            if _is_name_start(line):
                skipping_sender = False
            else:
                continue
        if _BILLER_RE.match(line):
            continue
        if not line:
            if cur and _block_has_name(cur):
                flush()
            continue
        if _is_name_start(line) and _block_has_name(cur):
            flush()
        cur.append(line)
    flush()
    return blocks


def _block_has_name(block: list[str]) -> bool:
    return any(_is_name_start(l) for l in block)


# --------------------------------------------------------------- block parser


def _add_product(order: Order, products: list[str], note: str = "") -> None:
    for product in products:
        if product and product not in order.items:
            order.items.append(product)
    if note:
        order.note = (order.note + " " + note).strip()


def _classify_unlabelled(order: Order, value: str) -> None:
    """Classify a line that did not have an explicit field label."""
    value = _clean(value)
    if not value:
        return

    # A bare six-digit number is always a pincode, never an address line.
    pin = _bare_pincode(value)
    if pin:
        if not order.pincode:
            order.pincode = pin
        return

    # State supplied on its own, e.g. "Tamilnadu".
    state = _state_from_text(value)
    if state:
        if not order.state:
            order.state = state
        return

    # A pincode embedded in an otherwise useful line. Keep the remaining
    # address text instead of printing the pincode twice.
    pin, remaining = _extract_pincode(value)
    if pin:
        if not order.pincode:
            order.pincode = pin
        if not remaining:
            return
        value = remaining

    # Bare phone number.
    if _is_bare_phone(value):
        order.phones.extend(normalize_phones(value))
        return

    # Quantity/product lines such as "1cxe", "3 CXE", or "1cxe yesterday".
    products, prod_note = _looks_like_products(value)
    if products and (order.name or order.address_lines):
        _add_product(order, products, prod_note)
        return

    # If no name exists yet, the first unlabelled line is the most likely name.
    if not order.name and not order.address_lines:
        order.name = _strip_trailing_dot(value)
        return

    # Everything else is genuine address text.
    order.address_lines.append(_strip_trailing_dot(value))


def parse_block(block: list[str]) -> Order:
    order = Order()
    unlabelled: list[str] = []

    for raw in block:
        line = _normalize_line(_clean(raw))
        if not line or _BILLER_RE.match(line):
            continue
        if line == config.SENDER_NAME or line.upper() == config.SENDER_NAME.upper():
            continue
        if _SENDER_JUNK_RE.match(line) and not order.name:
            continue

        # Product lines can appear without a "Product:" label. Only classify
        # them as products after we have seen a customer/name or address.
        products, prod_note = _looks_like_products(line)
        if products and (order.name or unlabelled or order.address_lines):
            _add_product(order, products, prod_note)
            continue

        for fieldname, value in _split_labelled(line):
            value = _clean(value)

            if fieldname is None:
                if value:
                    unlabelled.append(value)
                continue

            if not value:
                continue

            if fieldname == "name" and not order.name:
                order.name = _strip_trailing_dot(value)

            elif fieldname == "address":
                pin, remaining = _extract_pincode(value)
                if pin and not order.pincode:
                    order.pincode = pin
                if remaining:
                    order.address_lines.append(_strip_trailing_dot(remaining))

            elif fieldname == "district" and not order.district:
                order.district = _strip_trailing_dot(value)

            elif fieldname == "place" and not order.place:
                order.place = _strip_trailing_dot(value)

            elif fieldname == "state" and not order.state:
                order.state = _strip_trailing_dot(value)

            elif fieldname == "pincode":
                pin = normalize_pincode(value)
                if pin and not order.pincode:
                    order.pincode = pin
                elif not pin:
                    unlabelled.append(value)

            elif fieldname == "phone":
                order.phones.extend(normalize_phones(value))

            elif fieldname == "product":
                products, prod_note = _looks_like_products(value)
                if products:
                    _add_product(order, products, prod_note)
                else:
                    order.items.append(value)
                    if prod_note:
                        order.note = (order.note + " " + prod_note).strip()

            elif fieldname == "note":
                order.note = (order.note + " " + value).strip()

            else:
                unlabelled.append(value)

    # Do this only after all labelled fields are known. That way a bare state
    # or pincode is no longer accidentally appended to the address.
    for value in unlabelled:
        _classify_unlabelled(order, value)

    # Last chance: a pincode may have been attached to an address/place line.
    if not order.pincode:
        for i, line in enumerate(order.address_lines):
            pin, remaining = _extract_pincode(line)
            if pin:
                order.pincode = pin
                if remaining:
                    order.address_lines[i] = remaining
                else:
                    order.address_lines.pop(i)
                break

    # Remove any bare state/pincode lines that may have arrived through an
    # explicitly-labelled Address block.
    cleaned_address = []
    for line in order.address_lines:
        line = _strip_trailing_dot(_clean(line))
        if not line:
            continue
        pin = _bare_pincode(line)
        if pin:
            if not order.pincode:
                order.pincode = pin
            continue
        state = _state_from_text(line)
        if state:
            if not order.state:
                order.state = state
            continue
        cleaned_address.append(line)
    order.address_lines = cleaned_address

    # Dedupe phones while preserving order.
    seen, phones = set(), []
    for phone in order.phones:
        if phone and phone not in seen:
            seen.add(phone)
            phones.append(phone)
    order.phones = phones
    order.note = _clean(order.note)
    return order

def _is_bare_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    letters = re.sub(r"[^A-Za-z]", "", value)
    return len(digits) >= 10 and len(letters) == 0


def parse_orders(text: str) -> list[Order]:
    """Main entry point: messy paste in, list of Orders out."""
    orders = [parse_block(b) for b in split_blocks(text)]
    return [o for o in orders if o.name or o.address_lines]
