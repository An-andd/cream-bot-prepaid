"""Test with exact user addresses - generate DOCX for preview."""
import os, sys
sys.path.insert(0, '.')
from address_printer import parse_address_block, create_address_document_multipage

raw_addrs = [
    "Name: Shalini V\nAddress: Lakshmi appartment,athreyapuram main road,sriramapuram,gangai amman Kovil Street choolaimedu\nLakshmi appartment house no 27 B block\nChennai\nPincode: 600094\nState: Tamilnadu\nPhone number: 9790551399\n\n1CXe",
    "Name: Aneeta To\nAddress: Pallithode panchayath palam\nThachedath house\nCherthala\nPincode: 688540\nState: Kerala\nPhone number: 9778263247\n\n1CXe",
    "Name: Praveen A\nAddress: Boys hostel\nDhanalakshmi Srinivasan university\nSamayapuram Trichy\nPincode: 621112\nState: Tamilnadu\nPhone number: 9894748079\n\n3CXe",
    "Name: Hema S\nAddress: 21/15 ews nh3,rajaji street,MARAIMALAINAGAR\nChengalpattu\nPincode: 603209\nState: Tamilnadu\nPhone number: 7200624821\n\n2CXe",
    "Name: Dhatchitha Prakash\nAddress: No.14, Kattabomman Street, Parasakthi Nagar\nPareri, Singaperumal Koil\nPincode: 603204\nState: Tamilnadu\nPhone number: 8610100680\n\n1CXe",
    "Name: Vinothini Kamal\nAddress: Maruthi Suzuki showroom, nattamangalam\nSalem\nPincode: 636452\nState: Tamilnadu\nPhone number: 6381396653\n\n1CXe",
    "Name: Durga suresh\nAddress: PLOTNO.25 THULASI NAGAR\nOLD SURAMANGALAM SALEM\nPincode: 636005\nPhone number: 9344070553\n\n2cxe",
]

addrs = [parse_address_block(a) for a in raw_addrs]

print(f"Parsed {len(addrs)} addresses:")
for i, a in enumerate(addrs, 1):
    name = a['name'] or '(empty)'
    to_lines_count = 0
    if a['name']: to_lines_count += 1
    # Count how many lines address would split into
    addr_text = a['address']
    while len(addr_text) > 40:
        to_lines_count += 1
        break_at = addr_text.rfind(',', 0, 40)
        if break_at == -1: break_at = addr_text.rfind(' ', 0, 40)
        if break_at == -1: break_at = 40
        addr_text = addr_text[break_at + 1:].strip()
    if addr_text: to_lines_count += 1
    if a['pincode']: to_lines_count += 1
    if a['state']: to_lines_count += 1
    if a['phone']: to_lines_count += 1
    print(f"  #{i} {name} - {to_lines_count} lines, order='{a.get('order','')}'")

os.makedirs('output', exist_ok=True)
create_address_document_multipage(addrs, '1260357626', 'output/test_final.docx')
print(f"\nSaved: output/test_final.docx")
