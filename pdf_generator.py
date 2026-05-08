"""
PDF Generator - Rebuilt from exact template measurements.

Template measurements (from prepaidtemplate.docx):
  Page: 210mm x 297mm, Margins: 12.7mm all sides
  Table: 3 rows x 2 cols, each row = 79.8mm tall
  Each cell has 14 paragraphs:
    Para 0  : "To:"          (sz=14pt)
    Para 1-7: Address lines  (sz=14pt, name at para1 is larger)
    Para 8  : Spacer/order   (sz=14pt) - order item goes here
    Para 9-12: From block    (sz=12pt) - right aligned via tab
    Para 13 : Biller ID      (sz=10pt)
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
pt = 1  # 1 point = 1 reportlab unit
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


# ── Exact template dimensions ────────────────────────────────────────────────
PAGE_W       = 210 * mm
PAGE_H       = 297 * mm
MARGIN       = 12.7 * mm

# Usable area: 210 - 2*12.7 = 184.6mm wide, 297 - 2*12.7 = 271.6mm tall
USABLE_W     = PAGE_W - 2 * MARGIN       # 184.6mm
USABLE_H     = PAGE_H - 2 * MARGIN       # 271.6mm

# Each cell in the 3x2 grid
COL_W        = USABLE_W / 2              # 92.3mm each
ROW_H        = USABLE_H / 3             # 90.5mm each (3 rows)

# Inner cell padding (mimics Word's default cell margins ~1.8mm)
CELL_PAD     = 1.8 * mm

# Font sizes matching the template exactly
# Word sz=28 → 14pt, sz=24 → 12pt, sz=20 → 10pt, sz=22 → 11pt
SZ_TO_LABEL  = 10    # "To:" label
SZ_NAME      = 12    # Customer name (slightly bigger)
SZ_ADDR      = 9     # Address lines
SZ_FROM_LBL  = 9     # "From:" label
SZ_FROM_BODY = 9     # From address lines
SZ_BILLER    = 8     # Biller ID

FONT_BOLD    = 'Helvetica-Bold'
FONT_NORMAL  = 'Helvetica'

# ── Styles ───────────────────────────────────────────────────────────────────
def make_styles():
    s = getSampleStyleSheet()

    to_label = ParagraphStyle('ToLabel',
        fontName=FONT_BOLD, fontSize=SZ_TO_LABEL,
        leading=SZ_TO_LABEL * 1.2, textColor=colors.black,
        spaceAfter=0, spaceBefore=0)

    name_style = ParagraphStyle('Name',
        fontName=FONT_BOLD, fontSize=SZ_NAME,
        leading=SZ_NAME * 1.2, textColor=colors.black,
        spaceAfter=0, spaceBefore=0)

    addr_style = ParagraphStyle('Addr',
        fontName=FONT_BOLD, fontSize=SZ_ADDR,
        leading=SZ_ADDR * 1.3, textColor=colors.black,
        spaceAfter=0, spaceBefore=0)

    from_label = ParagraphStyle('FromLabel',
        fontName=FONT_BOLD, fontSize=SZ_FROM_LBL,
        leading=SZ_FROM_LBL * 1.2, textColor=colors.black,
        alignment=TA_RIGHT, spaceAfter=0, spaceBefore=0)

    from_body = ParagraphStyle('FromBody',
        fontName=FONT_BOLD, fontSize=SZ_FROM_BODY,
        leading=SZ_FROM_BODY * 1.3, textColor=colors.black,
        alignment=TA_RIGHT, spaceAfter=0, spaceBefore=0)

    order_style = ParagraphStyle('Order',
        fontName=FONT_BOLD, fontSize=SZ_ADDR,
        leading=SZ_ADDR * 1.2, textColor=colors.black,
        spaceAfter=0, spaceBefore=0)

    biller_style = ParagraphStyle('Biller',
        fontName=FONT_BOLD, fontSize=SZ_BILLER,
        leading=SZ_BILLER * 1.2, textColor=colors.black,
        spaceAfter=0, spaceBefore=0)

    return to_label, name_style, addr_style, from_label, from_body, order_style, biller_style


# ── Build one label cell ─────────────────────────────────────────────────────
def build_cell(addr, biller_id, styles):
    to_label, name_style, addr_style, from_label, from_body, order_style, biller_style = styles

    if addr is None:
        # Empty cell - just show From and Biller
        to_block = [[Paragraph("To:", to_label)]]
        addr_rows = [[Paragraph("", addr_style)]] * 7
    else:
        to_block = [[Paragraph("To:", to_label)]]
        # Name on its own row (larger font)
        name_row = [[Paragraph(addr.get('name', ''), name_style)]]
        # Address broken into lines
        addr_text = addr.get('address', '')
        pin_text  = f"Pin: {addr.get('pincode', '')}" if addr.get('pincode') else ""
        state_text = addr.get('state', '')
        mob_text  = f"Mob: {addr.get('phone', '')}" if addr.get('phone') else ""

        addr_lines = [addr_text, pin_text, state_text, mob_text]
        addr_rows = [[Paragraph(line, addr_style)] for line in addr_lines if line.strip()]
        # Pad to ensure consistent structure
        while len(addr_rows) < 6:
            addr_rows.append([Paragraph("", addr_style)])
        addr_rows = addr_rows[:6]  # max 6 lines

    # Order text (bottom left)
    order_text = addr.get('order', '') if addr else ''
    order_row = Paragraph(order_text, order_style)

    # From block (bottom right, right-aligned)
    from_lines = [
        Paragraph("From:", from_label),
        Paragraph("CREAM X EMIRATES", from_body),
        Paragraph("PUTHUPALLY, KTM", from_body),
        Paragraph(f"Pin: 686011", from_body),
        Paragraph(f"Mob: 8129770502", from_body),
    ]

    biller_row = Paragraph(f"Biller ID: {biller_id}", biller_style)

    # ── Bottom section: order(left) | from(right) ──────────────────────────
    from_col_w = COL_W * 0.52   # From block takes ~52% of cell width
    order_col_w = COL_W - from_col_w - 2 * CELL_PAD  # rest for order

    from_table_data = [[p] for p in from_lines]
    from_inner = Table(from_table_data, colWidths=[from_col_w])
    from_inner.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('ALIGN',         (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))

    bottom_row = Table(
        [[order_row, from_inner]],
        colWidths=[order_col_w, from_col_w]
    )
    bottom_row.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    # ── Address top section ────────────────────────────────────────────────
    # Total cell inner height = ROW_H - 2*CELL_PAD
    inner_h = ROW_H - 2 * CELL_PAD

    # Estimate bottom section height: ~5 lines of from_body + order
    bottom_h = (SZ_FROM_LBL * 1.2 + 4 * SZ_FROM_BODY * 1.3) * pt
    biller_h = SZ_BILLER * 1.5 * pt
    addr_h   = inner_h - bottom_h - biller_h

    # Build address rows as a sub-table
    addr_data = [[Paragraph("To:", to_label)]]
    if addr:
        addr_data.append([Paragraph(addr.get('name', ''), name_style)])
        for line in [addr_text, pin_text, state_text, mob_text]:
            if line.strip():
                addr_data.append([Paragraph(line, addr_style)])

    addr_table = Table(addr_data, colWidths=[COL_W - 2 * CELL_PAD])
    addr_table.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))

    # Final cell structure: [address top] [biller] [order+from]
    cell_data = [
        [addr_table],
        [biller_row],
        [bottom_row],
    ]
    cell_table = Table(
        cell_data,
        colWidths=[COL_W - 2 * CELL_PAD],
        rowHeights=[addr_h, biller_h, bottom_h]
    )
    cell_table.setStyle(TableStyle([
        ('VALIGN',        (0,0), (0,0), 'TOP'),
        ('VALIGN',        (0,1), (0,1), 'BOTTOM'),
        ('VALIGN',        (0,2), (0,2), 'BOTTOM'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    return cell_table


# ── Public API ───────────────────────────────────────────────────────────────
def create_address_pdf(addresses, biller_id, pdf_path):
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    styles = make_styles()
    elements = []
    blocks_per_page = 6

    for i in range(0, len(addresses), blocks_per_page):
        chunk = list(addresses[i:i + blocks_per_page])
        while len(chunk) < 6:
            chunk.append(None)

        grid_data = []
        for row_i in range(3):
            row = []
            for col_i in range(2):
                addr = chunk[row_i * 2 + col_i]
                row.append(build_cell(addr, biller_id, styles))
            grid_data.append(row)

        grid = Table(
            grid_data,
            colWidths=[COL_W, COL_W],
            rowHeights=[ROW_H, ROW_H, ROW_H],
        )
        grid.setStyle(TableStyle([
            ('GRID',          (0,0), (-1,-1), 0.75, colors.black),
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), CELL_PAD),
            ('RIGHTPADDING',  (0,0), (-1,-1), CELL_PAD),
            ('TOPPADDING',    (0,0), (-1,-1), CELL_PAD),
            ('BOTTOMPADDING', (0,0), (-1,-1), CELL_PAD),
        ]))

        elements.append(grid)

    doc.build(elements)
