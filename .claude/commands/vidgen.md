---
description: Generate Seedance 2.0 video for a storyboard set via BytePlus ARK API. Auto-resolves char/loc bible names → BytePlus asset_ids via Asset Library tab, attaches storyboard pencil iter as composition ref, builds inline Reference identities binding block from CHARACTERS bible. Subscription-paid via HK company's $1M wallet — $0 marginal until depletion.
argument-hint: <sheet-id-or-url> --set <N> --slot 1|2 [--sb-slot 1|2] [--duration 4-15] [--resolution 480p|720p|1080p] [--aspect 9:16|16:9] [--fast] [--confirm]   |   example: /vidgen <sheet> --set 1 --slot 1 --sb-slot 1 --confirm
---

User wants to generate a video cut for a storyboard set via Seedance 2.0 on BytePlus.

Their request: `$ARGUMENTS`

## Provider locked: BytePlus ARK Seedance 2.0
- Endpoint: `ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` (Singapore region)
- Auth: `BYTEPLUS_ARK_API_KEY` from `.env` (Bearer token)
- Models: `dreamina-seedance-2-0-260128` (standard) | `dreamina-seedance-2-0-fast-260128` (--fast)
- Wallet: HK parent company prepaid; subaccount `dearai`; project `D.AI`
- fal.ai is REMOVED. FLORA is REMOVED. BytePlus is the single path.

## Action — run directly, no dry-run

Parse `$ARGUMENTS` — extract sheet ID, set #, slot, optional flags, and any `@name` tokens.

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 byteplus_vidgen.py --sheet "<sheet>" --set <N> --slot <1|2> --sb-slot <1|2> [other flags] [--mentions @tara @minjun]
```

If user passes `--confirm`, the script prints detected refs + prompt, waits [y/N] before submitting. **Use this gate liberally** — it's the cheapest line of defense against ref bleed and bad prompts.

The dashboard's per-set Generate V1 / V2 buttons fire 2 parallel jobs each, mapping `--sb-slot` to which storyboard iter is the composition anchor:
- Click V1 → SB iter 1 (col G) → 2 jobs (output_slot 1+2 written to SP!M+!N)
- Click V2 → SB iter 2 (col H) → 2 jobs

## How it actually works (under the hood)

### 1. Read inputs from the sheet

Body comes from **`Shotlist!Q`** (NOT Storyboard Prompts!C — that's the pencil-art prompt, separate concern). For set N, concatenate Q-formula output for shots `(N-1)*5+1`..`N*5`.

Globals come from **Video Prompts** tab:
- `B1` — camera global (e.g. "Shot with Arri 35.")
- `B2` — audio/dialogue global (trilingual directive for Sajangnim)
- `B3` — setting global

### 2. Detect refs from Asset Library

By default, `detect_bible_refs(body, sh)` walks `Asset Library!A5:L500` finding rows where:
- Status = `Uploaded`
- Asset Code is set
- Name (or its split-word for chars, or alias for locations) matches body text

Sorted **CHARACTERS first, LOCATIONS second** (priority for the 6-ref cap).

If the user includes `@name` tokens, pass them through as `--mentions @tara @minjun ...`.
That disables body auto-detect and attaches only matching Asset Library rows whose
Name contains the stripped token.

**Multiple Asset Library rows can share the same canonical Name** — e.g. `PARK MIN-JUN` appears as both an `Image` row (still photo) and a `Video` row (face loop). Both get attached. Dedup is by `asset_code`, not by name.

### 3. Pull the storyboard pencil ref

Read `Storyboard Prompts!G{10+set}` (sb-slot 1) or `H{10+set}` (sb-slot 2). Convert from Drive `/view` URL → `https://lh3.googleusercontent.com/d/<id>=w2048` direct binary URL. (BytePlus rejects `/view` URLs as `InvalidParameter.UnsupportedImageFormat`.)

### 4. Build content[] payload

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {"type": "text", "text": "<assembled prompt — see §5>"},
    {"type": "image_url", "image_url": {"url": "https://lh3.googleusercontent.com/d/<sb-iter>=w2048"}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": "asset://asset-..."}, "role": "reference_image"},
    {"type": "video_url", "video_url": {"url": "asset://asset-..."}, "role": "reference_video"},
    {"type": "audio_url", "audio_url": {"url": "asset://asset-..."}, "role": "reference_audio"}
  ],
  "ratio": "9:16",
  "duration": 15,
  "resolution": "480p",
  "watermark": false
}
```

**CRITICAL — `asset://` is the ONLY format that bypasses face moderation.**
- `asset://asset-<id>` → 200, moderation bypassed
- bare `asset-<id>` → 400 InvalidParameter
- TOS URL from `GetAsset` (`https://ark-media-asset-...volces.com/...`) → 400 PrivacyInformation moderation reject

The TOS URL works for asset INSPECTION but fails as a content[] ref because BytePlus content moderation scans all plain HTTPS URLs. Never resolve `asset://`. Pass through verbatim.

**Cap at 6 refs.** Past that Seedance 2.0 dilutes identity. Storyboard sits at #1, then chars (with image+video pairs together), then locations.

### 5. Prompt assembly

