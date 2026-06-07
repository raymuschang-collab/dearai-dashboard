---
description: Build a self-contained production gallery HTML for any v2.2-schema microdrama Sheet (auto-detects bibles + show name + episode + character roster).
argument-hint: <sheet-id-or-url> [--max-set N] [--decoration png] [--feedback-module mod] [--char-overrides json] [--loc-aliases json]
---

User wants to build (or refresh) the production gallery HTML for an episode Sheet.

Target: `$ARGUMENTS`

If `$ARGUMENTS` is empty or doesn't look like a Sheet ID / Sheets URL, ASK the user which sheet to target.

## Action — run directly, no dry-run

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 ~/.claude/skills/production-gallery/build_gallery.py --sheet "$ARGUMENTS"
```

Then `open` the resulting HTML in default browser.

## For Pharaoh specifically

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 ~/.claude/skills/production-gallery/build_gallery.py \
  --sheet "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE" \
  --output "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html" \
  --max-set 12 \
  --decoration "/Users/raymuschang/Documents/Shotlist Workflows/hieroglyphics_bg.png" \
  --feedback-module feedback_data \
  --char-overrides "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_char_overrides.json" \
  --loc-aliases "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_loc_aliases.json"
open "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html"
```

## Final report

One block: show name, episode, sets rendered, output path. Concise.

## Authentication

Handled by `auth.py` in the working directory. Token is valid; do not re-run OAuth.

## Skill reference

Full spec at `~/.claude/skills/production-gallery/SKILL.md`. Source at `~/.claude/skills/production-gallery/build_gallery.py` (parametric port of the original `build_pharaoh_gallery_production_v2.py`).
