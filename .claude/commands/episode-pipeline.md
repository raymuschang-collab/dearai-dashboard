---
description: Run the full DearAI episode pipeline from optional shotlist generation through asset/storyboard/video generation.
argument-hint: --sheet <id-or-url> [--script <path>] [--name <show name>] [--from-step N] [--to-step M] [--skip 2,3] [--dry-run]
---

User invoked /episode-pipeline. Args: `$ARGUMENTS`

## Steps

1. `shotlist_gen.py` if `--script` is provided.
2. `imggen_all_assets.py` — characters via Higgsfield `gpt_image_2`; costume/props/effects via Higgsfield `nano_banana_2`; locations via Reve direct.
3. `byteplus_asset_upload.py --all-bibles`.
4. `storyboard_generate.py` — storyboards via Higgsfield `gpt_image_2`.
5. `vidgen_all_sets.py` — videos via BytePlus Seedance, default 480p.

Each step gates on previous success. `--from-step`, `--to-step`, and `--skip` are resume controls.

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 episode_pipeline.py $ARGUMENTS
```

`--dry-run` is passed to wrapper steps that support it and suppresses direct upload/storyboard generation steps.
