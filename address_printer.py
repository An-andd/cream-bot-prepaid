"""
Prepaid Address Printer Automation
===================================
Automates printing of customer addresses from WhatsApp messages
into a DOCX template with 6 address blocks per page, then exports to PDF.

Approach: docxtpl placeholder filling — template formatting is NEVER touched,
only the placeholder text is replaced. This guarantees pixel-perfect output.
"""

import re
import os
import sys
import datetime
from docxtpl import DocxTemplate

# ─── Configuration ───────────────────────────────────────────────────────────

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prepaidtemplate_tpl.docx")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

BILLER_IDS = {
    "1": "1260357626",
    "2": "1264602129",
    "3": "1624036027",
}

BILLER_LABELS = {
    "1": "1260357626 (default)",
    "2": "1264602129 (alternative 1)",
    "3": "1624036027 (alternative 2)",
}

BLOCKS_PER_PAGE = 6  # 3 rows × 2 columns

# ─── Address Parsing ─────────────────────────────────────────────────────────

INDIAN_STATES = {
    'andhra pradesh', 'arunachal pradesh', 'assam', 'bihar', 'chhattisgarh',
    'goa', 'gujarat', 'haryana', 'himachal pradesh', 'jharkhand', 'karnataka',
    'kerala', 'madhya pradesh', 'maharashtra', 'manipur', 'meghalaya', 'mizoram',
    'nagaland', 'odisha', 'orissa', 'punjab', 'rajasthan', 'sikkim',
    'tamil nadu', 'tamilnadu', 'telangana', 'tripura', 'uttar pradesh',
    'uttarakhand', 'uttaranchal', 'west bengal',
    'andaman and nicobar', 'chandigarh', 'dadra and nagar haveli',
    'daman and diu', 'delhi', 'new delhi', 'jammu and kashmir', 'jammu & kashmir',
    'ladakh', 'lakshadweep', 'puducherry', 'pondicherry',
}

STATE_MISSPELLINGS = {
    'tamilnadu': 'Tamil Nadu', 'tamil nadu': 'Tamil Nadu',
    'karnatka': 'Karnataka', 'karnataka': 'Karnataka',
    'kerela': 'Kerala', 'kerala': 'Kerala',
    'maharastra': 'Maharashtra', 'maharashtra': 'Maharashtra',
    'gujrat': 'Gujarat', 'gujarat': 'Gujarat',
    'rajastan': 'Rajasthan', 'rajasthan': 'Rajasthan',
    'utter pradesh': 'Uttar Pradesh', 'uttar pradesh': 'Uttar Pradesh',
    'madhya pradsh': 'Madhya Pradesh', 'madhya pradesh': 'Madhya Pradesh',
    'west bangal': 'West Bengal', 'west bengal': 'West Bengal',
    'andhra pradsh': 'Andhra Pradesh', 'andhra pradesh': 'Andhra Pradesh',
    'himachal pradsh': 'Himachal Pradesh', 'himachal pradesh': 'Himachal Pradesh',
    'telengana': 'Telangana', 'telangana': 'Telangana',
    'chhatisgarh': 'Chhattisgarh', 'chhattisgarh': 'Chhattisgarh',
    'jharkand': 'Jharkhand', 'jharkhand': 'Jharkhand',
    'uttrakhand': 'Uttarakhand', 'uttarakhand': 'Uttarakhand',
    'odisa': 'Odisha', 'odisha': 'Odisha', 'orissa': 'Odisha',
    'punjab': 'Punjab', 'panjab': 'Punjab',
    'haryana': 'Haryana', 'hariyana': 'Haryana',
    'delhi': 'Delhi', 'new delhi': 'New Delhi',
    'pondicherry': 'Puducherry', 'puducherry': 'Puducherry',
}

