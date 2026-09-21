# Cream X Emirates — Prepaid Label Automation

WhatsApp-driven shipping-label printing for prepaid orders. You type `start`,
pick a Biller ID, paste addresses, type `stop`, and the bot replies with a
print-ready PDF: **6 labels per page, 2 columns × 3 rows, bordered**, in the
exact format you already print.

```
WhatsApp: start
   ↓
bot: choose Biller ID (option1 / option2 / option3)
   ↓
you: paste prepaid addresses (any number of messages)
   ↓
WhatsApp: stop
   ↓
bot: prepaid-labels-<timestamp>.pdf  →  print
```

---

## What is in here

| File | Purpose |
|---|---|
| `app/parsing.py` | Turns messy pasted text into structured orders. The hard part. |
| `app/labels.py` | Draws the PDF: 2×3 grid, borders, auto-fitting font. |
| `app/labels_docx.py` | Optional Word output with the same bordered 2×3 table. |
| `app/bot.py` | The `start → biller → paste → stop` conversation. |
| `app/server.py` | Flask webhook for the WhatsApp Cloud API. |
| `app/store.py` | SQLite session state (survives Render restarts). |
| `app/woo.py` | Optional: pull prepaid orders straight from WooCommerce. |
| `app/config.py` | Every setting, from environment variables. |
| `cli.py` | Build labels from a text file, no WhatsApp needed. |
| `tests_parser.py` | Regression tests built from your real labels. |

---

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your values

python tests_parser.py                                  # verify the parser
python cli.py samples/sample_paste.txt -o labels.pdf    # build a PDF
python cli.py samples/sample_paste.txt --dry-run        # see what was parsed
python -m app.server                                    # run the webhook on :5000
```

`--dry-run` is the fastest way to debug a strange address: it prints the parsed
JSON instead of writing a PDF.

---

## Deploy on Render

1. Push this repo to GitHub.
2. Render → **New → Web Service** → connect the repo. `render.yaml` is picked
   up automatically, or set it manually:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app.server:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
3. Add the environment variables from `.env.example` (Render → Environment).
   Keep `--workers 1`: the free plan has no shared disk, and one worker keeps
   the SQLite session file consistent.
4. Open `https://<your-service>.onrender.com/` — it should return
   `{"status":"ok", ...}`.

### Meta / WhatsApp setup

