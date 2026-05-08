# DearAI Shotlist Workflows — Claude Code Operating Manual

This file is auto-loaded by Claude Code at session start. It tells Claude
how to drive the production pipeline using `@`-mentions in natural language.

If you're a teammate setting up for the first time, read **TEAM_CLAUDE_SETUP.md**
first — it walks you through clone + .env + token.json. Then come back here.

---

## What you can do in plain English

**Vidgen — locked to shotlist:**
> *"Vidgen set 9 V1"*  →  `byteplus_vidgen.py --set 9 --slot 1`

**Vidgen — set body with custom refs (hybrid):**
> *"Vidgen set 1 references @tara @galih @alley"*  →  `vidgen_freeform.py --from-set 1 --mentions "@tara,@galih,@alley"`

**Vidgen — pure freeform:**
> *"Fire a video of @tara plating bibimbap in the @kitchen, 480p 15s"*  →  `vidgen_freeform.py --mentions "@tara,@bibimbap,@kitchen" --body "..."`

**Storyboard / image gen — regenerate a set:**
> *"Image gen set 1 V1 and V2"*  →  `storyboard_generate.py --set 1 --force`

**Validate the Asset Library:**
> *"Validate all asset codes against BytePlus and clean up stale ones"*  →  `validate_asset_library.py --apply`

**Probe spend:**
> *"What's our BytePlus spend so far this month?"*  →  reads `.byteplus_expense.json`

Claude reads this file + the live Asset Library tab and figures out the rest.

---

## The `@`-mention system

When you `@`-mention an asset name in a vidgen request, Claude resolves it
**live from the Asset Library tab** on the bible sheet. No hardcoded codes.
Update an asset → next mention picks up the new code automatically.

### Recognized mention patterns

| Pattern | Resolves to |
|---|---|
| `@tara`, `@TARA`, `@tara-anjani` | TARA ANJANI (image + video + audio) |
| `@minjun`, `@park-min-jun`, `@MIN-JUN` | PARK MIN-JUN (image + video + voice) |
| `@galih` | GALIH (image + video + audio) |
| `@joon-ho`, `@joonho` | LEE JOON-HO |
| `@bu-endang`, `@endang` | BU ENDANG |
| `@manager` | MANAGER |
| `@kitchen`, `@hanbyeol-kitchen` | INT. Kitchen 4 (Hanbyeol Bistro Kitchen) |
| `@cooler`, `@chiller` | INT. Chiller V01 (Walk-In Cooler) |
| `@locker`, `@dressing-room` | INT. Locker Room (Hanbyeol Dressing Room) |
| `@office`, `@joon-ho-office` | INT. Office Lee Joon Ho |
| `@storage` | INT. Storage 4 |
| `@alley`, `@back-alley` | EXT. Back Alley |
| `@apartment`, `@tara-apartment` | Studio Apartment Day |
| `@bibimbap`, `@bibimbap-bowl` | Bibimbap bowl |
| `@kimchi-pot`, `@earthen-pot` | Earthen clay pot (kimchi jjigae) |
| `@knife`, `@chefs-knife` | Chef's knife |
| `@thermos`, `@coffee-cup` | Coffee cup |
| `@cigarette` | Cigarette |
| `@logo`, `@hanbyeol-logo` | Hanbyeol Logo |

For attire, mention the character — the relevant costume auto-attaches via
the owner-character pattern (e.g., "Sous chef whites (Min-jun)" attaches when
@minjun is mentioned).

### Match strategy (for unrecognized tokens)

Claude resolves any `@<token>` via this order:
1. **Exact normalized name match** in Asset Library
2. **Substring contains** (token in name OR name in token, ≥4 chars)
3. **Token-split fuzzy** match on words ≥3 chars

If a mention can't be resolved, Claude warns inline and skips it.

---

## How to invoke vidgen via Claude

### Freeform mode (recommended for ad-hoc requests)

Tell Claude something like:

> "Fire a vidgen of @tara serving food at the @kitchen pass while @minjun
> watches. 480p, 15s, vertical."

Claude will:
1. Parse the `@`-mentions: `@tara`, `@kitchen`, `@minjun`
2. Resolve each against Asset Library
3. Build a Seedance 2 prompt with proper identity binding
4. Submit to BytePlus
5. Download the MP4 and (if requested) upload to Drive
6. Return the URL

The script Claude calls under the hood:

```bash
python3 vidgen_freeform.py \
  --mentions "@tara,@kitchen,@minjun" \
  --body "Tara serves food at the kitchen pass while MIN-JUN watches" \
  --resolution 480p --duration 15 --aspect 9:16
```

### Set-based mode (locked to the shotlist)

For production runs against a specific set in the Storyboard Prompts tab:

