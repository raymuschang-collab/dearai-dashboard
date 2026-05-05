---
description: Build the Storyboard Prompts tab + Drive set-NN/ folders for one episode shotlist.
argument-hint: <sheet-id-or-url>
---

User wants to build (or refresh) the Storyboard Prompts tab for a single episode Sheet.

Target: `$ARGUMENTS`

If `$ARGUMENTS` is empty or doesn't look like a Sheet ID / Sheets URL, ASK the user which sheet to target. Do not default to anything — the canonical reference Sheet `1-EPcY1YXstCfJm81MpVCpmuCdvN6O3awXWZ5H885T78` is already complete and must not be overwritten.

## Action — run directly, no dry-run, no confirmation

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 storyboard_build.py --sheet "$ARGUMENTS"
```

The script is idempotent and safe to run without prior planning:
- Reuses existing `storyboards/` and `set-NN/` folders rather than duplicating them.
- If a populated Storyboard Prompts tab already has the right row count, it's left alone (success, not failure).
- The `--force` flag is the only path that overwrites existing tabs — never pass it unless the user explicitly says "rebuild from scratch."

## Final report

One line: sheet name, set count, status. Examples:
- `✓ Ep 2 - Dilacak — 14 sets ready, storyboards/ + set-01..set-14/ created.`
- `✓ Ep 1 - Ponsel Itu (v2.1 Atomized) — already populated, skipped.`

If the script exits non-zero, surface the stderr line and stop. Don't retry.

## Video Prompts globals — per-show, NOT defaults

The `Video Prompts` tab is created with empty B1+ cells. Producer fills PER-SHOW:
- **B1 (Camera global)** — required, e.g. "Shot with arri 35."
- **B2 (Audio/Dialogue global)** — required, e.g. accent + music direction.
- **B3 (Scale global)** — **OPTIONAL.** Only fill if the show has unusual-scale creatures/objects (e.g. kaiju, giants). **Leave blank for normal-scale shows.**
- **B4 (Setting global)** — **OPTIONAL.** Only fill if a single setting persists across the whole episode (e.g. "Setting is ancient Egypt"). **Leave blank when setting varies shot-by-shot.**
- **B5+ Bahasa rows** — optional translation pairs.

`fal_vidgen.py` / `flora_run.py` read B1:B4 and concat non-empty rows. Empty B3/B4 → skipped, no harm.

**DO NOT pre-populate B3/B4 in this build script.** Each show owns its own scale/setting context.

## Authentication

Handled by `auth.py` in the working directory. Token is valid; do not re-run OAuth.