```
<camera global>
Follow the storyboard reference for composition, framing, and blocking on every shot.
Reference identities:
- Reference image #1 = STORYBOARD pencil sketch — composition anchor for camera angle, blocking, depth.
- Reference image #2 = TARA ANJANI — Junior chef, 29, white chef coat...
- Reference image #3 = LEE JOON-HO — Owner & exec chef, 37, executive chef whites...
- Reference image #4 = PARK MIN-JUN — Sous chef, 33, sous chef whites...
- Reference video #5 = PARK MIN-JUN face loop — use this to anchor PARK MIN-JUN's identity in every shot where PARK MIN-JUN appears. Wardrobe and attire come from the still PARK MIN-JUN reference image.
- Reference audio #6 = PARK MIN-JUN voice sample — use this voice for ALL dialogue spoken by PARK MIN-JUN.
- Reference image #7 = Hanbyeol Bistro Kitchen (location / background reference)
<audio/dialogue global>
<setting global>
Documentary editorial photography aesthetic, natural skin texture...
VERTICAL 9:16 drama format. The video should follow these shots in sequence:
<5-shot body from Shotlist!Q>
```

The `Reference identities:` block (fix B) is **auto-built from CHARACTERS bible at submit time** using each row's Role / Age / Wardrobe / Personality. Without this block, Seedance scrambles identities (face matched to wrong character). With it, identity binds correctly.

### 6. Submit + poll

`POST {ARK_BASE}/contents/generations/tasks` → returns `{"id": "cgt-..."}`. Poll `GET .../tasks/<id>` every 15s. Status flow: `queued` → `in_progress` → `succeeded` (or `failed`/`expired`/`cancelled`). Typical wall time at 480p/15s: 90-180s.

### 7. Drive upload + sheet writeback

- Download MP4 from `result.results.video_url` (24h Drive expiry)
- Upload to `<show>/videos/set-NN/video-iteration-{slot}-{resolution}-{duration}s.mp4`
- Archive any same-name existing file → `set-NN/archive/{ts}_<filename>`
- Set anyone-with-link reader on new file
- Save local copy to `~/Desktop/<Project> Generated Videos/set-{set_num:02d}-iter-{slot}-{resolution}-{duration}s.mp4`
- Write Drive view URL to **`Storyboard Prompts!M{row}`** (slot 1) or **`!N{row}`** (slot 2) — NOT L (L is Location SOT)

`SLOT_TO_COL = {1: "M", 2: "N"}` — locked.

### 8. Asset Library bookkeeping

Update `Asset Library!I` (Used In Eps) + `!L` (Last Used) for each ref's row.

### 9. Cost log

Append to `.byteplus_expense.json` (rough estimate: 480p ≈ $0.05/sec; 15s ≈ $0.75). Real billing on BytePlus dashboard is in CNY 毫 (0.0001元) — divide raw number by 10,000 then ÷ 7.2 for USD.

720p / 1080p still available via `--resolution` flag for hero deliverables.

## Asset library — what to upload, what to skip

Only **CHARACTERS** and **LOCATIONS** need BytePlus asset library entries (they trigger face moderation as plain HTTPS URLs without the `asset://` bypass).

**Skip uploading:** COSTUME, PROPS, EFFECTS — pass to vidgen as plain HTTPS Drive URLs. No moderation issue.

**Per character, ideally:**
- Image still (clean studio neutral with full attire) — locks wardrobe
- 2-15s face video (silent, slight head turns, neutral lighting) — locks face identity
- 2-15s voice clip (clean speech sample) — locks voice timbre/accent

All three rows in Asset Library use the same canonical Name (e.g. `PARK MIN-JUN`). `detect_bible_refs` attaches all three to any shot mentioning the character.

## URL format reference

| Use case | URL pattern |
|---|---|
| Storyboard pencil iter (composition ref) | `https://lh3.googleusercontent.com/d/<id>=w2048` |
| Character/location asset (bypass face mod) | `asset://asset-<id>` |
| Voice / audio asset | `asset://asset-<id>` |
| Lazy-load thumbnail (dashboard) | `https://lh3.googleusercontent.com/d/<id>=w900` |
| Dashboard inline video player | `https://drive.google.com/file/d/<id>/preview` (iframe) |

Drive `/view?usp=drivesdk` URLs are HTML viewer pages and rejected by BytePlus.
TOS signed URLs from `GetAsset` work for inspection only — moderated when submitted.

## Spend ballpark

- 480p / 5s ≈ $0.25 USD per gen
- 480p / 15s ≈ $0.75 USD per gen (current default)
- 720p / 15s ≈ $1.20 USD per gen
- 1080p / 15s ≈ $1.98 USD per gen (hero deliverables only)
- HK wallet had $1M credit; ~$15 used as of 2026-05-05 evening session

Per-click cost (V1 or V2 button): 2× single-gen since each click fires 2 parallel jobs.

## Manual @-mention override

```text
/vidgen sheet --set 1 --slot 1                        → auto-detect
/vidgen sheet --set 1 --slot 1 @tara @minjun @kitchen → only these 3 refs
/vidgen sheet --set 1 --slot 1 @galih                 → only Galih
```

## When things break

- **InvalidParameter.UnsupportedImageFormat on `image_url`** → Drive `/view` URL leaked into refs. Convert to `lh3.googleusercontent.com/d/<id>=w2048`.
- **InputImageSensitiveContentDetected.PrivacyInformation** → asset got resolved to TOS URL somewhere. Use raw `asset://` only.
- **Identity scrambled** (Min-jun face on Joon-ho's wardrobe) → check the Reference identities block is being built; if it is and still scrambling, drop other-character refs from this set's gen (reduce ref pool).
- **Submit silently dropped** → check `submit_seedance_task` for skip clauses on URL scheme. Plain HTTPS for storyboards/non-face refs is fine; only TOS URLs (which contain real-person photos) trigger moderation.
- **Body empty error** → `Shotlist!Q` formulas not populated for that set. Check Q is a live formula (`=...`) not pasted text.
