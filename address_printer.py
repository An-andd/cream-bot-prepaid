"""
Prepaid Address Printer Automation
===================================
Automates printing of customer addresses from WhatsApp messages
into a DOCX template with 6 address blocks per page, then exports to PDF.

Usage:
    python address_printer.py

Flow:
    1. Type 'start' to begin a session
    2. Choose a biller ID (1, 2, or 3)
    3. Paste customer addresses (press Enter twice after each address)
    4. Type 'stop' to generate the PDF output
"""

import re
import os
import sys
import copy
import datetime
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from lxml import etree

# ─── Configuration ───────────────────────────────────────────────────────────

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prepaidtemplate.docx")
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

# Indian states and union territories (for auto-detection without label)
INDIAN_STATES = {
    'andhra pradesh', 'arunachal pradesh', 'assam', 'bihar', 'chhattisgarh',
    'goa', 'gujarat', 'haryana', 'himachal pradesh', 'jharkhand', 'karnataka',
    'kerala', 'madhya pradesh', 'maharashtra', 'manipur', 'meghalaya', 'mizoram',
    'nagaland', 'odisha', 'orissa', 'punjab', 'rajasthan', 'sikkim',
    'tamil nadu', 'tamilnadu', 'telangana', 'tripura', 'uttar pradesh',
    'uttarakhand', 'uttaranchal', 'west bengal',
    # Union territories
    'andaman and nicobar', 'chandigarh', 'dadra and nagar haveli',
    'daman and diu', 'delhi', 'new delhi', 'jammu and kashmir', 'jammu & kashmir',
    'ladakh', 'lakshadweep', 'puducherry', 'pondicherry',
}

# Common misspellings of states
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


def is_indian_state(text):
    """Check if a text line is an Indian state name (fuzzy)."""
    cleaned = text.strip().lower()
    # Direct match
    if cleaned in INDIAN_STATES:
        return True
    # Check misspellings
    if cleaned in STATE_MISSPELLINGS:
        return True
    # Fuzzy: check if the text is very close to a known state
    for state in INDIAN_STATES:
        # Simple similarity: if >80% of characters match
        if len(cleaned) >= 3 and len(state) >= 3:
            if cleaned in state or state in cleaned:
                return True
    return False


def normalize_state(text):
    """Normalize a state name to its correct spelling."""
    cleaned = text.strip().lower()
    if cleaned in STATE_MISSPELLINGS:
        return STATE_MISSPELLINGS[cleaned]
    # Return original with title case
    return text.strip().title()


# Fuzzy patterns for field detection (handles ALL spelling mistakes)
# Each pattern list covers many misspellings:
#   name -> nam, nme, naem, namee, naam, etc.
#   address -> adress, addres, addrss, addresss, adres, adrss, etc.
#   pincode -> pincod, pincode, pin code, pincde, pinncode, etc.
#   state -> stat, sate, statte, etc.
#   phone -> phne, phn, fone, phon, etc.

NAME_PATTERNS = [
    r'(?:n+a*m+e*\s*[:;-]\s*)(.*)',                     # name, nam, namee, naam
    r'(?:n+[aem]{1,3}e*\s*[:;-]\s*)(.*)',               # naem, nme, nmae, nae
]

ADDRESS_PATTERNS = [
    r'(?:a+d+[dr]*e*s+\s*[:;-]\s*)(.*)',                # address, adress, addres, addrss, addresss
    r'(?:a+d+[dr]*[aeiou]*s+\s*[:;-]\s*)(.*)',          # adres, adrss, addrs
]

PINCODE_PATTERNS = [
    r'(?:p+i*n+\s*(?:c+o*d+e*)?\s*[:;-]\s*)(.*)',       # pin, pincode, pincod, pincde, pinncode
    r'(?:p+o*s*t*a*l*\s*c+o*d+e*\s*[:;-]\s*)(.*)',      # postal code, postalcode, postl code
    r'(?:z+i*p+\s*(?:c+o*d+e*)?\s*[:;-]\s*)(.*)',       # zip, zipcode, zipcod
]

STATE_PATTERNS = [
    r'(?:s+t+a+t+e*\s*[:;-]\s*)(.*)',                   # state, stat, sate, statte, staet
]

