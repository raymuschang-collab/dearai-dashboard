---
description: Upload generated bible refs from Asset Library to BytePlus, skipping already-uploaded rows.
argument-hint: --sheet <id-or-url> [--bibles characters,locations,props,costume,effects] [--force]
---

User invoked /byteplus-upload-all. Args: `$ARGUMENTS`

## Action

Wrap `byteplus_asset_upload.py` in all-bibles mode. The script is idempotent: rows with Asset Code or Status=Uploaded are skipped unless `--force` is passed.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
/usr/bin/python3 byteplus_asset_upload.py --all-bibles $ARGUMENTS
```

## Notes

Asset Library is the source of truth for @name → BytePlus asset code resolution. Do not hand-edit generated asset codes unless replacing a known bad upload.