> "Fire vidgen for Sajangnim ep01 set 9 slot 1 at 480p"

Claude calls:

```bash
python3 byteplus_vidgen.py \
  --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc \
  --set 9 --slot 1 --resolution 480p
```

This auto-pulls body + globals + storyboard ref from the sheet, auto-detects
character/location/prop refs from the body text, and writes V1/V2 URLs
back to SP!M/N. Ideal for production runs that match the locked shotlist.

### Natural-language shorthand patterns

The team will phrase requests tersely. Claude should recognize these:

| What the team types | Maps to |
|---|---|
| `vidgen set 1` | locked: `byteplus_vidgen.py --set 1 --slot 1` |
| `vidgen set 1 V1` or `vidgen set 1 slot 1` | locked: same as above |
| `vidgen set 1 V2` | locked: `byteplus_vidgen.py --set 1 --slot 2` |
| `vidgen set 1 V1 and V2` | locked: fire both slots sequentially |
| `vidgen set 1 references @tara @galih @alley` | hybrid: `vidgen_freeform.py --from-set 1 --mentions "@tara,@galih,@alley"` |
| `vidgen set 1 with @tara only` | hybrid: same, with one mention |
| `vidgen set 1 1080p` | locked, but at 1080p delivery resolution |
| `vidgen @tara plating bibimbap, kitchen` | freeform: `vidgen_freeform.py --mentions "@tara,@bibimbap,@kitchen" --body "..."` |
| `image gen set 1 V1 and V2` | regen: `storyboard_generate.py --set 1 --force` |
| `image gen set 1` (alone) | regen: same as above (force both iters) |
| `regenerate storyboard for set 5` | regen: `storyboard_generate.py --set 5 --force` |

