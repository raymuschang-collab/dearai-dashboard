---
description: Generate storyboard panels for one set. Default = featureless stick figures (sajangnim aesthetic). Force --pencil / --photoreal as needed.
argument-hint: <sheet-id-or-url> set <N> [V1|V2|V1 and V2] [--stick|--pencil|--photoreal|--sheet] [--force]   |   example: /imggen <sheet> set 4
---

User invoked /imggen. Args: `$ARGUMENTS`

## Parse args

Extract the Sheet ID / URL first, then parse `set <N>` or bare `<N>`.

**Style modes** (preamble forced regardless of sheet B1:B4 globals):

- `--stick` (default, can be omitted) — Featureless stick figures, no facial features, black-pen on white-paper sketch. Sajangnim production aesthetic. Use for ALL coverage validation.
- `--pencil` — Director-pad pencil sketch with light shading. Features readable but loose. Use when stakeholders want more visual fidelity than stick figures.
- `--photoreal` — Full photoreal stills (Arri Alexa 35, Kodak Vision3 250D documentary aesthetic). Use ONLY for hero/key frames where the storyboard becomes a deliverable in itself. Most expensive.
- `--sheet` (legacy) — Use whatever style is hardcoded in the sheet's B1:B4 globals. Only pass this if you specifically want the old behavior.

**Sub-args:**

- `set N` generates one set.
- No set → generates all Pending sets.
- `V1`, `V2`, or `V1 and V2` are accepted as user wording. `storyboard_generate.py` writes both iterations together; no extra flag needed.
- `--force` regenerates Done sets.

If `$ARGUMENTS` is empty or does not include a Sheet ID / Sheets URL, ask once for the target sheet and stop.

## Action — fire directly

Provider: Higgsfield `gpt_image_2` via `storyboard_generate.py`.

Resolve `--stick` / `--pencil` / `--photoreal` / `--sheet` from the user's args. Default = `stick`.

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 storyboard_generate.py --sheet "<sheet>" --style <stick|pencil|photoreal|sheet> [--set <N>] [--force]
```

## Why default is stick

The atomized 5-shot storyboard is **a coverage validation tool**, not a final deliverable. Editor + director need to see staging, framing, camera moves — never likeness or lighting. Stick figures force the eye onto blocking. Photoreal storyboards distract reviewers into "does this character look right?" critiques that are out of scope for shot coverage.

If your team is still debating likeness at the storyboard stage, the answer is to lock the cast bible BEFORE storyboards, not to ship photoreal storyboards.

## Notes

- Style preamble is **prepended at runtime** by the script. You don't need to edit the sheet's B1:B4 globals.
- The script is idempotent: skips Done rows unless `--force`.
- Each set fires 2 iterations in parallel. Wall time ~45s per set at 1K resolution.
- Provider routing is locked to Higgsfield `gpt_image_2` for storyboards.
