import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT

def create_address_pdf(addresses, biller_id, pdf_path):
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=10*mm,
        leftMargin=10*mm,
        topMargin=10*mm,
        bottomMargin=10*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    style_normal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13, # Line spacing
        textColor=colors.black
    )
    
    style_name = ParagraphStyle(
        'CustomName',
        parent=style_normal,
        fontSize=12,
        leading=15
    )
    
    style_from = ParagraphStyle(
        'CustomFrom',
        parent=style_normal,
        alignment=TA_RIGHT,
        fontSize=9,
        leading=12
    )

    style_order = ParagraphStyle(
        'CustomOrder',
        parent=style_normal,
        fontSize=11,
        leading=14
    )
    
    blocks_per_page = 6
    elements = []
    
    # Process addresses into blocks of 6
    for i in range(0, len(addresses), blocks_per_page):
        chunk = addresses[i:i+blocks_per_page]
        
        # We need a 3x2 grid. Pad chunk to 6 if necessary.
        while len(chunk) < 6:
            chunk.append(None)
            
        data = []
        for row_idx in range(3):
            row_data = []
            for col_idx in range(2):
                addr = chunk[row_idx * 2 + col_idx]
                if addr is None:
                    # Empty cell layout (just the From and Biller ID)
                    to_para = Paragraph("", style_normal)
                    order_para = Paragraph("", style_order)
                else:
                    # Build "To" block
                    to_text = "To:<br/>"
                    if addr['name']:
                        to_text += f"<font size=12>{addr['name']}</font><br/>"
                    if addr['address']:
                        to_text += f"{addr['address']}<br/>"
                    if addr['pincode']:
                        to_text += f"Pin: {addr['pincode']}<br/>"
                    if addr['state']:
                        to_text += f"{addr['state']}<br/>"
                    if addr['phone']:
                        to_text += f"Mob: {addr['phone']}"
                        
                    to_para = Paragraph(to_text, style_normal)
                    order_para = Paragraph(addr['order'] if addr['order'] else "", style_order)
                
                # From Block
                from_text = (
                    "From:<br/>"
                    "CREAM X EMIRATES<br/>"
                    "PUTHUPALLY, KTM<br/>"
                    "Pin: 686011<br/>"
                    "Mob: 8129770502"
                )
                from_para = Paragraph(from_text, style_from)
                
                biller_para = Paragraph(f"Biller ID: {biller_id}", style_normal)
                
                # Create a sub-table for the bottom section (Order/Biller on left, From on right)
                bottom_data = [
                    [order_para, from_para],
                    [biller_para, ""]
                ]
                bottom_table = Table(bottom_data, colWidths=[45*mm, 45*mm])
                bottom_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                    ('ALIGN', (1,0), (1,-1), 'RIGHT'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ]))
                
                # Main cell table
                cell_data = [
                    [to_para],
                    [Spacer(1, 10*mm)], # spacer to push bottom block down
                    [bottom_table]
                ]
                cell_table = Table(cell_data, colWidths=[90*mm])
                cell_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (0,0), 'TOP'),
                    ('VALIGN', (0,2), (0,2), 'BOTTOM'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ]))
                
                row_data.append(cell_table)
            data.append(row_data)
            
        # Create the main 3x2 grid table
        # A4 height is 297mm. Margins are 20mm. Usable height is 277mm.
        # 3 rows = 277 / 3 = 92.33mm per row.
        main_table = Table(data, colWidths=[95*mm, 95*mm], rowHeights=[92*mm, 92*mm, 92*mm])
        main_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 3*mm),
        ]))
        
        elements.append(main_table)
        
    doc.build(elements)