NAME_PATTERNS = [
    r'(?:n+a*m+e*\s*[:;-]\s*)(.*)',
    r'(?:n+[aem]{1,3}e*\s*[:;-]\s*)(.*)',
]
ADDRESS_PATTERNS = [
    r'(?:a+d+[dr]*e*s+\s*[:;-]\s*)(.*)',
    r'(?:a+d+[dr]*[aeiou]*s+\s*[:;-]\s*)(.*)',
]
PINCODE_PATTERNS = [
    r'(?:p+i*n+\s*(?:c+o*d+e*)?\s*[:;-]\s*)(.*)',
    r'(?:p+o*s*t*a*l*\s*c+o*d+e*\s*[:;-]\s*)(.*)',
    r'(?:z+i*p+\s*(?:c+o*d+e*)?\s*[:;-]\s*)(.*)',
]
STATE_PATTERNS = [
    r'(?:s+t+a+t+e*\s*[:;-]\s*)(.*)',
]
PHONE_PATTERNS = [
    r'(?:(?:p+h+o*n+e*|f+o+n+e*)\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    r'(?:m+o+b+[ile]*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    r'(?:c+o*n*t+a*c*t*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    r'(?:c+e+l+l*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    r'(?:w+h*a+t*s*a+p+\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    r'(?:(?:mob|ph|phn)\s*[:;-]\s*)(.*)',
]


def fuzzy_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def is_indian_state(text):
    cleaned = text.strip().lower()
    if cleaned in INDIAN_STATES or cleaned in STATE_MISSPELLINGS:
        return True
    for state in INDIAN_STATES:
        if len(cleaned) >= 3 and len(state) >= 3:
            if cleaned in state or state in cleaned:
                return True
    return False


def normalize_state(text):
    cleaned = text.strip().lower()
    if cleaned in STATE_MISSPELLINGS:
        return STATE_MISSPELLINGS[cleaned]
    return text.strip().title()


def abbreviate_order(text):
    if not text:
        return text
    replacements = [
        (r'(?<![a-zA-Z])vit(?:amin)?\s*c\s*face\s*wash\b', 'Vit C FW'),
        (r'(?<![a-zA-Z])vit(?:amin)?\s*c\s*facewash\b', 'Vit C FW'),
        (r'(?<![a-zA-Z])body\s*lotion\b', 'BL'),
        (r'(?<![a-zA-Z])face\s*wash\b', 'FW'),
        (r'(?<![a-zA-Z])facewash\b', 'FW'),
        (r'(?<![a-zA-Z])cxe\b', 'CXE'),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result.upper()


def parse_address_block(raw_text):
    """Parse a raw WhatsApp address block into structured fields."""
    lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]

    result = {'name': '', 'address': '', 'pincode': '', 'state': '', 'phone': '', 'order': ''}
    consumed = [False] * len(lines)
    address_lines = []
    address_started = False

    for i, line in enumerate(lines):
        val = fuzzy_match(line, NAME_PATTERNS)
        if val and not result['name']:
            result['name'] = val
            consumed[i] = True
            continue

        val = fuzzy_match(line, PINCODE_PATTERNS)
        if val:
            result['pincode'] = re.sub(r'[^\d]', '', val)[:6]
            consumed[i] = True
            address_started = False
            continue

        val = fuzzy_match(line, STATE_PATTERNS)
        if val:
            result['state'] = normalize_state(val)
            consumed[i] = True
            address_started = False
            continue

        val = fuzzy_match(line, PHONE_PATTERNS)
        if val:
            result['phone'] = re.sub(r'[^\d+]', '', val)
            consumed[i] = True
            address_started = False
            continue

        val = fuzzy_match(line, ADDRESS_PATTERNS)
        if val:
            address_lines = [val]
            consumed[i] = True
            address_started = True
            continue

        if is_indian_state(line) and not result['state']:
            result['state'] = normalize_state(line)
            consumed[i] = True
            address_started = False
            continue

        if re.match(r'^\d{6}$', line.strip()) and not result['pincode']:
            result['pincode'] = line.strip()
            consumed[i] = True
            address_started = False
            continue

        if re.match(r'^\+?\d[\d\s-]{8,}\d$', line.strip()) and not result['phone']:
            digits = re.sub(r'[^\d+]', '', line)
            if len(digits) >= 10:
                result['phone'] = digits
                consumed[i] = True
                address_started = False
                continue

        if address_started and not consumed[i]:
            is_label = any(fuzzy_match(line, p) is not None
                           for p in [NAME_PATTERNS, PINCODE_PATTERNS, STATE_PATTERNS, PHONE_PATTERNS])
            if not is_label:
                address_lines.append(line)
                consumed[i] = True
                continue
            else:
                address_started = False

    last_consumed_idx = max((i for i in range(len(lines)) if consumed[i]), default=-1)

    order_lines = []
    for i, line in enumerate(lines):
        if not consumed[i]:
            if i > last_consumed_idx:
                order_lines.append(line)
            else:
                address_lines.append(line)

    if not result['name'] and address_lines:
        result['name'] = address_lines[0]
        address_lines = address_lines[1:]

    result['address'] = ', '.join(address_lines) if address_lines else ''
    result['order'] = abbreviate_order(', '.join(order_lines)) if order_lines else ''

    return result


# ─── DOCX Generation using docxtpl ───────────────────────────────────────────

MAX_LINE_LEN = 40  # chars per line in the address block at sz=24


def build_address_lines(addr):
    """Build up to 7 address lines from parsed address fields."""
    lines = []

    if addr['name']:
        lines.append(addr['name'])

    if addr['address']:
        text = addr['address']
        while len(text) > MAX_LINE_LEN:
            break_at = text.rfind(',', 0, MAX_LINE_LEN)
            if break_at == -1:
                break_at = text.rfind(' ', 0, MAX_LINE_LEN)
            if break_at == -1:
                break_at = MAX_LINE_LEN
            lines.append(text[:break_at + 1].strip())
            text = text[break_at + 1:].strip()
        if text:
            lines.append(text)

    if addr['pincode']:
        lines.append(f"Pin: {addr['pincode']}")

    if addr['state']:
        lines.append(addr['state'])

    if addr['phone']:
        lines.append(f"Mob: {addr['phone']}")

    # Merge overflow into last line if more than 7
    if len(lines) > 7:
        lines = lines[:6] + [', '.join(lines[6:])]

    # Pad to exactly 7 lines with empty strings
    while len(lines) < 7:
        lines.append('')

    return lines


def create_address_document(addresses, biller_id, template_path=None):
    """
    Fill a docxtpl template for one PAGE (up to 6 addresses).
    Returns a rendered DocxTemplate object.
    """
    if template_path is None:
        template_path = TEMPLATE_PATH

    # We generate one page at a time (6 blocks per page)
    # For multiple pages we create multiple docs and merge (or just return a list)
    # For now: handle multiple pages by creating separate files or using python-docx merge

    # Build context for all 6 block slots
    context = {}
    block_order = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]

    for slot_idx in range(6):
        b = f"b{slot_idx}"
        if slot_idx < len(addresses):
            addr = addresses[slot_idx]
            lines = build_address_lines(addr)
        else:
            lines = [''] * 7

        for line_idx, line_text in enumerate(lines, 1):
            context[f"{b}_l{line_idx}"] = line_text

        # Order text on the left of "From:" line
        order = addresses[slot_idx].get('order', '') if slot_idx < len(addresses) else ''
        context[f"{b}_order"] = order

        context[f"{b}_biller"] = f"Biller ID: {biller_id}"

    doc = DocxTemplate(template_path)
    doc.render(context)
    return doc


def create_address_document_multipage(addresses, biller_id, output_path, template_path=None):
    """
    Generate the full output DOCX for all addresses (multiple pages if needed).
    For simplicity: generate one file per page, then combine using python-docx.
    """
    import copy
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    if template_path is None:
        template_path = TEMPLATE_PATH

    num_pages = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE

    if num_pages == 1:
        doc = create_address_document(addresses[:6], biller_id, template_path)
        doc.save(output_path)
        return

    # Multiple pages: render each page and merge tables into one doc
    import tempfile, os

    page_files = []
    for page_idx in range(num_pages):
        start = page_idx * BLOCKS_PER_PAGE
        page_addrs = addresses[start:start + BLOCKS_PER_PAGE]
        doc = create_address_document(page_addrs, biller_id, template_path)
        tmp = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)
        tmp.close()
        doc.save(tmp.name)
        page_files.append(tmp.name)

    # Merge: take first page as base, append tables from subsequent pages
    base = DocxDocument(page_files[0])
    base_body = base.element.body

    for page_file in page_files[1:]:
        extra = DocxDocument(page_file)
        extra_body = extra.element.body

        # Add page break paragraph
        pg_break = parse_xml(
            f'<w:p {nsdecls("w")}>'
            f'  <w:pPr><w:sectPr>'
            f'    <w:pgSz w:w="11906" w:h="16838"/>'
            f'    <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/>'
            f'  </w:sectPr></w:pPr>'
            f'</w:p>'
        )
        # Insert before sectPr
        sect = base_body.find(qn('w:sectPr'))
        if sect is not None:
            sect.addprevious(pg_break)
        else:
            base_body.append(pg_break)

        # Copy table from extra page
        for tbl in extra_body.findall(qn('w:tbl')):
            tbl_copy = copy.deepcopy(tbl)
            if sect is not None:
                sect.addprevious(tbl_copy)
            else:
                base_body.append(tbl_copy)

    # Clean up temp files
    for f in page_files:
        os.unlink(f)

    base.save(output_path)


