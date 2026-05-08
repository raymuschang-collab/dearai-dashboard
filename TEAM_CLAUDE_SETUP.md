# Team Setup — Run the Vidgen Pipeline via Claude Code

Step-by-step for getting the BytePlus / Drive / Sheets pipeline running on
your laptop, driven through Claude Code (so you ask Claude to fire vidgen
runs in plain English instead of typing CLI commands).

Targets a teammate who:
- Has Claude Code installed already (or can install it)
- Has Python 3 on their Mac (built-in on macOS 13+)
- Is NOT necessarily a developer — copy-paste-ready instructions

Total setup time: ~10 minutes.

---

## 1. Get Claude Code installed

If you already have Claude Code, skip ahead.

Otherwise: https://claude.com/download → pick the macOS app, install, sign in
with your Anthropic account. Open Terminal once Claude Code is up.

---

## 2. Get the project on your machine

```bash
cd ~/Desktop
git clone https://github.com/raymus-rgb/dearai-dashboard.git "Shotlist Workflows"
cd "Shotlist Workflows"
```

If git isn't installed: download the repo as a ZIP from
https://github.com/raymus-rgb/dearai-dashboard → "Code" → "Download ZIP" →
unzip into `~/Desktop/Shotlist Workflows`.

---

## 3. Install the Python dependencies

```bash
pip3 install -r requirements.txt
```

If it complains about permissions:

```bash
pip3 install --user -r requirements.txt
```

You only need to do this once.

---

## 4. Receive your credentials from Raymus

You need TWO files in the project root:

### a) `.env` — API keys

Raymus will share these via 1Password (look for an item called
**"DearAI Dashboard — Production Secrets"**), or via Slack DM. Whichever
channel you receive it in, save the file as exactly:

```
~/Desktop/Shotlist Workflows/.env
```

The file must be named `.env` — note the leading dot. Some Macs hide dot
files in Finder. To see them: in Finder, press `Cmd+Shift+.`

The contents look like this (do not edit, just save the file):

```
BYTEPLUS_ARK_API_KEY=ark-...
BYTEPLUS_ACCESS_KEY=AKA...
BYTEPLUS_SECRET_KEY=WXp...
BYTEPLUS_PROJECT=D.AI
BYTEPLUS_GROUP_ID=group-...
DASHBOARD_ASSET_LIBRARY_SHEET_ID=1iygU-...
SOT_ASSET_LIBRARY_SHEET_ID=1iygU-...
FAL_KEY=...
OPENAI_API_KEY=sk-proj-...
```

### b) `token.json` — Google auth (Drive + Sheets)

Same channel. Save as:

```
~/Desktop/Shotlist Workflows/token.json
```

This is a refresh token tied to Raymus's Google account. It lets the
scripts read/write the production Sheets without a re-login on every
run. It refreshes itself automatically — you do not need to touch it.

> **Don't share `.env` or `token.json` outside the team.** They have
> production-grade access. The repo's `.gitignore` already excludes
> them from any future git commits, but stay aware.

---

## 5. Tell Claude Code about the project

Open Claude Code, then in the chat, type:

```
/init
```

Claude scans the project, reads `CLAUDE.md` (the project instructions),
and learns the codebase layout. Takes ~30 seconds.

---

## 6. Verify everything works

Ask Claude:

```
Verify my setup works — read 1 row of the Sajangnim ep01 Storyboard Prompts
tab to confirm Sheets auth is wired, and probe one BytePlus asset to confirm
my API key is live. Use python from my terminal.
```

Claude will run two tiny scripts and report back with ✓ marks. If it sees
an `ImportError`, you missed step 3. If it sees `auth failed`, you missed
step 4. If it sees the row + asset details, you're set.

---

## 7. Fire your first vidgen via Claude

Once verified, you can drive the whole pipeline through plain-English
prompts to Claude. Some examples that work today:

### Generate one V1 video for set 9 of Sajangnim ep01

```
Fire vidgen for Sajangnim ep01 set 9 slot 1 at 480p / 15s.
Use the bible sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc.
```

Claude will run `python3 byteplus_vidgen.py --sheet ... --set 9 --slot 1`,
stream the output, and tell you when the Drive URL lands in the sheet.

### Fire BOTH V1 and V2 for one set

```
Fire vidgen for Sajangnim ep01 set 8 — both V1 and V2. Run them sequentially.
```

### Recover a stalled job

If a previous vidgen run died mid-pipeline:

```
Run the vidgen resume script and tell me what it picked up.
```

### Check expense to date

```
What's my BytePlus cumulative spend so far?
```

Claude will read `.byteplus_expense.json` and reply with the dollar total.

