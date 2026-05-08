import zipfile
from xml.etree import ElementTree as ET

z = zipfile.ZipFile('prepaidtemplate.docx')
content = z.read('word/document.xml')
root = ET.fromstring(content)
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def twips_to_mm(t):
    return round(float(t) * 25.4 / 1440, 2)

print('Page: 210.01mm x 297.0mm')
print('Margins: top=12.7mm, bottom=12.7mm, left=12.7mm, right=12.7mm')

table = root.findall('.//w:tbl', ns)[0]
tblPr = table.find('w:tblPr', ns)
tblW = tblPr.find('w:tblW', ns)
w_val = tblW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')
print(f'Table width: {w_val} twips = {twips_to_mm(w_val)}mm')

rows = table.findall('w:tr', ns)
print(f'Number of rows: {len(rows)}')
for ri, row in enumerate(rows):
    cells = row.findall('w:tc', ns)
    trPr = row.find('w:trPr', ns)
    if trPr is not None:
        trH = trPr.find('w:trHeight', ns)
        if trH is not None:
            hval = trH.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
            if hval:
                print(f'Row {ri} height: {twips_to_mm(hval)}mm')
    for ci, cell in enumerate(cells):
        tcPr = cell.find('w:tcPr', ns)
        if tcPr is not None:
            tcW = tcPr.find('w:tcW', ns)
            if tcW is not None:
                w = tcW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')
                print(f'  Cell[{ri}][{ci}] width: {twips_to_mm(w)}mm')
            tcMar = tcPr.find('w:tcMar', ns)
            if tcMar is not None:
                for side in ['top','bottom','left','right']:
                    el = tcMar.find(f'w:{side}', ns)
                    if el is not None:
                        v = el.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')
                        if v: print(f'    margin-{side}: {twips_to_mm(v)}mm')
        paras = cell.findall('w:p', ns)
        print(f'  Cell[{ri}][{ci}]: {len(paras)} paragraphs')
        for pi, p in enumerate(paras[:16]):
            runs = p.findall('.//w:r', ns)
            text = ''.join([r.find('.//w:t', ns).text or '' for r in runs if r.find('.//w:t', ns) is not None])
            pPr = p.find('w:pPr', ns)
            sz_val = None
            spacing = {}
            if pPr is not None:
                sp = pPr.find('w:spacing', ns)
                if sp is not None:
                    spacing = {k.split('}')[1]:v for k,v in sp.attrib.items()}
                rPr = pPr.find('w:rPr', ns)
                if rPr is not None:
                    sz = rPr.find('w:sz', ns)
                    if sz is not None:
                        sz_val = sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
            else:
                runs2 = p.findall('.//w:r', ns)
                for r in runs2:
                    rpr = r.find('w:rPr', ns)
                    if rpr is not None:
                        sz = rpr.find('w:sz', ns)
                        if sz is not None:
                            sz_val = sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            break
            print(f'    Para {pi}: [{text[:35]}] sz={sz_val} spacing={spacing}')
