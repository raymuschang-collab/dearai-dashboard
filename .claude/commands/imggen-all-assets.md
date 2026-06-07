---
description: Generate every missing bible reference image across selected bible tabs.
argument-hint: --sheet <id-or-url> [--bibles characters,locations,props,costume,effects] [--force] [--dry-run]
---

User invoked /imggen-all-assets. Args: `$ARGUMENTS`

## Action

Run the idempotent asset-image orchestrator. It loops existing scripts:

- `character_generate.py` for CHARACTERS rows missing image URLs → Higgsfield `gpt_image_2`.
- `location_generate.py` for LOCATIONS rows missing wide/mid URLs → Reve direct, not Higgsfield.
- `bible_generate.py` for COSTUME, PROPS, EFFECTS rows missing refs → Higgsfield `nano_banana_2`.

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 imggen_all_assets.py $ARGUMENTS
```

`--force` regenerates rows that are already Done. `--dry-run` prints the commands without firing image jobs.
