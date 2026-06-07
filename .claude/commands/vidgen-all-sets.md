---
description: Sequentially generate BytePlus videos for every Pending storyboard set.
argument-hint: --sheet <id-or-url> [--max-set N] [--slot 1|2] [--mentions @tara @minjun] [--dry-run]
---

User invoked /vidgen-all-sets. Args: `$ARGUMENTS`

## Action

Run the sequential vidgen orchestrator. It reads Storyboard Prompts rows with Status=Pending and fires one `byteplus_vidgen.py --set N --slot <slot>` at a time to avoid moderation/concurrency issues.
If `--mentions @tara @minjun ...` is included, that explicit ref override propagates to every set's gen run.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
/usr/bin/python3 vidgen_all_sets.py $ARGUMENTS
```

Use `--dry-run` to print the set list and commands without submitting BytePlus jobs.
