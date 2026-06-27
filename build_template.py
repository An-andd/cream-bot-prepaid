"""
build_template.py
=================
Builds 'prepaidtemplate_tpl.docx' from 'kunjii.docx'.

Strategy:
  - Cell[0][0] supplies Paras 0-4 (To:, name, addr, pin/mob, blank).
  - Cell[0][1] supplies the From section (Paras 7-12) — its spacing is correct
    (Cell[0][0]'s CREAM X EMIRATES has 85 chars which wraps; Cell[0][1] has 73).
  - We INSERT 2 extra address line paragraphs (a2, a3) after Para 2 so the
    address is displayed across 3 separate lines instead of one long wrapped line.
  - We INSERT 2 blank gap paragraphs between the address block and the order line.

Final para structure per cell (15 paragraphs):
      0:  "To:"                           <- untouched
      1:  {{ bN_name }}
      2:  {{ bN_a1 }}                     <- address line 1 (street)
      3:  {{ bN_a2 }}                     <- address line 2 (area/landmark)
      4:  {{ bN_a3 }}                     <- address line 3 (city, state)
      5:  {{ bN_pin }}{{ bN_mob }}
      6:  "" blank gap 1                  <- inserted
      7:  "" blank gap 2                  <- inserted
      8:  {{ bN_order }}                  <- product line e.g. "3CXE"
      9:  "[spaces]From:"                 <- from Cell[0][1], untouched
     10:  "[spaces]CREAM X EMIRATES"      <- from Cell[0][1], untouched
     11:  "[spaces]PUTHUPALLY, KTM"       <- untouched
     12:  "[spaces]Pin: 686011"           <- untouched
     13:  "[spaces]Mob: 8129770502"       <- untouched
     14:  {{ bN_biller }}
"""

import copy
from docx import Document
from docx.oxml.ns import qn

TEMPLATE_IN  = 'kunjii.docx'
TEMPLATE_OUT = 'prepaidtemplate_tpl.docx'


def get_text(para):
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    return ''.join(t.text or '' for t in para.findall('.//w:t', ns))


def set_para_text(para, new_text, ref_run=None):
    """
    Set the text of a paragraph's first run, preserving formatting.
    If the paragraph has no runs, clone ref_run (inherits font/size).
    """
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    runs = para.findall(qn('w:r'))
    if not runs:
        if ref_run is not None:
            new_run = copy.deepcopy(ref_run)
            t_ex = new_run.find(qn('w:t'))
            if t_ex is not None:
                new_run.remove(t_ex)
        else:
            new_run = parse_xml(f'<w:r {nsdecls("w")}></w:r>')
        para.append(new_run)
        runs = [new_run]

    first_run = runs[0]
    for r in runs[1:]:
        para.remove(r)

    t_el = first_run.find(qn('w:t'))
    if t_el is None:
        from docx.oxml.ns import nsdecls as nd
        t_el = parse_xml(f'<w:t {nd("w")} xml:space="preserve"></w:t>')
        first_run.append(t_el)

    t_el.text = new_text
    t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def build_cell(cell_xml, ref_addr_paras, ref_from_paras, b):
    """
    Build one label cell:
      ref_addr_paras  — Paras 0-4 from Cell[0][0] (To:, name, addr, pin/mob, blank)
      ref_from_paras  — Paras 7-12 from Cell[0][1] (From section with correct spacing)
    """
    # Remove all existing paragraphs
    for p in cell_xml.findall(qn('w:p')):
        cell_xml.remove(p)

    # --- Address section: copy Paras 0-4 from Cell[0][0] ---
    # Para 0: To:     (copy as-is)
    # Para 1: name    (will set placeholder)
    # Para 2: addr1   (will set placeholder)
    # Para 3: pin/mob (will set placeholder) — we clone this to make addr2, addr3
    # Para 4: blank   (will be used for blank gaps and order)
    for src in ref_addr_paras:
        cell_xml.append(copy.deepcopy(src))

    paras = cell_xml.findall(qn('w:p'))
    # paras[0]=To:  [1]=name  [2]=addr  [3]=pin/mob  [4]=blank

    # Get a reference run for formatting (from name para)
    ref_run = paras[1].findall(qn('w:r'))
    ref_run = ref_run[0] if ref_run else None

    # Set name placeholder
    set_para_text(paras[1], f'{{{{ {b}_name }}}}')

    # Set addr line 1 placeholder (use original Para 2)
    set_para_text(paras[2], f'{{{{ {b}_a1 }}}}')

    # Insert addr line 2 (clone of Para 2) BEFORE Para 3
    addr2 = copy.deepcopy(paras[2])
    paras[3].addprevious(addr2)
    # Insert addr line 3 (clone of Para 2) BEFORE Para 3
    addr3 = copy.deepcopy(paras[2])
    paras[3].addprevious(addr3)

    # Refresh — paras[3] is now addr2, paras[4] is addr3, paras[5] is old pin/mob, paras[6] is blank
    paras = cell_xml.findall(qn('w:p'))
    set_para_text(paras[3], f'{{{{ {b}_a2 }}}}', ref_run=ref_run)
    set_para_text(paras[4], f'{{{{ {b}_a3 }}}}', ref_run=ref_run)

    # Para 5 (original Para 3): pin + mob
    set_para_text(paras[5], f'{{{{ {b}_pin }}}}{{{{ {b}_mob }}}}')

    # Para 6 (original Para 4): blank — insert 2 more blank lines before it for gap
    blank_gap = paras[6]  # this is the blank para
    gap1 = copy.deepcopy(blank_gap)
    gap2 = copy.deepcopy(blank_gap)
    blank_gap.addprevious(gap1)
    blank_gap.addprevious(gap2)

    # Refresh — gap1=Para6, gap2=Para7, blank_gap=Para8 (becomes order)
    paras = cell_xml.findall(qn('w:p'))
    # Para 8 = original blank -> set as order
    set_para_text(paras[8], f'{{{{ {b}_order }}}}', ref_run=ref_run)

    # --- From section: copy Paras 7-12 from Cell[0][1] ---
    # These have the correct spacing (73 chars for CREAM X EMIRATES, not 85)
    for src in ref_from_paras:
        cell_xml.append(copy.deepcopy(src))

    # The biller ID is the LAST paragraph (index 14)
    paras = cell_xml.findall(qn('w:p'))
    set_para_text(paras[14], f'{{{{ {b}_biller }}}}')

    return len(paras)


