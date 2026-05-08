import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

def create_address_pdf(addresses, biller_id, pdf_path):
    # A4: 210mm x 297mm
    # Increase margins to prevent page spillover
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=8*mm,
        leftMargin=8*mm,
        topMargin=8*mm,
        bottomMargin=8*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles - slightly smaller fonts to ensure they fit in the box
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
        fontSize=12,  # Name slightly larger
        leading=15
    )
    
    style_from = ParagraphStyle(
        'CustomFrom',
        parent=style_normal,
        alignment=TA_LEFT, # Left aligned text, but placed on the right side
        fontSize=10,
        leading=13
    )

    style_order = ParagraphStyle(
        'CustomOrder',
        parent=style_normal,
        fontSize=11,
        leading=14
    )
    
    blocks_per_page = 6
    elements = []
    
    for i in range(0, len(addresses), blocks_per_page):
        chunk = addresses[i:i+blocks_per_page]
        
        while len(chunk) < 6:
            chunk.append(None)
            
        data = []
        for row_idx in range(3):
            row_data = []
            for col_idx in range(2):
                addr = chunk[row_idx * 2 + col_idx]
                if addr is None:
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
                
                # From Block - Text is left aligned, but placed in the right column
                from_text = (
                    "From:<br/>"
                    "CREAM X EMIRATES<br/>"
                    "PUTHUPALLY, KTM<br/>"
                    "Pin: 686011<br/>"
                    "Mob: 8129770502"
                )
                from_para = Paragraph(from_text, style_from)
                
                biller_para = Paragraph(f"Biller ID: {biller_id}", style_normal)
                
                # Create a sub-table for the bottom section
                # Left column: Order (top) + Biller ID (bottom)
                # Right column: From block
                left_bottom_data = [
                    [order_para],
                    [biller_para]
                ]
                left_bottom_table = Table(left_bottom_data, colWidths=[45*mm])
                left_bottom_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ]))

                bottom_data = [
                    [left_bottom_table, from_para]
                ]
                bottom_table = Table(bottom_data, colWidths=[45*mm, 45*mm])
                bottom_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ]))
                
                # Main cell layout: Top row for address, Bottom row for bottom_table
                # Lock row heights so they NEVER push the bounding box down
                cell_data = [
                    [to_para],
                    [bottom_table]
                ]
                cell_table = Table(cell_data, colWidths=[90*mm], rowHeights=[60*mm, 25*mm])
                cell_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (0,0), 'TOP'),
                    ('VALIGN', (0,1), (0,1), 'BOTTOM'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                ]))
                
                row_data.append(cell_table)
            data.append(row_data)
            
        # Create the main 3x2 grid table
        # Usable height = 297 - 16 = 281mm. 3 rows of 92mm = 276mm (Fits perfectly!)
        main_table = Table(data, colWidths=[95*mm, 95*mm], rowHeights=[92*mm, 92*mm, 92*mm])
        main_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 2*mm),
        ]))
        
        elements.append(main_table)
        
    doc.build(elements)