PHONE_PATTERNS = [
    # phone, phon, phne, phn, fone, fon
    r'(?:(?:p+h+o*n+e*|f+o+n+e*)\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    # mobile, moble, mobil, moblie, mob
    r'(?:m+o+b+[ile]*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    # contact, contct, cntact, contac
    r'(?:c+o*n*t+a*c*t*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    # cell, cel
    r'(?:c+e+l+l*\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    # whatsapp, watsapp, whatsap, watsap
    r'(?:w+h*a+t*s*a+p+\s*(?:n+o\.?|n+u*m*b*e*r*)?\s*[:;-]\s*)(.*)',
    # short: mob:, ph:, phn:
    r'(?:(?:mob|ph|phn)\s*[:;-]\s*)(.*)',
]


def fuzzy_match(text, patterns):
    """Try to match text against multiple fuzzy regex patterns (case-insensitive)."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def abbreviate_order(text):
    """Abbreviate common product names."""
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
    return result


def parse_address_block(raw_text):
    """
    Parse a raw WhatsApp address block into structured fields.
    
    Handles:
    - Spelling mistakes in field labels
    - Multi-line addresses
    - Various phone number label variations
    - Indian state names without labels
    - Standalone pincode numbers
    - Order info (remaining text after all address fields)
    - Missing fields (returns empty string)
    """
    lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]
    
    result = {
        'name': '',
        'address': '',
        'pincode': '',
        'state': '',
        'phone': '',
        'order': '',
    }
    
    # Track which lines are consumed
    consumed = [False] * len(lines)
    address_lines = []
    address_started = False
    
    for i, line in enumerate(lines):
        # Try Name
        val = fuzzy_match(line, NAME_PATTERNS)
        if val and not result['name']:
            result['name'] = val
            consumed[i] = True
            continue
        
        # Try Pincode (labeled)
        val = fuzzy_match(line, PINCODE_PATTERNS)
        if val:
            result['pincode'] = re.sub(r'[^\d]', '', val)[:6]  # Extract digits, max 6
            consumed[i] = True
            address_started = False
            continue
        
        # Try State (labeled)
        val = fuzzy_match(line, STATE_PATTERNS)
        if val:
            result['state'] = normalize_state(val)
            consumed[i] = True
            address_started = False
            continue
        
        # Try Phone
        val = fuzzy_match(line, PHONE_PATTERNS)
        if val:
            result['phone'] = re.sub(r'[^\d+]', '', val)  # Keep digits and +
            consumed[i] = True
            address_started = False
            continue
        
        # Try Address (start)
        val = fuzzy_match(line, ADDRESS_PATTERNS)
        if val:
            address_lines = [val]
            consumed[i] = True
            address_started = True
            continue
        
        # Check if the line is a standalone Indian state name (no label)
        if is_indian_state(line) and not result['state']:
            result['state'] = normalize_state(line)
            consumed[i] = True
            address_started = False
            continue
        
        # Check if the line is a standalone pincode (6 digits)
        if re.match(r'^\d{6}$', line.strip()) and not result['pincode']:
            result['pincode'] = line.strip()
            consumed[i] = True
            address_started = False
            continue
        
        # Check if the line is a standalone phone number (10+ digits)
        if re.match(r'^\+?\d[\d\s-]{8,}\d$', line.strip()) and not result['phone']:
            digits = re.sub(r'[^\d+]', '', line)
            if len(digits) >= 10:
                result['phone'] = digits
                consumed[i] = True
                address_started = False
                continue
        
        # If address was started and this line doesn't match any label,
        # treat it as continuation of address
        if address_started and not consumed[i]:
            # Check if this line looks like it might be a label for something else
            is_label = False
            for patterns in [NAME_PATTERNS, PINCODE_PATTERNS, STATE_PATTERNS, PHONE_PATTERNS]:
                if fuzzy_match(line, patterns) is not None:
                    is_label = True
                    break
            
            if not is_label:
                address_lines.append(line)
                consumed[i] = True
                continue
            else:
                address_started = False
    
    # Separate remaining unconsumed lines into address vs order info.
    # Lines AFTER the last consumed line are treated as order info.
    # Lines BETWEEN consumed lines are treated as address continuation.
    last_consumed_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if consumed[i]:
            last_consumed_idx = i
            break
    
    order_lines = []
    for i, line in enumerate(lines):
        if not consumed[i]:
            if i > last_consumed_idx:
                # After all recognized fields -> order info
                order_lines.append(line)
            else:
                # Between recognized fields -> address continuation
                address_lines.append(line)
    
    # If no name was explicitly labeled, assume the first address line is the name
    if not result['name'] and address_lines:
        result['name'] = address_lines[0]
        address_lines = address_lines[1:]
        
    # Also, break the address into multiple lines instead of one giant string
    # so it naturally wraps better in the template
    result['address'] = ', '.join(address_lines) if address_lines else ''
    order_text = ', '.join(order_lines) if order_lines else ''
    result['order'] = abbreviate_order(order_text)
    
    return result


# ─── DOCX Generation ─────────────────────────────────────────────────────────

def create_address_document(addresses, biller_id, template_path):
    """
    Create a DOCX document by cloning the template structure and filling in addresses.
    
    Each page has 6 blocks (3 rows × 2 columns).
    Each block has:
        - To: (customer name + address + pincode)
        - From: (CREAM X EMIRATES, PUTHUPALLY, KTM, Pin: 686011, Mob: 8129770502)
        - Biller ID
    """
    # Load the template to clone its structure
    template_doc = Document(template_path)
    
    # Get the template table (the one with 6 blocks)
    template_table = template_doc.tables[0]
    
    # Calculate number of pages needed
    num_pages = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE
    
    # Create a new document
    doc = Document(template_path)
    
    # Get the XML body
    body = doc.element.body
    
    # Remove existing table from the new document
    existing_tables = body.findall(qn('w:tbl'))
    for t in existing_tables:
        body.remove(t)
    
    # Remove all paragraphs except the section properties
    existing_paras = body.findall(qn('w:p'))
    for p in existing_paras:
        body.remove(p)
    
    # Get the section properties (page size, margins, etc.)
    sect_pr = body.find(qn('w:sectPr'))
    if sect_pr is not None:
        body.remove(sect_pr)
    
    # Get the original template table XML for cloning
    template_body = template_doc.element.body
    original_table = template_body.findall(qn('w:tbl'))[0]
    original_sect_pr = template_body.find(qn('w:sectPr'))
    
    for page_idx in range(num_pages):
        start_idx = page_idx * BLOCKS_PER_PAGE
        page_addresses = addresses[start_idx:start_idx + BLOCKS_PER_PAGE]
        
        # Clone the template table
        new_table = copy.deepcopy(original_table)
        
        # CRITICAL: Force all row heights to EXACT so rows NEVER expand
        # This guarantees 3 rows always fit on one page = 6 labels per page
        rows = new_table.findall(qn('w:tr'))
        for row in rows:
            trPr = row.find(qn('w:trPr'))
            if trPr is None:
                trPr = parse_xml(f'<w:trPr {nsdecls("w")}></w:trPr>')
                row.insert(0, trPr)
            trHeight = trPr.find(qn('w:trHeight'))
            if trHeight is not None:
                trHeight.set(qn('w:hRule'), 'exact')
            else:
                trHeight = parse_xml(f'<w:trHeight {nsdecls("w")} w:val="4526" w:hRule="exact"/>')
                trPr.append(trHeight)
        
        # Fill in the addresses
        block_idx = 0
        
        for row in rows:
            cells = row.findall(qn('w:tc'))
            for cell in cells:
                if block_idx < len(page_addresses):
                    addr = page_addresses[block_idx]
                    fill_cell(cell, addr, biller_id)
                else:
                    # Clear unused blocks (leave empty "To:" section)
                    clear_cell_to_section(cell, biller_id)
                block_idx += 1
        
        # Add the table to the document body
        body.append(new_table)
        
        # Add page break between pages (not after the last page)
        if page_idx < num_pages - 1:
            # Create a section break paragraph
            p = parse_xml(
                f'<w:p {nsdecls("w")}>'
                f'  <w:pPr>'
                f'    <w:sectPr>'
                f'      <w:pgSz w:w="11906" w:h="16838" w:orient="portrait"/>'
                f'      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="708" w:footer="708"/>'
                f'    </w:sectPr>'
                f'  </w:pPr>'
                f'</w:p>'
            )
            body.append(p)
    
    # Add final section properties
    final_sect = copy.deepcopy(original_sect_pr)
    body.append(final_sect)
    
    return doc


def fill_cell(cell, addr, biller_id):
    """Fill a single cell (block) with customer address data."""
    paragraphs = cell.findall(qn('w:p'))
    
    # Cell structure (14 paragraphs) — template original:
    # Para 0:    "To:" header          (sz=28)  — untouched
    # Para 1-7:  Customer address       (sz=24 filled / sz=28 empty)
    # Para 8:    [items][spaces]"From:" (sz=28)  — items inserted on LEFT
    # Para 9:    [spaces]"CREAM X ..."  (sz=24)  — KEEP TEMPLATE
    # Para 10:   [spaces]"PUTHUPALLY"   (sz=24)  — KEEP TEMPLATE
    # Para 11:   [spaces]"Pin: 686011"  (sz=24)  — KEEP TEMPLATE
    # Para 12:   [spaces]"Mob: ..."     (sz=24)  — KEEP TEMPLATE
    # Para 13:   "Biller ID: xxx"       (sz=24)  — updated
    
    ADDR_SIZE = 24   # 12pt for filled address lines
    EMPTY_SIZE = 28  # 14pt for empty lines (matches template, fills vertical space)
    MAX_LINE_LEN = 40
    
    # Build the "To:" content lines
    to_lines = []
    
    if addr['name']:
        to_lines.append(addr['name'])
    
    if addr['address']:
        address_text = addr['address']
        while len(address_text) > MAX_LINE_LEN:
            break_at = address_text.rfind(',', 0, MAX_LINE_LEN)
            if break_at == -1:
                break_at = address_text.rfind(' ', 0, MAX_LINE_LEN)
            if break_at == -1:
                break_at = MAX_LINE_LEN
            to_lines.append(address_text[:break_at + 1].strip())
            address_text = address_text[break_at + 1:].strip()
        if address_text:
            to_lines.append(address_text)
    
    if addr['pincode']:
        to_lines.append(f"Pin: {addr['pincode']}")
    
    if addr['state']:
        to_lines.append(addr['state'])
    
    if addr['phone']:
        to_lines.append(f"Mob: {addr['phone']}")
    
    # Cap at 7 lines — merge overflow into last line
    if len(to_lines) > 7:
        to_lines = to_lines[:6] + [', '.join(to_lines[6:])]
    
    # Fill paragraphs 1-7 with customer address data
    for i in range(1, 8):
        if i - 1 < len(to_lines):
            # Filled line: use sz=24 for readability
            set_paragraph_text(paragraphs[i], to_lines[i - 1], 
                             bold=True, size=ADDR_SIZE, color="000000")
        else:
            # Empty line: use sz=28 (template size) to fill vertical space
            # This eliminates the gap below Biller ID
            set_paragraph_text(paragraphs[i], "", 
                             bold=True, size=EMPTY_SIZE, color="000000")
    
    # Para 8: Insert items on the LEFT side of the "From:" line
    # This keeps paras 9-12 (CREAM X, PUTHUPALLY, Pin, Mob) perfectly aligned
    if addr.get('order'):
        order_text = addr['order']
        orig_text = get_paragraph_text(paragraphs[8])
        
        # Original: "                                                From:"
        # New:      "1CXE                                            From:"
        leading_spaces = len(orig_text) - len(orig_text.lstrip())
        spaces_to_remove = int(len(order_text) * 1.5)
        new_spaces = max(5, leading_spaces - spaces_to_remove)
        
        new_text = order_text + (" " * new_spaces) + orig_text.lstrip()
        set_paragraph_text(paragraphs[8], new_text, bold=True, size=28, color="000000")
    
    # Paras 9-12: KEEP ORIGINAL TEMPLATE TEXT — do not modify
    # This preserves perfect alignment of From section
    
    # Para 13: Update Biller ID (left-aligned, matching template)
    set_paragraph_text(paragraphs[13], f"Biller ID: {biller_id}",
                      bold=True, size=24, color="000000")


def clear_cell_to_section(cell, biller_id):
    """Clear the To: section of a cell but keep From: and update Biller ID."""
    paragraphs = cell.findall(qn('w:p'))
    
    # Clear address paragraphs 1-7 with template size (sz=28)
    for i in range(1, 8):
        if i < len(paragraphs):
            set_paragraph_text(paragraphs[i], "",
                             bold=True, size=28, color="000000")
    
    # Paras 8-12: KEEP ORIGINAL TEMPLATE TEXT — do not modify
    
    # Update Biller ID only
    if len(paragraphs) > 13:
        set_paragraph_text(paragraphs[13], f"Biller ID: {biller_id}",
                          bold=True, size=24, color="000000")


def get_paragraph_text(paragraph):
    """Extract raw text from a paragraph's XML runs."""
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    texts = []
    for t in paragraph.findall('.//w:t', ns):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)