def main():
    doc = Document(TEMPLATE_IN)
    table = doc.tables[0]

    # --- Extract reference paragraphs ---
    # Cell[0][0]: address section (Paras 0-4: To:, name, addr, pin/mob, blank)
    cell00_xml = table.rows[0].cells[0]._tc
    all00 = cell00_xml.findall(qn('w:p'))
    ref_addr_paras = all00[0:5]   # Paras 0-4

    # Cell[0][1]: From section (Paras 7-12: From:, CREAM, PUTHUPALLY, Pin, Mob, BillerID)
    cell01_xml = table.rows[0].cells[1]._tc
    all01 = cell01_xml.findall(qn('w:p'))
    ref_from_paras = all01[7:13]  # Paras 7-12 (From section with correct spacing)

    print('Reference addr paras (from Cell[0][0]):')
    for i, p in enumerate(ref_addr_paras):
        print(f'  [{i}] {repr(get_text(p)[:60])}')
    print('Reference From paras (from Cell[0][1]):')
    for i, p in enumerate(ref_from_paras):
        print(f'  [{i+7}] {repr(get_text(p)[:70])}')

    # --- Build all 6 cells ---
    block_positions = [(0,0),(0,1),(1,0),(1,1),(2,0),(2,1)]
    for block_idx, (ri, ci) in enumerate(block_positions):
        b = f'b{block_idx}'
        cell_xml = table.rows[ri].cells[ci]._tc
        n = build_cell(cell_xml, ref_addr_paras, ref_from_paras, b)
        print(f'  Block {block_idx} ({ri},{ci}) -> {n} paras')

    doc.save(TEMPLATE_OUT)
    print(f'\n[DONE] Saved: {TEMPLATE_OUT}')

    # --- Verify ---
    print('\n--- Verification ---')
    doc2 = Document(TEMPLATE_OUT)
    table2 = doc2.tables[0]
    for block_idx, (ri, ci) in enumerate(block_positions):
        paras = table2.rows[ri].cells[ci].paragraphs
        n = len(paras)
        p = lambda i: paras[i].text[:28] if n > i else '?'
        print(
            f'  Block {block_idx} ({n}p): '
            f'name=[{p(1)}] a1=[{p(2)}] a2=[{p(3)}] a3=[{p(4)}] '
            f'pin=[{p(5)}] order=[{p(8)}] biller=[{p(14)}]'
        )


if __name__ == '__main__':
    main()
