from docx import Document
from docx.oxml.ns import qn

doc = Document('output/test_final.docx')
table = doc.tables[0]
rows = table._tbl.findall(qn('w:tr'))
cells = rows[0].findall(qn('w:tc'))
cell = cells[0]
paras = cell.findall(qn('w:p'))

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
print('=== Rendered Block 0 ===')
for i in range(0, 14):
    p = paras[i]
    texts = ''.join(t.text for t in p.findall('.//w:t', ns) if t.text)
    sz_els = p.findall('.//w:sz', ns)
    sz = sz_els[0].get(qn('w:val')) if sz_els else 'inherit'
    b_els = p.findall('.//w:b', ns)
    bold = 'Y' if b_els else 'N'
    print(f'Para {i:2d}: sz={sz:>4s} bold={bold}  [{texts[:55]}]')
