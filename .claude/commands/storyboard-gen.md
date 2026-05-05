---
description: Generate 2 stick-figure storyboard iterations per Pending set via fal.ai nano-banana-2; upload to Drive; write URLs back to the sheet.
argument-hint: <sheet-id-or-url> [--set N] [--force]
---

User wants to generate storyboards for one episode Sheet's Storyboard Prompts tab.

Args: `$ARGUMENTS`

If `$ARGUMENTS` is empty or doesn't look like a Sheet ID / Sheets URL, ASK the user which sheet to target. Do not default — running on the wrong sheet costs money.

## Action — run directly, no dry-run, no confirmation

The script is idempotent: it only generates Pending sets, skips Done ones. If the user wants to regenerate, they pass `--force` explicitly.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 storyboard_generate.py --sheet "$ARGUMENTS"
```

If the user passed extra flags after the sheet ID (e.g. `--set 5`, `--force`, `--aspect 16:9`), include them in the command.

## Cost expectations

- Default: 21:9 aspect, 1K resolution, 2 iterations per set = ~$0.10/set
- A 14-set episode costs ~$1.40 (28 generations)
- Generation takes ~30–60s per image; 14 sets ≈ 12–25 min wall time

## Final report

One block per set as the script runs (live), then a summary:

```
TOTAL: N done, M skipped, K failed
```

If any sets fail, surface the specific error from column I of the sheet so the user can decide whether to retry. Common failures:
- `invalid key credentials` — check FAL_KEY in .env
- `no images returned` — model issue, retry usually works
- `bad folder url` — Storyboard Prompts tab D column is missing/malformed

## Schema requirement

The script requires the 9-column v2.2 schema on the Storyboard Prompts tab. If it's still on the legacy 6-col schema, run `/storyboard-build <sheet-id>` first to migrate (safe and idempotent).

## Authentication

- Drive + Sheets: handled by `auth.py` (token.json valid, OAuth not re-run)
- fal.ai: `FAL_KEY` loaded from `.env` in the working directory
