from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

def create_address_pdf(addresses, biller_id, pdf_path):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    
    margin_x = 10 * mm
    margin_y = 10 * mm
    
    cell_w = (width - 2 * margin_x) / 2
    cell_h = (height - 2 * margin_y) / 3
    
    blocks_per_page = 6
    num_pages = (len(addresses) + blocks_per_page - 1) // blocks_per_page
    
    for page in range(num_pages):
        for i in range(6):
            idx = page * 6 + i
            
            row = i // 2
            col = i % 2
            
            x = margin_x + col * cell_w
            y = height - margin_y - (row + 1) * cell_h
            
            # Draw cell border
            c.rect(x, y, cell_w, cell_h)
            
            if idx < len(addresses):
                addr = addresses[idx]
                
                # Setup font
                c.setFont("Helvetica-Bold", 12)
                
                # To block
                text_y = y + cell_h - 10 * mm
                c.drawString(x + 5*mm, text_y, "To:")
                
                text_y -= 6 * mm
                if addr['name']:
                    c.drawString(x + 5*mm, text_y, addr['name'])
                    text_y -= 6 * mm
                if addr['address']:
                    # Wrap address
                    import textwrap
                    lines = textwrap.wrap(addr['address'], width=40)
                    for line in lines:
                        c.drawString(x + 5*mm, text_y, line)
                        text_y -= 6 * mm
                if addr['pincode']:
                    c.drawString(x + 5*mm, text_y, f"Pin: {addr['pincode']}")
                    text_y -= 6 * mm
                if addr['state']:
                    c.drawString(x + 5*mm, text_y, addr['state'])
                    text_y -= 6 * mm
                if addr['phone']:
                    c.drawString(x + 5*mm, text_y, f"Mob: {addr['phone']}")
                    
                # From block (right side)
                from_x = x + cell_w / 2 + 10*mm
                from_y = y + 40 * mm
                
                c.drawString(from_x, from_y, "From:")
                c.drawString(from_x, from_y - 6*mm, "CREAM X EMIRATES")
                c.drawString(from_x, from_y - 12*mm, "PUTHUPALLY, KTM")
                c.drawString(from_x, from_y - 18*mm, "Pin: 686011")
                c.drawString(from_x, from_y - 24*mm, "Mob: 8129770502")
                
                # Order Info (Left side, aligned with Pin of From block)
                if addr['order']:
                    c.drawString(x + 5*mm, from_y - 18*mm, addr['order'])
                    
                # Biller ID (Bottom left)
                c.drawString(x + 5*mm, y + 5*mm, f"Biller ID: {biller_id}")
                
            else:
                # Print empty block with From and Biller ID
                c.setFont("Helvetica-Bold", 12)
                
                from_x = x + cell_w / 2 + 10*mm
                from_y = y + 40 * mm
                
                c.drawString(from_x, from_y, "From:")
                c.drawString(from_x, from_y - 6*mm, "CREAM X EMIRATES")
                c.drawString(from_x, from_y - 12*mm, "PUTHUPALLY, KTM")
                c.drawString(from_x, from_y - 18*mm, "Pin: 686011")
                c.drawString(from_x, from_y - 24*mm, "Mob: 8129770502")
                
                c.drawString(x + 5*mm, y + 5*mm, f"Biller ID: {biller_id}")
                
        c.showPage()
    c.save()
