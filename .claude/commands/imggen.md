---
description: Generate 2 pencil-sketch storyboards (iter 1+2) directly via nano_banana_2 with bible references. Auto-injects refs from CHARACTERS / LOCATIONS / PROPS / COSTUME / EFFECTS bibles. NSFW fallback to gpt_image_2 if any panel rejects. Writes pencil URLs to G, H of Storyboard Prompts. Photoreal stage (gpt_image_2 → J, K) is DEPRECATED — use `--photoreal` flag to force-generate it for legacy compatibility.
argument-hint: set <set_num> [--photoreal]     |     example: /imggen set 4
---

User wants all 4 storyboard iterations for one set, generated in one shot.

Their request:

```
$ARGUMENTS
```

## Parse args

Standard form: `set <N>` (e.g. `set 4`). Strip the literal word `set` — it's a sentence connector, not an arg. Take the first integer as the set number.

Bare `<N>` also works.

If no integer parseable, ask once for `set <N>` and stop.

## Steps

### 1. Read body from sheet

Sheet ID: `1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE`
Tab: `Storyboard Prompts`
Row: `10 + set_num`
Read col C (body) + col E (storyboards/set-NN/ Drive folder URL).

### 2. Auto-detect refs from all 5 bibles

Same logic as `/set` command — scan body for matches against:
- **CHARACTERS** col A (with `ISFET SPAWN → ISFET SPAWN (2)` override). **Cap 5** — covers worst-case sets like Set 4 (KHENSU + AHMOSE + TEHUTI + SESHET + ISFET SPAWN (2)). **Always include ISFET SPAWN (2) if mentioned** — it carries scale conditioning the model needs. Pull col T (iter 1 URL).
- **LOCATIONS** col A with the alias map (`bazaar` → "Peasant Bazaar", `rooftop` → "Rooftop above the Bazaar", etc.). Cap 1. Pull only `wide` variant from col J.
- **PROPS** col A with case-insensitive substring match. Cap 1. Pull col G.
- **COSTUME** col A with first-word match. Cap 1. Pull col G.
- **EFFECTS** col A with substring match. Cap 1. Pull col G.

Total cap: 9 image refs. Build as `https://lh3.googleusercontent.com/d/{file_id}=w1024` URLs.

Print full ref list inline (`KHENSU char`, `Peasant Bazaar wide`, `Sun-Guard attire costume`, etc.) so user can spot misses.

### 3. Build the pencil prompt

**Direct pencil-from-bibles prompt** (for iter 1+2 via `nano_banana_2`):

```
Shot with arri 35.
No music.

Multi-panel storyboard layout: 21:9 wide canvas, EXACTLY {N} pencil panels
arranged HORIZONTALLY (left-to-right). Each panel a vertical 9:16 frame.
Panels separated by thin vertical black divider lines. Each panel labeled
at bottom-center with: SHOT NUMBER, camera angle/movement, brief 3-5 word
description.

Render in hand-drawn graphite/charcoal on warm tan paper aesthetic — soft
pencil lines, light cross-hatching for shadows, no color, monochrome
warm-paper background. Sketch quality, NOT photoreal. Storyboard for film
production reference.

Use the provided character/location/prop/costume reference images for
identity, body shape, and location architecture — but render them in the
pencil-sketch style described above.

SEQUENCE:

[body from col C]
```

Where `{N}` = number of shots in the body (typically 5, sometimes 3-4 for
short sets like Set 11).

### 4. Fire generation jobs — TWO STAGES

**Stage 1 (always):** photoreal via gpt_image_2.
**Stage 2 (default ON, suppress with `--no-pencil`):** auto-derive pencil sketches from the Stage 1 outputs.

```json
// Stage 1 — photoreal (count 2 → iter 1 + iter 2 → cols J + K)
{
  "model": "gpt_image_2",
  "prompt": "<photoreal prompt>",
  "aspect_ratio": "16:9",
  "count": 2,
  "quality": "high",
  "resolution": "2k",
  "medias": [<all detected refs as {value, role:"image"}>]
}
```

After Stage 1 completes, capture the 2 photoreal output URLs (iter 1 from J, iter 2 from K). These become *image references* for Stage 2.

```json
// Stage 2 Job A — pencil derived from iter 1 (writes to col G)
{
  "model": "nano_banana_2",
  "prompt": "<pencil derivation prompt — see below>",
  "aspect_ratio": "21:9",
  "count": 1,
  "resolution": "2k",
  "medias": [{"value": "<iter 1 photoreal URL>", "role": "image"}]
}

// Stage 2 Job B — pencil derived from iter 2 (writes to col H)
{
  "model": "nano_banana_2",
  "prompt": "<pencil derivation prompt — see below>",
  "aspect_ratio": "21:9",
  "count": 1,
  "resolution": "2k",
  "medias": [{"value": "<iter 2 photoreal URL>", "role": "image"}]
}
```

