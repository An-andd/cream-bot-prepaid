#!/usr/bin/env python3
"""Generate labels without WhatsApp.

    python cli.py samples/sample_paste.txt -o labels.pdf --biller option1
    python cli.py --woo 25 -o labels.pdf
    python cli.py samples/sample_paste.txt --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys

from app import config
from app.labels import render_pdf
from app.parsing import parse_orders


def main() -> int:
    ap = argparse.ArgumentParser(description="Build prepaid shipping labels.")
    ap.add_argument("input", nargs="?", help="text file with pasted addresses ('-' for stdin)")
    ap.add_argument("-o", "--output", default="labels.pdf")
    ap.add_argument("--biller", default="option1", help="option1 | option2 | option3 | raw id")
    ap.add_argument("--woo", type=int, metavar="N", help="pull N prepaid WooCommerce orders")
    ap.add_argument("--docx", action="store_true", help="also write a .docx version")
    ap.add_argument("--dry-run", action="store_true", help="print parsed JSON, write nothing")
    args = ap.parse_args()

    orders = []
    if args.input:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        orders.extend(parse_orders(raw))
    if args.woo:
        from app import woo as woo_mod
        orders.extend(woo_mod.fetch_prepaid_orders(limit=args.woo))
    if not orders:
        ap.error("no input: give a file, '-' for stdin, or --woo N")

    usable = [o for o in orders if o.is_usable()]
    for order in orders:
        if not order.is_usable():
            print(f"SKIPPED (too little info): {order.summary()}", file=sys.stderr)
        elif order.missing():
            print(f"WARNING {order.summary()}: missing {', '.join(order.missing())}",
                  file=sys.stderr)

    if args.dry_run:
        print(json.dumps([o.to_dict() for o in usable], indent=2, ensure_ascii=False))
        return 0

    table = config.billers()
    biller_id = table.get(args.biller.lower(), {}).get("id", args.biller)

    render_pdf(usable, biller_id, args.output)
    pages = (len(usable) + config.LABELS_PER_PAGE - 1) // config.LABELS_PER_PAGE
    print(f"{len(usable)} labels on {pages} page(s) -> {args.output}")

    if args.docx:
        from app.labels_docx import render_docx
        docx_path = args.output.rsplit(".", 1)[0] + ".docx"
        render_docx(usable, biller_id, docx_path)
        print(f"also wrote {docx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
