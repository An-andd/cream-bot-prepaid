"""
Create a new prepaidtemplate_tpl.docx with placeholders injected
into the blank address lines (paras 1-7 and para 8's left side).
We copy ALL formatting from the original template exactly.
Run this ONCE to create the template, then docxtpl fills it at runtime.
"""
import copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from lxml import etree

src = Document('prepaidtemplate.docx')
table_src = src.tables[0]

# We work directly on the source and save as new file
doc = Document('prepaidtemplate.docx')
table = doc.tables[0]

rows = table._tbl.findall(qn('w:tr'))

# Block positions: 2 cols × 3 rows = 6 blocks
# We'll set placeholders for each block slot (b0..b5)
# Each block: line1..line7 = address lines, order = item, biller = biller id

for block_idx, (row_i, col_i) in enumerate([(0,0),(0,1),(1,0),(1,1),(2,0),(2,1)]):
    row = rows[row_i]
    cells = row.findall(qn('w:tc'))
    cell = cells[col_i]
    paras = cell.findall(qn('w:p'))
    
    b = f"b{block_idx}"  # e.g. b0, b1, ...
    
    # Para 1-7: Set placeholder text, keep ALL original formatting
    placeholders = [
        f"{{{{ {b}_l1 }}}}",
        f"{{{{ {b}_l2 }}}}",
        f"{{{{ {b}_l3 }}}}",
        f"{{{{ {b}_l4 }}}}",
        f"{{{{ {b}_l5 }}}}",
        f"{{{{ {b}_l6 }}}}",
        f"{{{{ {b}_l7 }}}}",
    ]
    
    for i, placeholder in enumerate(placeholders, 1):
        p = paras[i]
        # Find the run and replace its text
        runs = p.findall(qn('w:r'))
        if runs:
            # Use first run, set its text to placeholder
            t = runs[0].find(qn('w:t'))
            if t is None:
                t = parse_xml(f'<w:t {nsdecls("w")} xml:space="preserve"></w:t>')
                runs[0].append(t)
            t.text = placeholder
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            # Remove extra runs
            for r in runs[1:]:
                p.remove(r)
        else:
            # No run exists - create one matching para 1's formatting
            ref_run = paras[1].findall(qn('w:r'))
            if ref_run:
                new_r = copy.deepcopy(ref_run[0])
                t = new_r.find(qn('w:t'))
                if t is None:
                    t = parse_xml(f'<w:t {nsdecls("w")} xml:space="preserve"></w:t>')
                    new_r.append(t)
                t.text = placeholder
                t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                p.append(new_r)
    
    # Para 8: Replace "From:" line with "{{b0_order}}[spaces]From:"
    # Keep exact spacing — just prepend the order placeholder
    p8 = paras[8]
    runs8 = p8.findall(qn('w:r'))
    if runs8:
        t = runs8[0].find(qn('w:t'))
        orig_text = t.text if t is not None else ""
        # orig_text is like "                                                From:"
        # Replace with placeholder + spaces + From:
        new_text = f"{{{{ {b}_order }}}}" + orig_text  # prepend placeholder
        t.text = new_text
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    
    # Para 13: Replace "Biller ID: 1260357626" with placeholder
    p13 = paras[13]
    runs13 = p13.findall(qn('w:r'))
    if runs13:
        t = runs13[0].find(qn('w:t'))
        if t is not None:
            t.text = f"{{{{ {b}_biller }}}}"
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

doc.save('prepaidtemplate_tpl.docx')
print("Created prepaidtemplate_tpl.docx with placeholders!")

# Verify by printing all para texts
doc2 = Document('prepaidtemplate_tpl.docx')
table2 = doc2.tables[0]
rows2 = table2._tbl.findall(qn('w:tr'))
cells2 = rows2[0].findall(qn('w:tc'))
cell2 = cells2[0]
paras2 = cell2.findall(qn('w:p'))
print("\nBlock 0 paragraphs:")
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
for i, p in enumerate(paras2):
    texts = [t.text for t in p.findall('.//w:t', ns) if t.text]
    print(f"  Para {i}: {''.join(texts)[:80]}")
