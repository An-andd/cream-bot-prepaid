"""Render orders as shipping labels: 2 columns x 3 rows = 6 per page.

The layout mirrors the existing printed labels exactly:

    To:
    Name: <name>
    Address: <line 1>
    <line 2...>
    District: <d>   State: <s>
    Pincode: <p>
    Phone Number: <a> , <b>

    <product>

    From:
    CREAM X EMIRATES
    PUTHUPALLY, KTM
    Pin: 686011
    Mob: 8129770502
    Biller ID: <id>
"""
from __future__ import annotations

import os

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

from . import config
from .parsing import Order

Line = tuple[str, bool]  # (text, bold)


# ------------------------------------------------------------- content build


def build_to_lines(order: Order) -> list[Line]:
    """The customer block: everything printed under 'To:'."""
    lines: list[Line] = [("To:", True)]

    if order.name:
        lines.append((f"Name: {order.name}", False))

    if order.address_lines:
        lines.append((f"Address: {order.address_lines[0]}", False))
        for extra in order.address_lines[1:]:
            lines.append((extra, False))

    if order.place:
        lines.append((f"Place: {order.place}", False))

    # District and State share a line on the existing labels when both exist.
    if order.district and order.state:
        lines.append((f"District: {order.district}   State: {order.state}", False))
    elif order.district:
        lines.append((f"District: {order.district}", False))
    elif order.state:
        lines.append((f"State: {order.state}", False))

    if order.pincode:
        lines.append((f"Pincode: {order.pincode}", False))

    if order.phones:
        lines.append((f"{config.PHONE_LABEL}: {' , '.join(order.phones)}", False))

    if order.items:
        lines.append(("", False))
        item_text = " , ".join(order.items)
        if order.note:
            item_text = f"{item_text}. {order.note}"
        lines.append((item_text, True))
    elif order.note:
        lines.append(("", False))
        lines.append((order.note, True))

    return lines


def build_from_lines(biller_id: str) -> list[Line]:
    """The fixed sender block, printed on the right of each label."""
    lines: list[Line] = [("From:", True), (config.SENDER_NAME, False)]
    for addr in config.sender_address_lines():
        lines.append((addr, False))
    if config.SENDER_PIN:
        lines.append((f"Pin: {config.SENDER_PIN}", False))
    if config.SENDER_PHONE:
        lines.append((f"Mob: {config.SENDER_PHONE}", False))
    if biller_id:
        lines.append(("", False))
        lines.append((f"Biller ID: {biller_id}", False))
    return lines


def build_label_lines(order: Order, biller_id: str) -> list[Line]:
    """Single-column version (FROM stacked under TO). Used by the .docx
    fallback and kept so FROM_BLOCK_POSITION=below still works."""
    return build_to_lines(order) + [("", False)] + build_from_lines(biller_id)


# ------------------------------------------------------------------ wrapping