# ─── PDF Conversion ──────────────────────────────────────────────────────────

def convert_to_pdf(docx_path, pdf_path):
    """Convert DOCX to PDF using docx2pdf (requires MS Word on Windows)."""
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return True
    except Exception as e:
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True
        print(f"\n⚠️  PDF conversion error: {e}")
        return False


# ─── Main Interactive Loop ────────────────────────────────────────────────────

def print_banner():
    print()
    print("+" + "=" * 62 + "+")
    print("|         CREAM X EMIRATES - Address Printer              |")
    print("|                Prepaid Label Automation                  |")
    print("+" + "=" * 62 + "+")
    print()


def print_parsed_address(addr, index):
    print(f"\n  [OK] Address #{index} parsed:")
    print(f"     Name    : {addr['name'] or '(empty)'}")
    print(f"     Address : {addr['address'] or '(empty)'}")
    print(f"     Pincode : {addr['pincode'] or '(empty)'}")
    print(f"     State   : {addr['state'] or '(empty)'}")
    print(f"     Phone   : {addr['phone'] or '(empty)'}")
    print(f"     Order   : {addr.get('order') or '(empty)'}")


def print_address_list(addresses):
    if not addresses:
        print("\n  [LIST] No addresses entered yet.")
        return
    print(f"\n  [LIST] Current Address List ({len(addresses)} total):")
    print("  " + "-" * 58)
    for i, addr in enumerate(addresses, 1):
        name = addr['name'] or '(no name)'
        address = addr['address'] or '(no address)'
        if len(address) > 40:
            address = address[:37] + "..."
        print(f"  #{i:>2}  {name}")
        print(f"       {address}")
        print(f"       Pin: {addr['pincode'] or '----'} | {addr['state'] or '----'} | Ph: {addr['phone'] or '----'}")
        print(f"       Order: {addr.get('order') or '----'}")
        print("  " + "-" * 58)
    pages = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE
    print(f"  Pages needed: {pages} ({BLOCKS_PER_PAGE} addresses per page)")