def set_paragraph_text(paragraph, text, bold=False, size=None, color=None, align=None):
    """Set the text of a paragraph, preserving the paragraph properties but replacing runs.
    align: 'left', 'right', 'center', or None to keep existing."""
    
    # Set paragraph alignment if specified
    if align:
        pPr = paragraph.find(qn('w:pPr'))
        if pPr is None:
            pPr = parse_xml(f'<w:pPr {nsdecls("w")}></w:pPr>')
            paragraph.insert(0, pPr)
        # Remove existing alignment
        existing_jc = pPr.find(qn('w:jc'))
        if existing_jc is not None:
            pPr.remove(existing_jc)
        # Add new alignment
        jc = parse_xml(f'<w:jc {nsdecls("w")} w:val="{align}"/>')
        pPr.append(jc)
    
    # Remove all existing runs
    runs = paragraph.findall(qn('w:r'))
    for r in runs:
        paragraph.remove(r)
    
    # Create new run with text
    new_run = parse_xml(f'<w:r {nsdecls("w")}></w:r>')
    
    # Build run properties
    rpr_xml = f'<w:rPr {nsdecls("w")}>'
    if bold:
        rpr_xml += '<w:b w:val="1"/><w:bCs w:val="1"/>'
    if size:
        rpr_xml += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    if color:
        rpr_xml += f'<w:color w:val="{color}"/>'
    rpr_xml += '<w:rtl w:val="0"/>'
    rpr_xml += '</w:rPr>'
    
    rpr = parse_xml(rpr_xml)
    new_run.append(rpr)
    
    # Create text element
    t = parse_xml(f'<w:t {nsdecls("w")} xml:space="preserve">{escape_xml(text)}</w:t>')
    new_run.append(t)
    
    paragraph.append(new_run)