When the team says **"references"**, **"refs"**, or lists @-mentions explicitly,
they want hybrid mode (override the auto-detected refs). When they don't, they
want locked mode (use what's in the shotlist).

### Storyboard regen mode

Regenerating storyboards for an existing set is a separate flow from vidgen.
Use this when:
- The first auto-generated storyboard came out wrong
- The body/dialogue changed, so the storyboard needs to reflect the new content
- Iter 1 looks great but iter 2 is unusable (regen iter 2 only — TBD flag)

> *"Image gen set 5 V1 and V2"*

Claude calls:

```bash
python3 storyboard_generate.py \
  --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc \
  --set 5 --force
```

The script:
- Reads SP!C{row} (the storyboard prompt body)
- Uses Higgsfield gpt_image_2 (16:9, 1K, 2 iterations)
- Uploads to `<show>/storyboards/set-NN/`
- Writes G/H URLs back to the sheet
- Sets Status to Done

Wall time: ~2-3 min per set (both iters fire in parallel).

### Hybrid mode — set's body but with custom refs

When the team wants to **keep set 1's body** but override which characters /
locations / props attach (e.g. "fire the set 5 dialogue but with @galih
instead of @minjun, in the alley not the kitchen"):

> "Fire vidgen using set 5's body, but only @tara and @galih in the @alley. 480p, 15s."

Claude calls:

```bash
python3 vidgen_freeform.py \
  --from-set 5 \
  --mentions "@tara,@galih,@alley" \
  --resolution 480p --duration 15
```

`--from-set 5` pulls **body + globals + Iter 1 storyboard** from
`Storyboard Prompts!{row 15}` and `Video Prompts!B1:B3` automatically.
Then `--mentions` OVERRIDES the auto-detected refs with what you specified.

If you OMIT `--mentions` while using `--from-set`, the script falls back to
auto-detection (same behavior as `byteplus_vidgen.py`):

> "Fire vidgen using set 5's body as a freeform run"

```bash
python3 vidgen_freeform.py --from-set 5 --resolution 480p
```

Use this hybrid path when:
- You want to test a what-if (different cast, different setting)
- You want to render the same body without writing back to the sheet
- The shotlist body is fine but BytePlus stuck a wrong ref last time

---

## Project sheet IDs (Sajangnim)

| Sheet | ID |
|---|---|
| **Bible / EP01 master** | `1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc` |
| EP02 — Garam Jadi Gula | `1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4` |
| EP03 — Kalau Aku Pergi | `10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I` |
| EP04 — Pukul Lima Pagi | `1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4` |
| EP05 — Mata yang Mengamati | `1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg` |
| EP06 — Sajangnim Sudah Tahu | `1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI` |

The bible sheet is the source of truth for **all bibles + Asset Library**.
Episode sheets only carry per-episode Shotlist + Storyboard Prompts.

---

## Asset Library = source of truth

Every `@`-mention resolves against the Asset Library tab. Rules to keep
the system reliable:

1. **Don't hardcode asset codes anywhere** — codes change, names don't.
2. **Asset Library Status column matters** — only `Uploaded` rows are
   considered live. Mark stale entries `Replaced`.
3. **Names in Asset Library should match bible names** — TARA ANJANI in
   CHARACTERS bible should appear as TARA ANJANI in Asset Library, not
   "TARA" or "Tara". Vidgen matches by name.
4. **Multiple media per character is fine** — TARA can have image + video
   + audio rows, all using the same `name=TARA ANJANI`. Vidgen pulls all
   of them on `@tara`.

When the Asset Library drifts (BytePlus deletes assets behind your back,
team renames things, etc.), run the validator:

> "Validate Asset Library and clean up stale rows"

Claude runs:

```bash
python3 validate_asset_library.py --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc
```

This probes every Uploaded row against BytePlus, marks orphans `Replaced`,
and reports a diff.

---

## What if Claude forgets / something breaks?

Claude doesn't have memory between sessions, but **CLAUDE.md (this file)
is auto-loaded on every new session**. So as long as this file stays at
the repo root, every Claude session reads it.

If Claude is acting confused or unfamiliar with the workflow:
1. Tell it: "Read CLAUDE.md and TEAM_BYTEPLUS_VIDGEN.md"
2. Or run `/init` to force a re-scan of the project

Worst-case fallback: drop into the Terminal directly. Every workflow has a
CLI script that works without Claude:

| Workflow | CLI fallback |
|---|---|
| Freeform vidgen | `python3 vidgen_freeform.py --mentions ... --body ...` |
| Set-based vidgen | `python3 byteplus_vidgen.py --sheet ... --set N --slot N` |
| Resume crashed jobs | `python3 byteplus_vidgen_resume.py` |
| Validate Asset Library | `python3 validate_asset_library.py --sheet ...` |
| Storyboard generation | `python3 storyboard_generate.py --sheet ...` |
| Spend tally | `cat .byteplus_expense.json \| python3 -m json.tool` |

---

## Common patterns

### "Quick fire" — just generate something

> "Make a quick test video of @tara walking through the @kitchen, 4s, 480p"

### Voice override

If you want a character's voice on someone else's body:

> "Fire @tara face with @minjun voice, walking through the kitchen"

(Claude will ATTACH @tara's video + @minjun's audio, prompt clarifies.)

### Multi-character scenes

> "Vidgen of @tara at the pass, @minjun yelling at her, @galih watching from the line. 15s 480p"

3 character bundles + voice for whoever speaks. Storyboard composition
lives in the body description; cumulative video budget enforces 15s cap.

### High-res deliverable

> "Re-fire set 9 V1 at 1080p with confirm gate"

Adds `--resolution 1080p --confirm` so you can review the prompt before paying.

### Bahasa locale

> "Fire @tara at the kitchen pass, dialogue in Bahasa Jakarta"

Body text in Bahasa is fine — Seedance handles trilingual EN/ID/KO out of
the box. Voice ref drives accent.

---

## What Claude should NOT do automatically

- **Do not delete BytePlus assets** unless explicitly asked. Use Replaced
  status in Asset Library instead.
- **Do not modify bible tabs** (CHARACTERS, LOCATIONS, etc.) without
  confirmation. Asset codes auto-update there but other fields are
  human-edited.
- **Do not run vidgen at 1080p without `--confirm`**. 1080p is 2.6× more
  expensive; always preview the prompt first.
- **Do not retry failed jobs without checking why they failed**. A 15s
  budget bust or a stale asset code needs a fix, not a retry.

---

## Architecture quick reference

```
Drive 01. Assets/                   ← raw media files
  ├── Character/<NAME>/             (image + video + audio per character)
  ├── Location/<sub>/                (location refs by zone)
  ├── Costume/                       (attire refs, parenthetical owner)
  ├── Props/                         (props)
  └── Effects/                       (FX)

Bible Sheet (1iygU-...)              ← logical schema + status
  ├── CHARACTERS / LOCATIONS / etc.  (bible rows w/ Asset Code col)
  └── Asset Library                  (single source of truth: name → code)

BytePlus virtual library             ← actual binary assets
  └── group sajangnim-bibles         (resolved via asset:// URI scheme)

Episode sheets (1-EPcY1... etc.)     ← per-episode shotlist + storyboard prompts
  └── Storyboard Prompts             (set-by-set, M=V1, N=V2)

Render dashboard                     ← review only (vidgen click-fire is unreliable)
  https://dearai-dashboard.onrender.com
```

For everyday vidgen: **stay in Claude Code on your laptop**. The dashboard
is for review/audit, not for generation triggers (Render's worker process
is too unstable for the long-running BytePlus calls).

---

— Last updated: 2026-05-08
