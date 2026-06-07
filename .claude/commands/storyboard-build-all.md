---
description: Build the Storyboard Prompts tab on every episode Sheet in a parent Drive folder.
argument-hint: <parent-folder-id-or-url>
---

User wants to batch-build storyboard tabs for every episode Sheet in a single Drive folder.

Parent folder: `$ARGUMENTS`

If `$ARGUMENTS` is empty, ask the user for the parent folder ID. Do NOT silently default. (The "LAST RIDE (Jakarta Edition)" folder is `1nSOdfqgGjMWaSzy3wE_MSP_XAxlLoT3z` — only use it if the user names it.)

## Action — run directly, no dry-run, no confirmation

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 storyboard_build.py --all-in-folder "$ARGUMENTS"
```

The script is idempotent. Sheets that already have a complete Storyboard Prompts tab are skipped. The `--force` flag is never passed by default — only if the user explicitly says "rebuild all from scratch."

## Final report

One line per episode showing build / skip / fail, then a summary count.

If any sheet fails, surface its name and the stderr line; the rest still complete. Do not retry failures automatically.

## Notes

- Each sheet's `storyboards/` folder is created in the SAME parent as that Sheet, not at the batch-folder level. Episodes in different parents (sub-projects) get their own storyboards/ subtree correctly.
- Authentication is handled by `auth.py` in the working directory. Token is valid; do not re-run OAuth.
