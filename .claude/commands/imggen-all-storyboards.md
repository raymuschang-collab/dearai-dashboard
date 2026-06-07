---
description: Generate storyboard images for every Pending set. Default = featureless stick figures (sajangnim aesthetic). Override with --pencil / --photoreal.
argument-hint: --sheet <id-or-url> [--stick|--pencil|--photoreal|--sheet] [--force]
---

User invoked /imggen-all-storyboards. Args: `$ARGUMENTS`

## Action

Wraps `storyboard_generate.py` with `--style stick` as the default — every Pending set is generated with featureless stick-figure preamble FORCED at runtime, regardless of what's in the sheet's B1:B4 globals.
Provider: Higgsfield `gpt_image_2`.

Style flags (mirror `/imggen`):
- `--stick` (default) — forced stick figures, sajangnim aesthetic
- `--pencil` — director-pad pencil sketch
- `--photoreal` — full photoreal stills (only for hero deliverables, expensive)
- `--sheet` — legacy: use the sheet's B1:B4 globals

Resolve the user's args. If they didn't pass any style flag, default to `--style stick`. If they passed `--pencil`, swap to `--style pencil`. Etc.

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 storyboard_generate.py --sheet "<sheet>" --style <stick|pencil|photoreal|sheet> [--force]
```

`--force` regenerates Done sets. Use sparingly — paid generations.
