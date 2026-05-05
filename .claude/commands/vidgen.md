---
description: Generate Seedance 2.0 video for a storyboard set via BytePlus ARK API. Auto-resolves bible names → BytePlus asset_ids via Asset Library tab. Subscription-paid via HK company's $1M wallet — $0 marginal until depletion.
argument-hint: <sheet-id-or-url> --set <N> --slot 1|2 [--duration 4-15] [--resolution 480p|720p|1080p|2K] [--aspect 9:16|16:9|...] [--fast] [--confirm]   |   example: /vidgen <sheet> --set 1 --slot 1 --confirm
---

User wants to generate a video cut for a storyboard set via Seedance 2.0 on BytePlus.

Their request: `$ARGUMENTS`

## Provider locked: BytePlus ARK Seedance 2.0
- Endpoint: `ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` (Singapore region)
- Auth: `BYTEPLUS_ARK_API_KEY` from `.env` (Bearer token)
- Models: `doubao-seedance-2-0-260128` (standard) | `doubao-seedance-2-0-fast-260128` (--fast)
- Wallet: HK parent company prepaid; subaccount `dearai`
- fal.ai is REMOVED. FLORA is REMOVED. BytePlus is the single path.

## Action — run directly, no dry-run

Parse `$ARGUMENTS` — extract sheet ID, set #, slot, optional flags.

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 byteplus_vidgen.py --sheet "<sheet>" --set <N> --slot <1|2> [other flags]
```

If user passes `--confirm`, the script prints detected refs + prompt, waits [y/N] before submitting. **Use this gate liberally** — it's the cheapest line of defense against ref bleed and bad prompts.

## How it actually works (under the hood)

1. Read `Storyboard Prompts!C<10+set_num>` body
2. Walk Asset Library tab, find bible entries mentioned in body where Status="Uploaded"
3. Compose prompt: video globals (B1+B2 of Video Prompts) + realism anchor + 9:16 directive + body
4. Submit task to BytePlus ARK with content array: text prompt + asset_ids as `image_reference` (role="subject")
5. Poll `/contents/generations/tasks/{id}` every 15s until `succeeded`
6. Download MP4 from results URL (24-hour expiry — must be fast)
7. Upload to Drive `videos/set-NN/`, archive prior file
8. Write URL to `Storyboard Prompts!L<row>` (slot 1) or `M<row>` (slot 2)
9. Update Asset Library `Last Used` (col L) for each detected asset
10. Append to `.byteplus_expense.json` for cumulative spend tally

## Asset Library lookup is the new ref system

Old fal.ai pattern: scan body, pull iter URLs from each bible's iter-1 col, pass as image refs. Brittle.

New BytePlus pattern: scan body, look up Asset Library tab → get asset_codes → pass as references to Seedance. Single source of truth, less drift.

The Asset Library tab is required. If it doesn't exist or is empty for the show, run `/asset-library <sheet> --seed-from-bibles` first, then `/byteplus-upload <sheet>` to populate asset codes.

## Cost expectations

| Resolution × duration | Standard tier | Fast tier (--fast) |
|---|---|---|
| 720p × 8s | ~$0.64 | ~$0.32 |
| 1080p × 15s | ~$1.98 | ~$0.99 |
| 2K × 15s | ~$3.00 | ~$1.50 |

vs the old fal.ai $4.50/15s/1080p — **3× cheaper at standard tier, 6× cheaper at fast.**

## Final report

One block: set #, slot, refs detected, BytePlus task_id, Drive URL, sheet cell written, estimated cost.

## Authentication

- `auth.py` for Drive + Sheets (token.json valid)
- `BYTEPLUS_ARK_API_KEY` in `.env`
- `BYTEPLUS_ACCESS_KEY` + `BYTEPLUS_SECRET_KEY` only needed for asset library upload (separate command)

## Don't ask, just do

User invoked the slash explicitly. Skip diff/confirm. If args are malformed (no set #, no sheet), ask once. Otherwise fire.

If a ref is missing (no Asset Library entries for detected names), proceed text-only — flag inline but don't block.
