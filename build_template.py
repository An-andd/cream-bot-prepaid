"""
build_template.py
=================
Builds 'prepaidtemplate_tpl.docx' from 'kunjii.docx'.

Strategy:
  - Cell[0][0] is the REFERENCE cell (has the correct 11-para structure + formatting).
  - We deep-copy it into ALL 6 cells, then INSERT 2 blank gap paragraphs between
    the address block (pin/mob) and the order line, giving a 2-line visual gap.
  - Final para structure per cell (13 paragraphs after insertion):
      0:  "To:"                              <- untouched
      1:  name placeholder                   <- {{ bN_name }}
      2:  address placeholder                <- {{ bN_addr }}
      3:  pin + mob line                     <- {{ bN_pin }}{{ bN_mob }}
      4:  "" (blank gap 1)                   <- inserted
      5:  "" (blank gap 2)                   <- inserted
      6:  order items line                   <- {{ bN_order }}  (e.g. "3CXe", "1 CXE, 1 BL")
      7:  "        From:"                    <- untouched
      8:  "        CREAM X EMIRATES "        <- untouched
      9:  "        PUTHUPALLY, KTM"          <- untouched
     10:  "        Pin: 686011"              <- untouched
     11:  "        Mob: 8129770502"          <- untouched
     12:  "Biller ID: ..."                   <- {{ bN_biller }}
"""

import copy
from docx import Document
from docx.oxml.ns import qn

TEMPLATE_IN  = 'kunjii.docx'
TEMPLATE_OUT = 'prepaidtemplate_tpl.docx'


def get_full_text(para):
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    return ''.join(t.text or '' for t in para.findall('.//w:t', ns))


def set_para_text(para, new_text, ref_run=None):
    """
    Replace text in a paragraph's first run while preserving ALL formatting.
    Extra runs are removed. xml:space='preserve' is set.

    If the paragraph has no runs (e.g. an empty gap para), a run is cloned
    from ref_run (should be the name-run from the reference cell) so the
    order text inherits the same font/size formatting.
    """
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    runs = para.findall(qn('w:r'))

    if not runs:
        # Paragraph has no run — clone formatting from ref_run if provided
        if ref_run is not None:
            new_run = copy.deepcopy(ref_run)
            # Clear any existing <w:t> text in the cloned run
            t_existing = new_run.find(qn('w:t'))
            if t_existing is not None:
                new_run.remove(t_existing)
        else:
            # Bare minimum run with no formatting
            new_run = parse_xml(f'<w:r {nsdecls("w")}></w:r>')
        para.append(new_run)
        runs = [new_run]

    # Keep the first run, remove the rest
    first_run = runs[0]
    for r in runs[1:]:
        para.remove(r)

    # Get or create the <w:t> element
    t_el = first_run.find(qn('w:t'))
    if t_el is None:
        t_el_str = f'<w:t {nsdecls("w")} xml:space="preserve"></w:t>'
        t_el = parse_xml(t_el_str)
        first_run.append(t_el)

    t_el.text = new_text
    t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def inject_placeholders(cell_xml, cell_paras, b):
    """
    Inject Jinja2 placeholders and insert 2 blank gap paragraphs between
    the address block (pin/mob) and the order line.

    After insertion the final layout is:
      Para 0:  To:          (untouched)
      Para 1:  {{ bN_name }}
      Para 2:  {{ bN_addr }}
      Para 3:  {{ bN_pin }}{{ bN_mob }}
      Para 4:  "" (blank gap 1)  <- inserted
      Para 5:  "" (blank gap 2)  <- inserted
      Para 6:  {{ bN_order }}
      Para 7:  From:        (untouched)
      Para 8:  CREAM X EMIRATES (untouched)
      Para 9:  PUTHUPALLY   (untouched)
      Para 10: Pin: 686011  (untouched)
      Para 11: Mob: 8129770502 (untouched)
      Para 12: {{ bN_biller }}
    """
    # Para 1 -> name
    set_para_text(cell_paras[1], f'{{{{ {b}_name }}}}')
    # Para 2 -> address
    set_para_text(cell_paras[2], f'{{{{ {b}_addr }}}}')
    # Para 3 -> pin + mob
    set_para_text(cell_paras[3], f'{{{{ {b}_pin }}}}{{{{ {b}_mob }}}}')

    # --- Insert 2 blank paragraphs BEFORE Para 4 (the order slot) ---
    # Clone the gap para (Para 4, currently blank) twice and insert before it.
    blank_1 = copy.deepcopy(cell_paras[4])
    blank_2 = copy.deepcopy(cell_paras[4])
    # addprevious inserts immediately before cell_paras[4] each time:
    #   after first:  [..., 3:pin/mob, 4:blank_1, 5:cell_paras[4], 6:From, ...]
    #   after second: [..., 3:pin/mob, 4:blank_1, 5:blank_2, 6:cell_paras[4], 7:From, ...]
    cell_paras[4].addprevious(blank_1)
    cell_paras[4].addprevious(blank_2)

    # Refresh para list after insertion (cell_paras is now stale)
    new_paras = cell_xml.findall(qn('w:p'))

    # Para 6 (original Para 4) -> order
    # It has no runs, so clone the name run for correct formatting.
    ref_run = new_paras[1].findall(qn('w:r'))
    ref_run = ref_run[0] if ref_run else None
    set_para_text(new_paras[6], f'{{{{ {b}_order }}}}', ref_run=ref_run)

    # Para 12 (original Para 10) -> biller
    set_para_text(new_paras[12], f'{{{{ {b}_biller }}}}')