def handle_delete(addresses, command):
    parts = command.split()
    if len(parts) != 2:
        print("\n  [ERROR] Usage: delete N (example: delete 3)")
        return
    try:
        index = int(parts[1])
    except ValueError:
        print("\n  [ERROR] Invalid number.")
        return
    if index < 1 or index > len(addresses):
        print(f"\n  [ERROR] Invalid address number. Valid range: 1 to {len(addresses)}")
        return
    removed = addresses.pop(index - 1)
    print(f"\n  [DELETED] Address #{index}: {removed['name'] or '(no name)'}")
    print(f"  Total addresses: {len(addresses)}")


def main():
    print_banner()

    while True:
        user_input = input("Type 'start' to begin a new batch: ").strip().lower()
        if user_input == 'start':
            break
        elif user_input in ('quit', 'exit'):
            print("Goodbye!")
            return
        else:
            print("  [ERROR] Please type 'start' to begin or 'exit' to quit.")

    print("\n[SETUP] Started new batch setup.")
    print("\n  Choose biller option:")
    print("  1 - 1260357626 (default)")
    print("  2 - 1264602129 (alternative 1)")
    print("  3 - 1624036027 (alternative 2)")

    while True:
        choice = input("\n  Send: 1, 2, or 3: ").strip()
        if choice in BILLER_IDS:
            biller_id = BILLER_IDS[choice]
            print(f"\n  [OK] Biller ID set to: {biller_id} ({BILLER_LABELS[choice]})")
            break
        else:
            print("  [ERROR] Invalid choice. Please enter 1, 2, or 3.")

    addresses = []
    print("\n" + "-" * 62)
    print("Paste customer addresses below.")
    print("   * Press ENTER on an empty line to submit each address")
    print("   * Commands: stop / list / undo / delete N")
    print("-" * 62)

    while True:
        print(f"\nAddress #{len(addresses) + 1} (or type 'stop' / 'list' / 'undo' / 'delete N'):")
        lines = []
        empty_count = 0
        stripped = ''

        while True:
            try:
                line = input()
            except EOFError:
                break

            stripped = line.strip().lower()
            if not lines:
                if stripped in ('stop', 'undo', 'list'):
                    break
                if stripped.startswith('delete '):
                    break

            if line.strip() == '':
                empty_count += 1
                if empty_count >= 1 and lines:
                    break
                continue
            else:
                empty_count = 0
                lines.append(line)

        if not lines:
            if stripped == 'stop':
                if not addresses:
                    print("\n  [WARNING] No addresses entered. Nothing to generate.")
                    continue
                break
            elif stripped == 'list':
                print_address_list(addresses)
                continue
            elif stripped == 'undo':
                if addresses:
                    removed = addresses.pop()
                    print(f"\n  [UNDO] Removed last address: {removed['name']}")
                    print(f"  Total addresses: {len(addresses)}")
                else:
                    print("\n  [WARNING] No addresses to undo.")
                continue
            elif stripped.startswith('delete '):
                handle_delete(addresses, stripped)
                continue
            else:
                continue

        raw_text = '\n'.join(lines)
        parsed = parse_address_block(raw_text)
        addresses.append(parsed)
        print_parsed_address(parsed, len(addresses))
        print(f"\n  Total addresses: {len(addresses)}")
        pages_needed = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE
        print(f"  Pages needed: {pages_needed} ({BLOCKS_PER_PAGE} addresses per page)")

    # Generate output
    print("\n" + "=" * 62)
    print(f"[GENERATING] Document with {len(addresses)} addresses...")
    print(f"   Biller ID: {biller_id}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    docx_path = os.path.join(OUTPUT_DIR, f"addresses_{timestamp}.docx")
    pdf_path = os.path.join(OUTPUT_DIR, f"addresses_{timestamp}.pdf")

    create_address_document_multipage(addresses, biller_id, docx_path)
    print(f"\n  [SAVED] DOCX: {docx_path}")

    print(f"  [CONVERTING] To PDF...")
    success = convert_to_pdf(docx_path, pdf_path)

    if success:
        print(f"  [DONE] PDF saved: {pdf_path}")
        try:
            os.startfile(pdf_path)
        except Exception:
            pass
    else:
        print(f"  [INFO] Open the DOCX manually: {docx_path}")


if __name__ == '__main__':
    main()
