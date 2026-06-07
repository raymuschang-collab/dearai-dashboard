---
description: Generate a 16:9 character reference sheet via Higgsfield gpt_image_2 using the locked production-bible template. Ad-hoc (free-form description) OR sheet-based (pulls from CHARACTERS bible tab).
argument-hint: <free-form character description>   |   --sheet <id> --char "Name"   |   --name "X" --role "Y" --ethnicity "Z" ...
---

User invoked /charsheet. Args: `$ARGUMENTS`

## What this does

Fires the **locked production-bible character reference sheet** prompt against Higgsfield `gpt_image_2`. Locked output: 16:9 landscape page, off-white studio bg, documentary-editorial portraiture, Kodak Portra 400, with labeled panels:

- Header block (Name, Alias, Role, Age, Personality, Core Theme, Speech Accent)
- MAIN IDENTITY + SCALE SHEET (4 full-body views: front · 3/4 · side · back)
- COLOR PALETTE (7 swatches)
- EXPRESSION PROGRESSION (8 head-and-shoulders: Neutral → Relieved)
- MICRO EXPRESSIONS (5 tight CUs)
- HEAD DETAIL SHEET (5 head angles)
- NEUTRAL BASELINE + POSTURE VARIATION
- WARDROBE / ACCESSORIES DETAILS (4 macro crops)
- PROP (isolated product-style shot)
- CLOSE-UP POSE (hero portrait)

Defaults: aspect `16:9` · quality `high` · resolution `2k` · single iter.

## Parse args — three modes

### MODE A · Sheet-based (the production path)

If `$ARGUMENTS` contains `--sheet <id-or-url>` AND `--char "Name"`, dispatch to the production script:

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 character_generate.py --sheet "<sheet>" --char "<name>" [--force]
```

This reads the row from the CHARACTERS bible tab, builds the full 17-field prompt, fires the gen, uploads to Drive, writes the iter URL back to the sheet, marks Status=Done. Idempotent — skips Done rows unless `--force`.

### MODE B · Explicit flags (ad-hoc, no sheet)

If `$ARGUMENTS` contains `--name "X"` (required), parse all of the bible-field flags and pass through:

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 _charsheet_adhoc.py \
  --name "X" \
  [--role "..."] [--age N] [--gender "..."] [--ethnicity "..."] \
  [--height "..."] [--build "..."] [--hair "..."] [--eyes "..."] \
  [--distinguishing "..."] [--wardrobe "..."] [--prop "..."] \
  [--personality "..."] [--theme "..."] [--accent "..."] [--mood "..."] \
  [--iters 2] [--aspect 16:9] [--quality high] [--resolution 2k]
```

Output saves to `~/Desktop/Char Sheets/<slug>_v<N>.png` and auto-opens in Preview.

### MODE C · Free-form description (fastest)

If `$ARGUMENTS` is just plain prose (no `--name` / `--sheet`), YOU parse the description into the 17 bible fields, then call MODE B with the parsed fields.

Example user input:
```
/charsheet Carmen Tan, 30, Singaporean Chinese photojournalist. Bob haircut, cream blazer over black top. Calm and observant. Singapore English accent. Carries a Leica M6.
```

You extract:
- name: Carmen Tan
- age: 30
- ethnicity: Singaporean Chinese
- role: Photojournalist
- hair: Bob haircut
- wardrobe: cream blazer over black top
- personality: Calm and observant
- accent: Singapore English
- prop: Leica M6

Then fire MODE B with those flags. Fill `--mood`, `--theme`, etc. with sensible defaults extracted from context — don't ask the user 17 questions. If a field is unclear, leave it out (the script defaults to "—").

## When the user gives BOTH a free-form description AND some explicit flags

Use explicit flags as the source of truth; let the free-form description fill any gaps. The script's `--description` flag routes the free-form into the `distinguishing features` slot as a fallback when explicit fields aren't given.

## When to NOT ask clarifying questions

Don't ask. Parse what's there, fill in defaults, fire. The user can re-fire with tighter flags if the output drifts. Trying to interview the user before firing kills the fast-iteration loop this command exists for.

## Tips

- Single iter is the default (saves credits + time). Pass `--iters 2` for an A/B.
- For an alt background, use `--background "dark slate seamless paper"` or similar.
- 1k resolution is 2× faster than 2k and usually enough for review. Override with `--resolution 1k`.
- Sheet mode writes to Drive + the sheet's `T` (Iter 1) and `V` (Status) columns; ad-hoc mode writes ONLY to `~/Desktop/Char Sheets/` locally.

## Cost / wall time

Higgsfield subscription-paid via the HK company's $1M wallet (per the project's routing memory): $0 marginal until depletion. Wall time per iter: ~60–90s at 2k, ~30–45s at 1k.

## Locked prompt template

Lives in `character_generate.py:48–82` as `PROMPT_TEMPLATE`. The ad-hoc wrapper (`_charsheet_adhoc.py`) imports this template directly — single source of truth, no drift between sheet-based and ad-hoc paths.
