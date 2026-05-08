# BytePlus Vidgen — Team CLI Guide

Direct-to-terminal workflow for generating videos via BytePlus Seedance 2.0
while the dashboard's Generate V1/V2 button is being stabilized on Render.

This bypasses the dashboard entirely — fires straight at BytePlus, uploads
to Drive, writes the URL into the Storyboard Prompts sheet. Same pipeline
the dashboard uses, just run from your laptop instead of Render.

---

## 1. One-time setup (5 minutes)

### a) Clone the repo

```bash
cd ~/Desktop
git clone https://github.com/raymus-rgb/dearai-dashboard.git "Shotlist Workflows"
cd "Shotlist Workflows"
```

### b) Install Python dependencies

```bash
pip3 install -r requirements.txt
```

If you get permission errors:

```bash
pip3 install --user -r requirements.txt
```

### c) Get the `.env` file

The repo doesn't ship the `.env` (secrets) — Raymus will send you a copy
of his via 1Password / Slack DM. Drop it at:

```
~/Desktop/Shotlist Workflows/.env
```

The file has these keys (you don't edit them — just receive the file):

```
BYTEPLUS_ARK_API_KEY=ark-xxxxxxxx
BYTEPLUS_ACCESS_KEY=AKA…
BYTEPLUS_SECRET_KEY=WXp…
BYTEPLUS_PROJECT=D.AI
BYTEPLUS_GROUP_ID=group-…
```

> **Never commit `.env`** to git. The repo's `.gitignore` already protects
> it, but stay aware.

### d) Set up Google auth (Drive + Sheets)

You need a `token.json` to read/write the production Sheets. Either:

- **Option A** (faster): Raymus shares his `token.json` once, you drop it next
  to `.env`. Token auto-refreshes on use.
- **Option B** (cleaner): get added as an editor on the project's GCP OAuth
  client and run `python3 auth.py` to generate your own token via the
  browser flow. One-time. Refresh handled automatically thereafter.

### e) Verify it works

```bash
python3 -c "
from auth import get_credentials
import gspread
gc = gspread.authorize(get_credentials())
sh = gc.open_by_key('1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc')
print('✓ auth works:', sh.title)
"
```

If you see the sheet title, you're set.

---

## 2. The basic vidgen command

```bash
python3 byteplus_vidgen.py \
  --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc \
  --set 9 \
  --slot 1
```

That fires V1 for set 9 of Sajangnim ep01. ~3-5 min wall time. When done,
the URL is written to **Storyboard Prompts!M19** automatically.

### What it does end-to-end

1. Reads the storyboard image at SP!G19 (slot 1) or H19 (slot 2)
2. Reads the body of shots 41-45 from the Shotlist tab
3. Auto-detects which character / location / costume / prop refs apply
   to the body (looks at Asset Library)
4. Builds the Seedance prompt + ref-bundle
5. Submits to BytePlus, polls until succeeded (~3-5 min)
6. Downloads the MP4
7. Uploads to `<show>/videos/set-09/video-iteration-1-480p-15s.mp4`
8. Writes the Drive URL into Storyboard Prompts!M19

If any prior file exists at that location, it's auto-archived under
`set-09/archive/<timestamp>_…` — nothing gets clobbered.

---

## 3. Common arguments

| Arg | Default | Notes |
|-----|---------|-------|
| `--sheet <id>` | required | Spreadsheet ID. Sajangnim bible = `1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc` |
| `--set <N>` | required | Set number (1-14 for Ep 1). Maps to row 10+N on SP. |
| `--slot 1\|2` | `1` | Slot 1 → writes to SP!M (Video Iter 1). Slot 2 → SP!N. |
| `--resolution 480p\|720p\|1080p\|2K` | `480p` | 480p = $0.05/s, 1080p = $0.13/s. 480p for iteration, 1080p for delivery. |
| `--duration <N>` | `15` | Clip length in seconds (4-15). |
| `--aspect 9:16\|16:9` | `9:16` | Vertical drama default. |
| `--fast` | off | Use the cheaper "fast" Seedance tier (~half cost, slightly lower quality). |
| `--confirm` | off | Print refs + prompt preview, wait for [y/N] before submitting. Good for high-res deliverable runs. |

### Sajangnim-specific cheat sheet

```bash
# Iteration draft (cheap, 480p, both slots)
python3 byteplus_vidgen.py --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc --set 9 --slot 1
python3 byteplus_vidgen.py --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc --set 9 --slot 2

# Final 1080p delivery (with confirm gate)
python3 byteplus_vidgen.py --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc --set 9 --slot 1 \
  --resolution 1080p --confirm
```

---

## 4. What the output tells you

When you run vidgen, you'll see live status in the terminal:

```
  + storyboard ref (G19): https://lh3.googleusercontent.com/d/...
  + asset asset-20260508091409-k4rrz (video)
    duration: 5.0s
  + asset asset-20260506170734-qbqzx (audio)
  ⤳ skipping char-image PARK MIN-JUN (video face-loop already attached)

  asset refs detected (5):
    [CHARACTERS] PARK MIN-JUN  → asset-20260508091409-k4rrz
    [CHARACTERS] TARA ANJANI   → asset-20260507192025-mvx2c
    ...

  Submitting...
  task_id: cgt-20260508091949-72m9l
  Polling (typical: 30-180s)...
  [0s] status: running
  [167s] status: succeeded

  ✓ video ready: https://...
  ✓ Drive: https://drive.google.com/file/d/.../view
  ✓ Storyboard Prompts!M19 written
```

The two key markers to watch for:

- **`✓ Drive: https://...`** — the MP4 is uploaded
- **`✓ Storyboard Prompts!M19 written`** — the URL is in the sheet

If the script exits before both, something failed mid-pipeline and the
result is partial. See troubleshooting below.

---

## 5. Crash recovery — `byteplus_vidgen_resume.py`

If a vidgen run dies mid-pipeline (laptop sleeps, network drops, ctrl-C
at the wrong moment), the BytePlus task may have completed but the
download/upload step never ran. The task_id is persisted to
`.byteplus_pending.json` BEFORE the long-running steps so you can resume:

```bash
python3 byteplus_vidgen_resume.py            # finish all pending tasks
python3 byteplus_vidgen_resume.py --dry-run   # preview what would resume
```

The resume script:

1. Reads `.byteplus_pending.json`
2. Calls BytePlus GetTask for each entry
3. For tasks that succeeded: downloads MP4, uploads to Drive, writes
   the sheet cell
4. For tasks still running: leaves the entry, retry later
5. For failed tasks: removes the entry
6. **Idempotent** — if SP!M/N already has a URL, skips the re-upload

You can also run it as a periodic cleanup (cron, every 10 min) without
worrying about double-processing.

---

## 6. Troubleshooting

### `submit failed: 400 ... not found`

A bible row has a stale BytePlus asset code (the original asset was
deleted on BytePlus's side). Find the row in Asset Library, mark its
Status column "Replaced", and re-fire.

To validate ALL Asset Library codes at once:

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
import byteplus_asset_v2 as bp
import gspread
from auth import get_credentials
gc = gspread.authorize(get_credentials())
sh = gc.open_by_key('1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc')
ws = sh.worksheet('Asset Library')
rows = ws.get('A5:F500', value_render_option='FORMATTED_VALUE')
for i, r in enumerate(rows, start=5):
    if not r or not r[0].strip(): continue
    code = (r[2] if len(r)>2 else '').strip()
    status = (r[5] if len(r)>5 else '').strip()
    if not code or status.lower() != 'uploaded': continue
    resp = bp.call('GetAsset', {'Id': code})
    err = resp.get('ResponseMetadata', {}).get('Error')
    if err:
        print(f'STALE row {i}: {r[0]!r:<40} → {code}')
"
```

### `cumulative video-ref duration NN.Ns exceeds 14.0s budget — dropping longest first`

BytePlus caps cumulative duration of all `video_url` refs at 15s. The
enforcer drops the longest video ref until the sum fits. If a character's
face-loop is being dropped, re-record the source as a 4-5s clip:

```bash
ffmpeg -i input.mov -filter:v "setpts=$(python3 -c 'print(4.95/ORIGINAL_SECS)')*PTS" \
  -an -t 4.95 -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p output.mp4
```

Then upload via the asset upload helper:

```bash
python3 byteplus_asset_v2.py create-asset \
  --group group-20260505195134-wqx2b \
  --url "https://drive.google.com/uc?export=download&id=<DRIVE_FILE_ID>" \
  --type Video \
  --name "PARK MIN-JUN" \
  --wait
```

The returned asset code goes in Asset Library col C.

### `⚠ ref limit (8) hit — dropping ...`

Only 8 refs (storyboard + 7 bible) make it to BytePlus. Order is locked
by priority: CHARACTERS → COSTUME → LOCATIONS → PROPS → EFFECTS. Drop
EFFECTS or PROPS first if you need to free room.

### `⚠ no 'Asset Library' tab — refs cannot be resolved to asset codes`

You're firing against an episode sheet that doesn't have its own Asset
Library. For Sajangnim, **always pass `--sheet 1iygU-…LXCc`** (the
bible sheet), even when generating videos that get written to a
specific episode sheet — the bible sheet routes everything correctly.

### Output is silent / hangs

Auth issue. Re-run `python3 auth.py` to refresh the OAuth token, or
check that `BYTEPLUS_ARK_API_KEY` is set in `.env`. The script's first
real action is a sheet read — if that hangs, auth is the most likely
culprit.

---

## 7. Cost ballpark

Per call, at default 480p / 15s / 9:16:

| Resolution | $/sec | 15s clip |
|-----------|-------|----------|
| 480p | $0.05 | $0.75 |
| 720p | $0.08 | $1.20 |
| 1080p | $0.13 | $1.95 |
| 2K | $0.20 | $3.00 |

Track cumulative spend in `.byteplus_expense.json` — every successful
run appends a row. To check the running total:

```bash
python3 -c "import json; print(f\"Total: \${json.load(open('.byteplus_expense.json'))['cumulative_usd']}\")"
```

---

## 8. Quick reference card

```bash
# Fire a single iteration
python3 byteplus_vidgen.py --sheet <ID> --set <N> --slot <1|2>

# Fire both V1 + V2 of one set (run sequentially)
for slot in 1 2; do
  python3 byteplus_vidgen.py --sheet <ID> --set <N> --slot $slot
done

# Resume any tasks that died mid-pipeline
python3 byteplus_vidgen_resume.py

# Dry-run resume to see what's pending
python3 byteplus_vidgen_resume.py --dry-run

# Spend tally
python3 -c "import json; print(json.load(open('.byteplus_expense.json'))['cumulative_usd'])"
```

---

## Notes for Raymus / contact

If you hit a problem this guide doesn't cover, drop a message in
`#dearai-pipeline` with:

- The exact CLI command you ran
- The last 20-30 lines of terminal output
- The set / slot / sheet you targeted

That's enough context to debug in <2 min.

— Last updated: 2026-05-08