**Pencil derivation prompt (STRICT TEMPLATE LOCK — required, otherwise nano_banana_2 reinterprets composition instead of style-transferring):**

```
STRICT IMAGE-TO-IMAGE STYLE TRANSFER. Take the input source image and convert
ONLY its rendering style — DO NOT change anything else. Keep the EXACT same
number of panels, the EXACT same panel boundaries and dividers, the EXACT same
character positions in each panel, the EXACT same camera framing and angle for
each panel, the EXACT same panel labels at the bottom of each panel. The ONLY
difference between input and output should be the rendering style: photoreal →
graphite pencil sketch on warm tan paper background. Soft pencil lines, light
cross-hatching for shadows, no color, monochrome. Preserve every compositional
detail of the source. Treat the input image as a STRICT TEMPLATE — same panels,
same shots, same positions, same framings, same labels. Only the visual treatment
changes from photo to pencil sketch. 21:9 wide canvas.
```

NOTE: this phrasing was tuned after observing that the milder "preserve composition" prompt caused nano_banana_2 to creatively reinterpret panels rather than match them. The "STRICT TEMPLATE" + "ONLY rendering style changes" framing keeps composition locked.

**NSFW FALLBACK:** if `nano_banana_2` returns `status: "nsfw"` for any pencil derivation (sometimes triggers on battlefield/violence panels), automatically retry the same call on `gpt_image_2` with the same prompt + reference. gpt_image_2 has a different (more permissive) moderation threshold for the same content. Cost: ~7 cr instead of 2 cr per panel — small premium for guaranteed completion.

Capture all 4 returned job IDs (Stage 1: 2 jobs from count=2, Stage 2: 2 jobs).

### 5. Poll until all 4 completed

Pattern: launch a `Bash` `sleep 90` in `run_in_background: true`. When timer fires, `mcp__...__job_display` with the 4 job IDs. Repeat until each shows `status: "completed"`. NB Pro typically completes in 30-60s, gpt-image-2 in 90-150s.

### 6. Download all 4 + upload to Drive

For each completed job, download `results.rawUrl`. Upload to the set-NN/ folder (col E):

| Iter | Filename | Source | Default |
|------|----------|--------|---------|
| 1 (photoreal) | `iter-1-photoreal.png` | Stage 1 image 0 (gpt_image_2) | ✓ |
| 2 (photoreal) | `iter-2-photoreal.png` | Stage 1 image 1 (gpt_image_2) | ✓ |
| 3 (pencil from iter 1) | `iter-3-pencil-from-1.png` | Stage 2 Job A (nano_banana_2) | ✓ (suppress with `--no-pencil`) |
| 4 (pencil from iter 2) | `iter-4-pencil-from-2.png` | Stage 2 Job B (nano_banana_2) | ✓ (suppress with `--no-pencil`) |

Trash any existing same-name file in the folder first. Set permission to anyone-with-link reader.

### 7. Write 4 URLs to sheet

`Storyboard Prompts` row `10 + set_num`:
- Col **J** ← iter 1 photoreal URL (gallery "Iteration 1 (photoreal)")
- Col **K** ← iter 2 photoreal URL (gallery "Iteration 2 (photoreal)")
- Col **G** ← iter 3 pencil URL (gallery "Iteration 3 (pencil from iter 1)") — derived from J
- Col **H** ← iter 4 pencil URL (gallery "Iteration 4 (pencil from iter 2)") — derived from K

NOTE: cols G/H legacy content was the old `storyboard_gen.py` stick-figure pencils; those get overwritten by the new pencil-from-photoreal flow.

### 8. Rebuild gallery + open

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 build_pharaoh_gallery_production_v2.py
open "/Users/raymuschang/Desktop/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html"
```

The Storyboards tab shows all 4 iters stacked vertically in the storyboards column for that set.

## Final report

Single block: set #, body length, refs auto-injected, 4 Drive URLs, sheet cells written. Concise.

## Cost

Each Nano Banana Pro run ≈ 2 cr × 2 = 4 cr.
Each GPT Image 2 high 2K run ≈ 7 cr × 2 = 14 cr.
**Total per `/img-set N` invocation: ~18 cr.** (Cheap — image gen is far cheaper than video on Higgsfield.)

## Don't ask, just do

User invoked the slash explicitly. Skip the diff/confirm flow. Single block of output as it runs, final URLs when done.

If a ref is missing or bible match fails, proceed text-only — flag it inline but don't block.