### Replace a stale character / costume / prop reference

```
The TARA face video on BytePlus is wrong. I uploaded a new one to
this Drive file: <paste link>. Speed it up to 4.95s, upload to BytePlus,
and swap the old asset out in the Asset Library.
```

Claude will run ffmpeg, upload to Drive + BytePlus, mark the old row
Replaced, add a new row.

---

## 8. Common things to know

### What sheet ID do I use?

For Sajangnim, **always pass the bible sheet** when firing vidgen:

```
1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc
```

Even though episodes have their own sheets, the bible sheet is where
Asset Library + CHARACTERS live, and where vidgen reads from.

### What is "set N"?

Each episode is broken into ~14 sets of 5 shots each. So set 9 = shots
41-45, set 10 = shots 46-50, etc. Each set produces 2 video iterations
(V1 + V2).

### What's the difference between V1 and V2?

Both fire the SAME prompt and refs to BytePlus. The only difference is
which storyboard image is used as the composition reference (slot 1
uses Storyboard 1, slot 2 uses Storyboard 2). You get two takes that
naturally vary because Seedance has internal variance.

### How long does vidgen take?

3-5 minutes wall time per slot at 480p / 15s. So one full set
(V1 + V2) is ~6-10 min. Run them sequentially, not parallel — fewer
moving parts to debug.

### What if the Asset Library has a stale ref?

This happens — BytePlus sometimes garbage-collects old assets. If a run
fails with `400 ... not found`, ask Claude:

```
Validate all asset codes in Sajangnim's Asset Library against BytePlus.
Mark any that return NotFound as Replaced.
```

Claude will probe each row and clean up. Then re-fire.

### Cost ballpark per video

| Resolution | Per 15s clip |
|-----------|-------|
| 480p | $0.75 |
| 720p | $1.20 |
| 1080p | $1.95 |

Iterate at 480p, then re-fire approved sets at 1080p just before final
delivery.

---

## 9. What about the dashboard?

The web dashboard at https://dearai-dashboard.onrender.com is currently
unreliable for vidgen — Render sometimes kills the subprocess before it
reaches BytePlus, so the click silently fails. The CLI path works
reliably; use it via Claude until the dashboard issue is resolved.

You can still use the dashboard for:
- Reviewing storyboards and videos (read-only)
- Managing the Reviewed checkbox + comments on each set
- Auditing the Asset Library

For anything that GENERATES content (vidgen, storyboard regen), drop
into Claude Code on your laptop.

---

## 10. Shortcuts for common workflows

If you find yourself running the same prompt over and over, you can
turn it into a Claude Code slash command. Create
`.claude/commands/<name>.md` in the project. Example —
`.claude/commands/vidgen-set.md`:

```markdown
Fire vidgen for Sajangnim ep01.

Sheet: 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc
Set: $1 (the user passes this as a number)
Resolution: 480p
Duration: 15

Run BOTH slots (V1 + V2) sequentially. Stream output as it runs. When
both finish, give me the two Drive URLs.
```

Then in Claude:

```
/vidgen-set 9
```

— fires both V1 and V2 of set 9, hands off to Claude to drive end-to-end.

---

## 11. Troubleshooting

### Claude says "command not found: python3"

You need to install Python 3. Easiest path:

```bash
brew install python3
```

(If you don't have Homebrew yet: https://brew.sh — copy the install
command, paste in Terminal, run.)

### Claude says "ImportError: No module named gspread"

You missed step 3. Run:

```bash
cd ~/Desktop/"Shotlist Workflows"
pip3 install -r requirements.txt
```

### Claude says "Could not find auth.py"

You're not in the project directory. In Terminal:

```bash
cd ~/Desktop/"Shotlist Workflows"
ls
```

Should list `auth.py`, `byteplus_vidgen.py`, etc. If those aren't there,
go back to step 2.

### "BYTEPLUS_ARK_API_KEY not set in .env"

The `.env` file isn't where the script expects, or has the wrong name.
Verify:

```bash
ls -la ~/Desktop/"Shotlist Workflows"/.env
```

Should show the file exists. If not, see step 4a.

### "Google credentials unavailable"

Token expired or `token.json` is missing. Either:
- Get a fresh `token.json` from Raymus (most common fix), OR
- Run `python3 auth.py` once to do an OAuth login in your browser

---

## 12. Who to ask

- **Pipeline / vidgen issues**: ping `#dearai-pipeline` in Slack
- **Sheet schema / shotlist issues**: same channel
- **Credentials, account access**: DM Raymus directly
- **Claude Code issues** (not project-specific): https://claude.com/download
  → "Help" tab in the app

---

— Last updated: 2026-05-08