def main():
    doc = Document(TEMPLATE_IN)
    table = doc.tables[0]

    # Grab the reference cell (row 0, col 0) - has correct 11-para structure
    ref_cell = table.rows[0].cells[0]
    ref_cell_xml = ref_cell._tc  # the <w:tc> element
    ref_paras_xml = ref_cell_xml.findall(qn('w:p'))

    print(f"Reference cell: {len(ref_paras_xml)} paragraphs")
    for i, p in enumerate(ref_paras_xml):
        print(f"  Para {i}: [{get_full_text(p)[:60]}]")

    # Block positions: (row_idx, col_idx)
    block_positions = [
        (0, 0), (0, 1),
        (1, 0), (1, 1),
        (2, 0), (2, 1),
    ]

    for block_idx, (ri, ci) in enumerate(block_positions):
        b = f'b{block_idx}'
        cell = table.rows[ri].cells[ci]
        cell_xml = cell._tc

        # Remove all existing paragraphs from this cell
        for p in cell_xml.findall(qn('w:p')):
            cell_xml.remove(p)

        # Deep-copy the 11 paragraphs from the reference cell
        # Find where to insert (before any <w:tcPr> or at end)
        for src_para in ref_paras_xml:
            new_para = copy.deepcopy(src_para)
            cell_xml.append(new_para)

        # Now inject Jinja2 placeholders (also inserts 2 blank gap paras)
        new_paras = cell_xml.findall(qn('w:p'))
        inject_placeholders(cell_xml, new_paras, b)
        # After injection, cell has 13 paragraphs
        final_count = len(cell_xml.findall(qn('w:p')))
        print(f"  Block {block_idx} ({ri},{ci}) done -> {final_count} paras")

    doc.save(TEMPLATE_OUT)
    print(f"\n[DONE] Saved: {TEMPLATE_OUT}")

    # Verify
    print("\n--- Verification ---")
    doc2 = Document(TEMPLATE_OUT)
    table2 = doc2.tables[0]
    for block_idx, (ri, ci) in enumerate(block_positions):
        cell = table2.rows[ri].cells[ci]
        paras = cell.paragraphs
        b = f'b{block_idx}'
        p1  = paras[1].text  if len(paras) >  1 else '?'
        p2  = paras[2].text  if len(paras) >  2 else '?'
        p3  = paras[3].text  if len(paras) >  3 else '?'
        p4  = paras[4].text  if len(paras) >  4 else '?'  # blank gap 1
        p5  = paras[5].text  if len(paras) >  5 else '?'  # blank gap 2
        p6  = paras[6].text  if len(paras) >  6 else '?'  # order
        p12 = paras[12].text if len(paras) > 12 else '?'  # biller
        print(
            f"  Block {block_idx} ({len(paras)} paras): "
            f"name=[{p1[:22]}] pin/mob=[{p3[:22]}] "
            f"gap=['{p4}','{p5}'] order=[{p6[:15]}] biller=[{p12[:22]}]"
        )


if __name__ == '__main__':
    main()