1. developers.facebook.com → your app → **WhatsApp → Configuration**.
2. Callback URL: `https://<your-service>.onrender.com/webhook`
3. Verify token: the same string as `WHATSAPP_VERIFY_TOKEN`.
4. Subscribe to the **messages** webhook field.
5. Copy **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`, and the access token
   → `WHATSAPP_TOKEN`. Test-number tokens expire in 24 h; generate a permanent
   System User token for daily use.
6. Put your own WhatsApp number in `ALLOWED_SENDERS` so nobody else can drive
   the bot. Leave it empty only while testing.

> Free Render instances sleep. The first message after a sleep can take ~30 s.

---

## Bot commands

| Command | Effect |
|---|---|
| `start` | Begin a batch, ask for the Biller ID |
| `option1` / `option2` / `option3` | Pick the Biller ID (or paste the raw ID) |
| *(paste)* | Add one or many addresses; repeat as much as you like |
| `list` | Show the batch with a page count |
| `undo` | Drop the last address |
| `clear` | Empty the batch, keep the Biller ID |
| `biller` | Change the Biller ID mid-batch |
| `woo` / `woo 25` | Pull the last prepaid WooCommerce orders into the batch |
| `stop` | Build the PDF and send it back |
| `cancel` | Throw the batch away |
| `help` | Command list |

After each paste the bot replies with what it understood, and flags anything
missing, e.g. `! Ilakkiya - 623523 - 1cxe - missing pincode`.

---

## What the parser handles

Everything in your reference PDF was turned into a test case
(`tests_parser.py`, 22 real customers, all passing):

- Separators `:`  `-`  `;`  `.`  `/`  `,` — `Name-A.dhivakar`, `Address. 185`,
  `Phone number; 8056010354`, `Pincode, 631207`
- Label spellings: `Phone Number`, `Mob`, `Number`, `Contact num`, `Aadress`,
  `Dist`, `Landmark`, `Village`
- Two fields on one line: `District: Ramanathapuram State: Tamilnadu`
- Trailing labels: `Theni dist.` → District: Theni
- The `To:` / `:Name:` line-break quirk
- Multi-line addresses, kept whole — the Crocodile Store label keeps all four
  of its lines
- Pincodes with a space: `629 702` → `629702`; and pincodes hidden inside an
  address line when the field is missing
- Multiple phones: `6374177133 , 8111013566`; `+91` and leading `0` stripped,
  the second number never lost
- Duplicated labels: `Phone Number: Phone number: 7483634534`
- Bare phone numbers on their own line
- Products `1cxe`, `2cxe`, `3cxe`, `5cxe`, `10cxe`, `2CXe`, `2 x cxe`, and
  non-CXE products via `Product:` or `KNOWN_PRODUCTS`
- Notes `Return`, `Forgot`, `Mistake`, `Dtdc` printed under the product
- Address lines that merely start with a number (`No 43 mullai 4th cross
  street`, `10/m marapagounder layout`) are **not** mistaken for products

Anything it cannot classify is kept as an address line rather than dropped.
Nothing is silently lost.

---

## The label

Rendered by `app/labels.py`, one cell of the 2×3 grid. The customer block
runs down the left, the sender block sits at the bottom right, as on your
printed labels:

```
+--------------------------------------------------+
| To:                                              |
| Name: Ilakkiya                                   |
| Address: 2/165 mpk valasai                       |
| Kumparam (post)                                  |
| District: Ramanathapuram                         |
| State: Tamilnadu                                 |
| Pincode: 623523                                  |
| Phone Number: 6374177133 , 8111013566            |
|                                                  |
| 1cxe                                             |
|                          From:                   |
|                          CREAM X EMIRATES        |
|                          PUTHUPALLY, KTM         |
|                          Pin: 686011             |
|                          Mob: 8129770502         |
|                          Biller ID: 1260357626   |
+--------------------------------------------------+
```

Controlled by `FROM_BLOCK_POSITION` (`right`, the default, or `below` to stack
it under the customer), `TO_COLUMN_RATIO` (how much width the left column
gets), `FROM_VALIGN` (`bottom` / `middle` / `top`) and `COLUMN_GAP_MM`.

Empty fields are skipped — no blank `Place:` or `District:` lines. Font size
starts at `BASE_FONT_SIZE` (10 pt) and shrinks automatically down to
`MIN_FONT_SIZE` (6 pt) for long addresses, so a label never overflows its box.

Tuning knobs, all environment variables: `PAGE_SIZE`, `PAGE_MARGIN_MM`,
`LABEL_PADDING_MM`, `BASE_FONT_SIZE`, `MIN_FONT_SIZE`, `FONT_NAME`,
`BORDER_WIDTH`, `DRAW_BORDER`, `PHONE_LABEL`, `FROM_BLOCK_POSITION`,
`TO_COLUMN_RATIO`, `FROM_VALIGN`, `COLUMN_GAP_MM`.

If an address is long, both columns shrink together (down to `MIN_FONT_SIZE`)
so the sender block always stays level and readable.

### Word output

Set `OUTPUT_FORMAT=both` and the bot also sends a `.docx` with the same
bordered 2×3 table. Point `DOCX_TEMPLATE` at your master template to inherit
its styles and page setup.

### A different font

Helvetica is built into every PDF reader. To use a specific TTF instead,
register it once at the top of `app/labels.py`:

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont("Cream", "fonts/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Cream-Bold", "fonts/Arial-Bold.ttf"))
```

then set `FONT_NAME=Cream` and `FONT_NAME_BOLD=Cream-Bold`.

---

## WooCommerce (optional)

Set `WOO_URL`, `WOO_CONSUMER_KEY`, `WOO_CONSUMER_SECRET` (WooCommerce →
Settings → Advanced → REST API, read permission is enough).

An order counts as prepaid when its status is in `WOO_PAID_STATUSES`
(`processing,completed`) **and** its payment method is not in
`WOO_COD_METHODS`. `date_paid` must be present unless the order is completed.

Then in WhatsApp: `start` → `option1` → `woo 25` → check with `list` → `stop`.

Line items become `2cxe` style when the SKU is a single token, otherwise
`Product name x 2`. Several line items produce several entries on one label —
they are never merged.

---

## Replacing the old prepaid bot

Compared with `cream-bot-prepaid`, the label rendering is the part that
changed: labels are drawn on a fixed 2×3 grid with measured text wrapping
instead of flowing paragraphs, which is why the size and spacing now match the
printed sheet. Keep the same Render service and Meta webhook URL, point the
service at this repo, copy over `WHATSAPP_TOKEN` and
`WHATSAPP_PHONE_NUMBER_ID`, and add `BILLERS`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Webhook verification fails | `WHATSAPP_VERIFY_TOKEN` must match Meta exactly |
| Bot silent | Check `ALLOWED_SENDERS` holds your number, digits only, with country code |
| PDF never arrives | Token expired (24 h on test numbers) — check Render logs for `upload_media failed` |
| Every message processed twice | Expected: Meta retries. `store.already_seen` deduplicates them |
| An address parsed wrongly | `python cli.py bad.txt --dry-run`, then add the case to `tests_parser.py` |
| Text too small on a label | Raise `MIN_FONT_SIZE` or lower `LABEL_PADDING_MM` |
