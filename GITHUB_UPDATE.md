# Updating the existing repo (`cream-bot-prepaid`)

This replaces the code in your existing repository rather than creating a new
one, so the Render service and the Meta webhook URL keep working untouched.

---

## 1. Replace the code

```bash
git clone https://github.com/An-andd/cream-bot-prepaid.git
cd cream-bot-prepaid

# keep a way back before deleting anything
git checkout -b old-version
git push -u origin old-version
git checkout main            # or master, whichever your repo uses

# remove the old application code (keep .git, and keep README if you like)
git rm -r --cached . -q
rm -rf $(ls -A | grep -v -e '^\.git$')

# copy in the new project: the contents of the cream-prepaid folder,
# not the folder itself
cp -r /path/to/cream-prepaid/. .

git add -A
git commit -m "Rewrite prepaid label generator: 6-per-page grid, right-side sender block"
git push origin main
```

After this the repo root should look like:

```
app/  cli.py  tests_parser.py  samples/  requirements.txt
render.yaml  Procfile  README.md  .env.example  .gitignore
```

`.env` is git-ignored on purpose. Never commit your WhatsApp token.

### If you prefer to keep the old files around

```bash
mkdir old && git mv <old files> old/     # instead of the rm -rf above
```

## 2. Point Render at the new entry point

Render → your service → **Settings**:

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app.server:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` |
| Health Check Path | `/` |

The entry point moved (`app.server:app`), so this must be changed or the
deploy will fail with a module-not-found error.

Then **Manual Deploy → Deploy latest commit**, and open
`https://<your-service>.onrender.com/` — you should see:

```json
{"status":"ok","service":"cream-prepaid-labels","whatsapp_configured":true,...}
```

## 3. Meta webhook

Nothing changes if your old bot already used `/webhook`. Confirm at
developers.facebook.com → WhatsApp → Configuration:

- Callback URL: `https://<your-service>.onrender.com/webhook`
- Verify token: exactly the same string as `WHATSAPP_VERIFY_TOKEN`
- Webhook field **messages** is subscribed

## 4. Test before printing

In WhatsApp, to the test number:

```
start
option1
<paste 2 addresses>
list
stop
```

You should get a PDF back with 2 labels on one page.

---

# Values you must fill in yourself

Set these in **Render → Environment**, one per row. The ones marked **required**
must be filled or the bot will not run.

| Variable | Required | Where to get it | Example |
|---|---|---|---|
| `WHATSAPP_TOKEN` | yes | developers.facebook.com → your app → WhatsApp → API Setup → temporary token, or a permanent System User token | `EAAG...` |
| `WHATSAPP_PHONE_NUMBER_ID` | yes | same page, **Phone number ID** (not the phone number) | `123456789012345` |
| `WHATSAPP_VERIFY_TOKEN` | yes | you invent it; paste the identical string into Meta's Configuration page | `cream-verify-9f3x` |
| `ALLOWED_SENDERS` | strongly advised | your own WhatsApp number, country code first, digits only, comma-separated for more than one | `918129770502` |
| `BILLERS` | yes | your three Biller IDs (given below, already filled in) | see below |
| `WHATSAPP_API_VERSION` | no | leave unset unless Meta deprecates it | `v22.0` |

`BILLERS`, as a single line — this already has your three real IDs, paste it as-is:

```
{"option1":{"label":"default","id":"1260357626"},"option2":{"label":"alternative 1","id":"1264602129"},"option3":{"label":"alternative 2","id":"1624036027"}}
```

If you only ever use one Biller ID, set just `BILLER_ID=1260357626` and skip
`BILLERS` — the bot will offer a single option.

### Already correct, change only if your details change

| Variable | Current value |
|---|---|
| `SENDER_NAME` | `CREAM X EMIRATES` |
| `SENDER_ADDRESS` | `PUTHUPALLY, KTM` |
| `SENDER_PIN` | `686011` |
| `SENDER_PHONE` | `8129770502` |
| `OUTPUT_DIR` | `/tmp/cream_labels` |
| `DB_PATH` | `/tmp/cream_prepaid.sqlite3` |

### Optional — WooCommerce (`woo` command)

| Variable | Where to get it |
|---|---|
| `WOO_URL` | your store URL, no trailing slash, e.g. `https://creamxemirates.com` |
| `WOO_CONSUMER_KEY` | WordPress admin → WooCommerce → Settings → Advanced → REST API → Add key, permission **Read** |
| `WOO_CONSUMER_SECRET` | shown once when the key is created — copy it immediately |

Leave all three unset and everything else still works; only the `woo` command
is disabled.

### Optional — layout tuning

Only touch these if the print does not line up on your label sheet.

| Variable | Default | Effect |
|---|---|---|
| `FROM_BLOCK_POSITION` | `right` | `below` stacks the sender under the customer instead |
| `TO_COLUMN_RATIO` | `0.58` | raise toward `0.65` to give long addresses more width |
| `FROM_VALIGN` | `bottom` | `middle` or `top` moves the sender block up |
| `COLUMN_GAP_MM` | `3` | gap between the two columns |
| `PAGE_MARGIN_MM` | `8` | outer page margin |
| `LABEL_PADDING_MM` | `5` | space inside each box |
| `BASE_FONT_SIZE` | `10` | starting font size |
| `MIN_FONT_SIZE` | `6` | smallest the font may shrink to |
| `OUTPUT_FORMAT` | `pdf` | `both` also sends an editable Word file |

## Checklist

- [ ] Old code pushed to the `old-version` branch as a backup
- [ ] New code on `main`, repo root contains `app/`
- [ ] Render start command changed to `gunicorn app.server:app ...`
- [ ] `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` set
- [ ] `WHATSAPP_VERIFY_TOKEN` identical in Render and Meta
- [ ] Your number in `ALLOWED_SENDERS`
- [ ] `BILLERS` set with your three real IDs (below)
- [ ] `/` returns `"status":"ok"` with `whatsapp_configured: true`
- [ ] A two-address test batch printed correctly
