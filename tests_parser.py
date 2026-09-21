#!/usr/bin/env python3
"""Regression tests built from the real labels in the reference PDF."""
from app.parsing import normalize_phones, parse_orders

PASTE = open("samples/sample_paste.txt", encoding="utf-8").read()
ORDERS = {o.name.lower(): o for o in parse_orders(PASTE)}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok -", msg)


def run():
    check(len(ORDERS) == 22, f"22 customers parsed (got {len(ORDERS)})")

    o = ORDERS["ilakkiya"]
    check(o.phones == ["6374177133", "8111013566"], "two phone numbers preserved")
    check(o.address_lines == ["2/165 mpk valasai", "Kumparam (post)"],
          "multi-line address preserved")
    check(o.district == "Ramanathapuram" and o.state == "Tamilnadu",
          "District and State on one line are split")

    check(ORDERS["rekhavargeesh"].pincode == "629702", "pincode with a space is joined")
    check(ORDERS["a.dhivakar"].note.lower() == "return", "'Return' captured as a note")
    check(ORDERS["sindhu"].note.lower() == "forgot", "'Forgot' captured as a note")
    check(ORDERS["rajadurai p"].note.lower() == "mistake", "'Mistake' captured as a note")
    check(ORDERS["sajitha souparnika"].note.lower() == "dtdc", "'Dtdc' captured as a note")
    check(ORDERS["nithya's"].items == ["10cxe"], "10cxe (two-digit qty) parsed")
    check(ORDERS["sangeetha b"].items == ["5cxe"], "5cxe parsed")

    d = ORDERS["dileepan"]
    check("CROCODILE STORE F24-A 1ST FLOOR" in d.address_lines
          and "BROOKFIELD'S MALL Dr.KRISHNASAMY ROAD" in d.address_lines
          and d.place == "Near petrol bunk Apposite"
          and d.district == "COIMBATORE",
          "long multi-line store address is never truncated")

    check(ORDERS["sindhu"].phones == ["7483634534"], "duplicated 'Phone number:' label handled")
    check(ORDERS["shabana"].phones == ["7025723830"], "unlabelled bare phone number found")
    check(ORDERS["c. vinodhini"].name == "C. Vinodhini", "'To\\n:Name:' quirk handled")
    check(ORDERS["padmavathi"].address_lines[0].startswith("10/m"),
          "'10/m ...' is an address, not a product")
    check(ORDERS["guna p"].items == ["1cxe"]
          and ORDERS["guna p"].address_lines[0].startswith("No 43"),
          "'No 43 mullai 4th cross street' is not read as a product")

    check(normalize_phones("+91 63741 77133") == ["6374177133"], "country code stripped")
    check(normalize_phones("9876543210 / 9123456789") ==
          ["9876543210", "9123456789"], "slash-separated numbers kept")
    check(normalize_phones("09876543210") == ["9876543210"], "leading zero stripped")

    for name, order in ORDERS.items():
        check(order.is_usable(), f"{name} is printable")

    print("\nAll parser tests passed.")


if __name__ == "__main__":
    run()
