---
description: Destructively delete BytePlus assets listed in Asset Library; dry-run unless --confirm is passed.
argument-hint: --sheet <id-or-url> [--scope replaced|all] [--confirm]
---

User invoked /byteplus-flush. Args: `$ARGUMENTS`

## Action

This is destructive. Default scope is `replaced`, and without `--confirm` the script only prints what would be deleted.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
/usr/bin/python3 byteplus_flush.py $ARGUMENTS
```

Only pass `--scope all --confirm` when the user explicitly asks to nuke the entire Asset Library.