def escape_xml(text):
    """Escape special XML characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


# ─── PDF Conversion ──────────────────────────────────────────────────────────

def convert_to_pdf(docx_path, pdf_path):
    """Convert DOCX to PDF using docx2pdf (requires MS Word on Windows)."""
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return True
    except Exception as e:
        # docx2pdf sometimes throws a COM error when closing Word,
        # but the PDF is still generated successfully
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True
        print(f"\n⚠️  PDF conversion error: {e}")
        print(f"    The DOCX file has been saved at: {docx_path}")
        print(f"    You can manually convert it to PDF using MS Word.")
        return False


# ─── Main Interactive Loop ────────────────────────────────────────────────────

def print_banner():
    """Print a nice startup banner."""
    print()
    print("+" + "=" * 62 + "+")
    print("|         CREAM X EMIRATES - Address Printer              |")
    print("|                Prepaid Label Automation                  |")
    print("+" + "=" * 62 + "+")
    print()


def print_parsed_address(addr, index):
    """Print a nicely formatted parsed address for confirmation."""
    print(f"\n  [OK] Address #{index} parsed:")
    print(f"     Name    : {addr['name'] or '(empty)'}")
    print(f"     Address : {addr['address'] or '(empty)'}")
    print(f"     Pincode : {addr['pincode'] or '(empty)'}")
    print(f"     State   : {addr['state'] or '(empty)'}")
    print(f"     Phone   : {addr['phone'] or '(empty)'}")
    print(f"     Order   : {addr.get('order') or '(empty)'}")


def print_address_list(addresses):
    """Print a formatted list of all entered addresses."""
    if not addresses:
        print("\n  [LIST] No addresses entered yet.")
        return
    
    print(f"\n  [LIST] Current Address List ({len(addresses)} total):")
    print("  " + "-" * 58)
    
    for i, addr in enumerate(addresses, 1):
        name = addr['name'] or '(no name)'
        address = addr['address'] or '(no address)'
        pincode = addr['pincode'] or '----'
        state = addr['state'] or '----'
        phone = addr['phone'] or '----'
        
        # Truncate long addresses for display
        if len(address) > 40:
            address = address[:37] + "..."
        
        order = addr.get('order') or '----'
        
        print(f"  #{i:>2}  {name}")
        print(f"       {address}")
        print(f"       Pin: {pincode} | {state} | Ph: {phone}")
        print(f"       Order: {order}")
        print("  " + "-" * 58)
    
    pages = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE
    print(f"  Pages needed: {pages} ({BLOCKS_PER_PAGE} addresses per page)")


def handle_delete(addresses, command):
    """Handle the 'delete N' command to remove a specific address."""
    parts = command.split()
    if len(parts) != 2:
        print("\n  [ERROR] Usage: delete N (example: delete 3)")
        return
    
    try:
        index = int(parts[1])
    except ValueError:
        print("\n  [ERROR] Invalid number. Usage: delete N (example: delete 3)")
        return
    
    if index < 1 or index > len(addresses):
        print(f"\n  [ERROR] Invalid address number. Valid range: 1 to {len(addresses)}")
        return
    
    removed = addresses.pop(index - 1)
    print(f"\n  [DELETED] Address #{index}: {removed['name'] or '(no name)'}")
    print(f"  Total addresses: {len(addresses)}")


def main():
    print_banner()
    
    # Wait for 'start' command
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
    
    # Collect addresses
    addresses = []
    print("\n" + "-" * 62)
    print("Paste customer addresses below.")
    print("   * Paste the full address from WhatsApp")
    print("   * Press ENTER on an empty line to submit each address")
    print("")
    print("   Commands (type on empty line):")
    print("   * stop         -> Generate PDF and finish")
    print("   * list         -> Show all entered addresses")
    print("   * undo         -> Remove the last address")
    print("   * delete N     -> Remove address number N")
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
            
            # Check for commands (only when no address lines entered yet)
            stripped = line.strip().lower()
            if not lines:
                if stripped in ('stop', 'undo', 'list'):
                    break
                if stripped.startswith('delete '):
                    break
            
            if line.strip() == '':
                empty_count += 1
                if empty_count >= 1 and lines:
                    # One empty line after content = submit this address
                    break
                continue
            else:
                empty_count = 0
                lines.append(line)
        
        # Handle commands
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
        
        # Parse the address
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
    pages = (len(addresses) + BLOCKS_PER_PAGE - 1) // BLOCKS_PER_PAGE
    print(f"   Pages: {pages}")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    docx_filename = f"addresses_{timestamp}.docx"
    pdf_filename = f"addresses_{timestamp}.pdf"
    docx_path = os.path.join(OUTPUT_DIR, docx_filename)
    pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)
    
    # Create DOCX
    doc = create_address_document(addresses, biller_id, TEMPLATE_PATH)
    doc.save(docx_path)
    print(f"\n  [SAVED] DOCX: {docx_path}")
    
    # Convert to PDF
    print(f"  [CONVERTING] To PDF...")
    success = convert_to_pdf(docx_path, pdf_path)
    
    if success:
        print(f"  [SAVED] PDF: {pdf_path}")
    
    print("\n" + "=" * 62)
    print("[DONE] Your address labels are ready!")
    print("=" * 62)
    
    # Ask if they want to start another batch
    print()
    again = input("Start another batch? (yes/no): ").strip().lower()
    if again in ('yes', 'y', 'start'):
        main()  # Recursive call for another batch
    else:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
