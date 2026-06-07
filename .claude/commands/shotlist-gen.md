---
description: Atomize a locked script into the DearAI v2.2 shotlist + text-only bible tabs.
argument-hint: --script <path> --sheet <id-or-url> --name <show name> [--locale jakarta|manila|seoul|generic] [--dry-run]
---

User invoked /shotlist-gen. Args: `$ARGUMENTS`

## Action

Parse `$ARGUMENTS` and run the atomizer. `--dry-run` prints the planned shot and bible rows without writing to Sheets.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
/usr/bin/python3 shotlist_gen.py $ARGUMENTS
```

## Guardrails

- Reuses `auth.py`; do not reimplement OAuth.
- Writes Shotlist data columns only and reapplies live prompt/translation formulas.
- Populates CHARACTERS, LOCATIONS, PROPS, COSTUME, EFFECTS with text rows only. Image refs are generated later.
- Never paste static text into Shotlist Prompt/Bahasa Prompt or Storyboard Prompts C/D.