def _wrap(text: str, bold: bool, size: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    font = config.FONT_NAME_BOLD if bold else config.FONT_NAME
    if stringWidth(text, font, size) <= max_width:
        return [text]
    out: list[str] = []
    for word in text.split(" "):
        if not out:
            out = [word]
            continue
        trial = f"{out[-1]} {word}"
        if stringWidth(trial, font, size) <= max_width:
            out[-1] = trial
        else:
            out.append(word)
    # hard-break any single word that is still too wide (long addresses/urls)
    final: list[str] = []
    for chunk in out:
        while stringWidth(chunk, font, size) > max_width and len(chunk) > 1:
            cut = len(chunk)
            while cut > 1 and stringWidth(chunk[:cut], font, size) > max_width:
                cut -= 1
            final.append(chunk[:cut])
            chunk = chunk[cut:]
        final.append(chunk)
    return final


def _layout(lines: list[Line], size: float, max_width: float) -> list[Line]:
    wrapped: list[Line] = []
    for text, bold in lines:
        for piece in _wrap(text, bold, size, max_width):
            wrapped.append((piece, bold))
    return wrapped


def _fit_font(lines: list[Line], box_w: float, box_h: float) -> tuple[float, list[Line]]:
    size = config.BASE_FONT_SIZE
    while size >= config.MIN_FONT_SIZE:
        wrapped = _layout(lines, size, box_w)
        leading = size * 1.22
        if len(wrapped) * leading <= box_h:
            return size, wrapped
        size -= 0.25
    size = config.MIN_FONT_SIZE
    return size, _layout(lines, size, box_w)


def _fit_two_columns(to_lines: list[Line], from_lines: list[Line],
                     to_w: float, from_w: float, box_h: float
                     ) -> tuple[float, list[Line], list[Line]]:
    """Pick the largest font at which BOTH columns still fit the box."""
    size = config.BASE_FONT_SIZE
    while size >= config.MIN_FONT_SIZE:
        left = _layout(to_lines, size, to_w)
        right = _layout(from_lines, size, from_w)
        leading = size * 1.22
        if (max(len(left), len(right)) * leading <= box_h
                and len(left) * leading <= box_h):
            return size, left, right
        size -= 0.25
    size = config.MIN_FONT_SIZE
    return size, _layout(to_lines, size, to_w), _layout(from_lines, size, from_w)


# -------------------------------------------------------------------- render


def _page_size():
    return letter if config.PAGE_SIZE == "LETTER" else A4


def _draw_block(c: rl_canvas.Canvas, lines: list[Line], x: float, top_y: float,
                size: float, floor_y: float) -> None:
    leading = size * 1.22
    ty = top_y
    for text, bold in lines:
        if ty < floor_y:
            break
        if text:
            c.setFont(config.FONT_NAME_BOLD if bold else config.FONT_NAME, size)
            c.drawString(x, ty, text)
        ty -= leading


def draw_label(c: rl_canvas.Canvas, x: float, y: float, w: float, h: float,
               order: Order, biller_id: str) -> None:
    """x, y = bottom-left corner of the cell."""
    if config.DRAW_BORDER:
        c.setLineWidth(config.BORDER_WIDTH)
        c.rect(x, y, w, h)

    pad = config.LABEL_PADDING_MM * mm
    box_w = w - 2 * pad
    box_h = h - 2 * pad

    if config.FROM_BLOCK_POSITION != "right":
        size, wrapped = _fit_font(build_label_lines(order, biller_id), box_w, box_h)
        _draw_block(c, wrapped, x + pad, y + h - pad - size, size, y + pad - size)
        return

    # ---- two columns: customer on the left, sender on the right ----------
    gap = config.COLUMN_GAP_MM * mm
    to_w = (box_w - gap) * config.TO_COLUMN_RATIO
    from_w = box_w - gap - to_w

    to_lines = build_to_lines(order)
    from_lines = build_from_lines(biller_id)
    size, left, right = _fit_two_columns(to_lines, from_lines, to_w, from_w, box_h)
    leading = size * 1.22

    top = y + h - pad - size
    floor_y = y + pad - size
    _draw_block(c, left, x + pad, top, size, floor_y)

    right_x = x + pad + to_w + gap
    right_h = len(right) * leading
    if config.FROM_VALIGN == "top":
        right_top = top
    elif config.FROM_VALIGN == "middle":
        right_top = y + h / 2 + right_h / 2 - size
    else:  # bottom
        right_top = y + pad + right_h - size
    right_top = min(right_top, top)
    _draw_block(c, right, right_x, right_top, size, floor_y)


def render_pdf(orders: list[Order], biller_id: str, out_path: str,
               title: str = "Prepaid Shipping Labels") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    page_w, page_h = _page_size()
    c = rl_canvas.Canvas(out_path, pagesize=(page_w, page_h))
    c.setTitle(title)

    margin = config.PAGE_MARGIN_MM * mm
    cols, rows = config.LABELS_PER_ROW, config.LABEL_ROWS
    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows

    for index, order in enumerate(orders):
        slot = index % (cols * rows)
        if index and slot == 0:
            c.showPage()
        row, col = divmod(slot, cols)
        x = margin + col * cell_w
        y = page_h - margin - (row + 1) * cell_h
        draw_label(c, x, y, cell_w, cell_h, order, biller_id)

    if not orders:
        c.setFont(config.FONT_NAME, 12)
        c.drawString(margin, page_h - margin - 20, "No orders.")
    c.showPage()
    c.save()
    return out_path
