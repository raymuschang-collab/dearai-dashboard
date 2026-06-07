# HANDOFF — Carousel & Static Post Pipeline (Source-of-Truth Architecture)

**Date**: 2026-05-02
**For**: another Claude session in a different working directory
**Owner**: Raymus / dearai.com (SEA microdrama producer)
**Sibling pipeline**: video shotlist (lives at `/Users/raymuschang/Documents/Shotlist Workflows/`)

---

## TL;DR

We're scaffolding a Google-Sheet-based source-of-truth for **carousel posts** and **static (1-panel) posts** that mirrors the existing video-shotlist architecture. The atomic unit shifts from **shot → panel**. A static post is a carousel with N=1, so one schema handles both. Three Sheet tabs, three new bibles, three new scripts, three new slash commands. **Two design calls are still open and need user confirmation before code lands.**

This doc is self-contained — it does NOT require reading the video pipeline first, but referencing it is recommended (sibling architecture, same auth, same conventions).

---

## Why this exists

Raymus runs a SEA microdrama studio and has built a working AI-driven video pipeline (Pharaoh Ep 1 just shipped). The video pipeline keys off a granular per-shot Sheet that drives auto-ref-detection, prompt assembly, gen routing, and gallery rendering. He wants the **same level of granularity for social posts** — both multi-panel carousels and single-panel statics — so that the same producer discipline transfers across formats.

**The design call**: don't build a separate "post system." Build a **parallel pipeline** that reuses the same auth, same bibles, same auto-detect logic, same iteration discipline. The atomic unit just changes.

---

## Mental model — shotlist → post-list mapping

| Video shotlist | Post-list equivalent | Notes |
|---|---|---|
| Shot # | Panel # | Atomic ID |
| Set (groups 5 shots) | **Carousel ID** (groups N panels) | Static = N=1 under one ID |
| Length (s) | **Reading Time (target sec)** | Pacing budget per panel |
| Shot Type | **Panel Function** | hook / context / data / quote / proof / cta / payoff |
| Camera Movement | **Composition** | center / thirds / full-bleed / split / grid / asymmetric |
| Shot Description | **Visual Brief** | What the camera sees |
| Tone of Voice | **Tone** | Bracketed, e.g. `(deadpan)`, `(quiet flex)` |
| Dialogue/VO | **Headline + Subhead + Body + CTA** | Spoken → on-panel typography |
| Music/SFX | *(drop)* | No audio |
| Location | **Setting/Backdrop** | Same |
| Time of Day | **Mood/Lighting** | Same intent, renamed |
| Characters / Costume / Props / Effects | Same — bibles unchanged | |
| Refs Detected — Chars / Loc/Prop/Costume/FX | Same — auto-populated by audit script | |
| Storyboard Set | **Carousel ID** (same role) | |

Five conceptual fields are NEW to the post pipeline (no video equivalent):

- **Panel Function** (hook/proof/cta/payoff — replaces Shot Type)
- **Type Hierarchy** (typography rules — irrelevant in video)
- **Continuity Anchor** (visual carry from panel to panel — replaces temporal cut)
- **Swipe Trigger** (carousel-specific engagement mechanism)
- **Hook Score** (1–5 producer-rated; only meaningful on Panel Position 1/N)

---

## Three-tab Sheet architecture

### Tab 1: **Posts** (atomic panel list, equivalent of Shotlist)

One row per panel. Static post = 1 row with `Panel Position = "1 of 1"`.

| Col | Field | Notes |
|---|---|---|
| A | Panel # | |
| B | Carousel ID | e.g. `dearai-launch-001`, `static-014` — namespaced |
| C | Panel Position | `"1 of 5"`, `"3 of 5"`, `"1 of 1"` |
| D | Panel Function | hook / context / proof / cta / payoff |
| E | Format | Image / Image+Text / Pure Text / Loop |
| F | Aspect Ratio | 4:5 / 1:1 / 9:16 / 16:9 |
| G | Composition | center / thirds / full-bleed / split / grid |
| H | Visual Brief | "Wide of KHENSU on rooftop, golden hour, 40% bottom-space reserved for headline" |
| I | Tone | bracketed, e.g. `(urgent)` |
| J | Headline | BIG on-panel text |
| K | Subhead | supporting text |
| L | Body Copy | long-form (LinkedIn, X threads) |
| M | CTA | `Swipe →`, `Link in bio`, etc |
| N | Type Hierarchy | H1 / H2 / body |
| O | Setting/Backdrop | |
| P | Mood/Lighting | |
| Q | Characters | comma-separated bible names |
| R | Costume | bible refs |
| S | Props | bible refs |
| T | Effects | bible refs |
| U | Continuity Anchor | what carries from prev panel (color / gesture / character / object) |
| V | Swipe Trigger | question / cut-off image / cliffhanger |
| W | Hook Score (1-5) | only meaningful on Panel 1/N |
| X | Refs Detected — Chars | auto by `refs_audit_posts.py` |
| Y | Refs Detected — Loc/Prop/Cost/FX/Type | auto by `refs_audit_posts.py` |
| Z | Prompt | assembled |
| AA | Iter 1 URL | |
| AB | Iter 2 URL | cache-bypass repro OR alt composition (see open call #2) |
| AC | Final URL | |
| AD | Notes | |
| AE | Status | Pending / In Review / Approved / Done |

**31 columns.** Header at row 1, data rows from row 2.

### Tab 2: **Post Prompts** (carousel rollup, equivalent of Storyboard Prompts)

One row per carousel. Mirrors the set-of-5 storyboard pattern. Header at row 10, data rows from row 11 (so row = 10 + carousel_index, parallel to video pipeline convention).

| Col | Field |
|---|---|
| A | Carousel ID |
| B | Title |
| C | Platform | IG / X / LinkedIn / TikTok / Threads |
| D | Aspect Ratio | drives gen format |
| E | Total Panels |
| F | Body (assembled brief) | concatenation of per-panel visual briefs |
| G | Drive folder URL | `carousel-NN/` in Drive |
| H | Iter 1 URL (composite) | preview grid of all N panels |
| I | Iter 2 URL (composite) | cache-bypass dup OR alt set |
| J | Final composite URL | grid for review |
| K | Caption | the IG/X/LinkedIn caption proper |
| L | Hashtags | |
| M | CTA URL | link in bio / utm-tagged |
| N | Approved date | |
| O | Posted date | |
| P | Status | |

### Tab 3: **Post Globals** (per-show globals, equivalent of Video Prompts)

| Cell | Content | Required? |
|---|---|---|
| B1 | Brand voice + visual system | **REQUIRED** — e.g. "minimal sans-serif, ivory bg, Indonesian casual" |
| B2 | Platform constraints | **REQUIRED** — e.g. "IG 4:5 with 14% top/bottom safe-zones" |
| B3 | Campaign theme | **OPTIONAL** — only if campaign-wide visual hook persists |
| B4 | Setting global | **OPTIONAL** — only if a single backdrop persists across the carousel |
| B5+ | Translation pairs | OPTIONAL |

**Same per-show / not-default rule as video.** B3/B4 left blank by default in the build script. Only fill when the show genuinely has persistent context.

---

## New bibles (post-specific)

The 5 video bibles (CHARACTERS / LOCATIONS / PROPS / COSTUME / EFFECTS) carry over **unchanged**. Add three more for post production:

| Bible | What it holds | Match logic for `refs_audit` |
|---|---|---|
| **TYPOGRAPHY** | Named type styles: H1/H2/body, font, weight, size, kerning, color | first-word match against col A (cap 1) |
| **TEMPLATES** | Recurring layouts: "full-bleed quote", "split-vertical 60/40", "9-grid", "before-after" | substring match (cap 1) |
| **COLOR_PALETTES** | Named brand palettes with hex codes + sample swatch image | first-word match (cap 1) |

Bible structure mirrors video bibles: `Name | Description | metadata cols | Status | Iter 1 URL (col G) | Iter 2 URL`.

### Total ref budget per panel

```
carousel_iter (1)
+ characters     (≤4)
+ setting        (≤1)
+ props          (≤2)
+ fx             (≤1)
+ typography     (≤1)
+ template       (≤1)
+ palette        (≤1)
= max 12 refs
```

This is higher than video's 9-ref ceiling. Watch for model noise; if quality degrades, consider tightening to 10.

---

## Auto-detect logic (`refs_audit_posts.py`)

Identical pattern to `refs_audit.py` for video:

- **Characters** — whole-word, case-insensitive against CHARACTERS col A
- **Locations** — alias map (define per-show, similar to Pharaoh's `rooftop → Rooftop above the Bazaar`)
- **Props** — substring against PROPS col A (cap 2)
- **Costume** — first-word against COSTUME col A (cap 1)
- **Effects** — substring against EFFECTS col A (cap 1)
- **Typography** — first-word against TYPOGRAPHY col A (cap 1) ← NEW
- **Templates** — substring against TEMPLATES col A (cap 1) ← NEW
- **Color Palettes** — first-word against COLOR_PALETTES col A (cap 1) ← NEW

Scan text = `Visual Brief + Tone + Headline + Subhead + Body Copy + CTA`. Write detected list to cols X (chars) + Y (loc/prop/cost/fx/type/template/palette).

---

## Pipeline reuse — what to copy, what to write new

### Reuses unchanged (literally import or copy)

- `auth.py` — Drive + Sheets OAuth (token.json valid)
- bible auto-detect logic (port from `refs_audit.py` line-by-line, just add 3 new bibles)
- iter-1 / iter-2 cache-bypass strategy (CHARACTERS!T = iter 1, !U = iter 2 reproduction; replicate for new bibles)
- `--confirm` gate pattern (port from `fal_vidgen.py` to `post_generate.py`)
- the `set-NN/` Drive folder convention → becomes `carousel-NN/`

### Net new scripts to write

- `post_build.py` — analog of `storyboard_build.py`. Scaffolds the 3 tabs + new bibles. Idempotent. Only `--force` overwrites populated tabs.
- `post_generate.py` — fires per-panel image gens. Provider routing follows the existing rule (characters → gpt-image-2; locations/backdrops → Reve direct API; typography/templates → TBD, propose nano-banana-pro for low cost).
- `post_compose.py` — assembles the panel grid composite for review. **NEW** — no video equivalent. Takes N panel images + output canvas (4:5 IG carousel preview, etc), tiles them, writes to Post Prompts iter URL.
- `refs_audit_posts.py` — sweeps Posts tab and writes X+Y cols.

### Net new slash commands to define

| Command | Maps to | Behavior |
|---|---|---|
| `/post-build <sheet>` | `post_build.py` | scaffold the 3 tabs + new bibles |
| `/post-gen <carousel-N> iter <M>` | `post_generate.py` | fire panel gens for one carousel iter |
| `/post-compose <carousel-N>` | `post_compose.py` | build review grid composite |

Slash commands live in `.claude/commands/` (relative to working dir) as `.md` files. Use the existing `storyboard-build.md` / `set.md` files in `/Users/raymuschang/Documents/Shotlist Workflows/.claude/commands/` as templates — same frontmatter (description + argument-hint), same "Don't ask, just do" + "Final report" + "Authentication" sections.

---

## ⚠️ Two open design calls — get user confirmation before building

### Call 1: One rolling Posts tab per brand, OR one per campaign?

**Trade-off:**
- **Rolling per brand** (Raymus's lean recommendation): one Sheet for `dearai`, one for `pharaoh`, etc. Carousel IDs namespaced like `dearai-launch-001`, `pharaoh-promo-001`. Pros: easier scheduling across weeks, single archive per brand. Cons: tab grows long over time.
- **Per campaign**: one Sheet per campaign (`Pharaoh Promo Wave 1`). Pros: cleaner archive, mirrors episode-style separation in video. Cons: more Sheets to manage.

**Default if not yet confirmed**: rolling per brand. Confirm before scaffolding.

### Call 2: Iter-2 = deliberate ALT composition, OR near-identical cache-bypass dup?

**Trade-off:**
- **Alt composition** (e.g. iter-1 = headline-top, iter-2 = headline-bottom): producer picks the better one. Higher creative value per credit.
- **Near-identical cache-bypass dup** (current video pattern): forces two sample variants of the same intent. Useful when fal.ai/Higgsfield moderation hits.

**Default if not yet confirmed**: hybrid — alt comp by default; collapse to near-dup only when moderation forces it. Confirm before wiring `post_generate.py`.

---

## Recommended build order

1. **Build a reference Sheet first** (study artifact, NOT executable code). Same pattern Raymus used for the video pipeline at sheet ID `1dVY9X4D0jGouASUgHgsdE3FXL0Id3m2DFOJDTPAxpIw` — open that one in a tab and mirror the structure: README + 3 working tabs + bibles, with a tiny dummy carousel populated for clarity. Open with anyone-with-link reader. **This is the lowest-risk first step** — it lets Raymus visually validate the schema before any pipeline code commits.

2. **Resolve the two open design calls** (above).

3. **Write `post_build.py`** — the scaffolding script. Idempotent, no `--force` by default.

4. **Write `refs_audit_posts.py`** — port from `refs_audit.py`, add 3 new bibles.

5. **Write `post_generate.py`** — wire provider routing, `--confirm` gate, iter-1/iter-2 strategy per call #2.

6. **Write `post_compose.py`** — grid composite for review.

7. **Wire the 3 slash commands** — copy frontmatter from existing video commands.

8. **Build the first real carousel** end-to-end as a smoke test.

---

## Reference artifacts (copy-paste IDs/paths)

| Artifact | URL/ID/Path |
|---|---|
| **Video pipeline working dir** (sibling, study reference) | `/Users/raymuschang/Documents/Shotlist Workflows/` |
| **Video schema reference Sheet** (the parallel architecture, populated with dummy script) | `https://docs.google.com/spreadsheets/d/1dVY9X4D0jGouASUgHgsdE3FXL0Id3m2DFOJDTPAxpIw/edit` |
| **Video pipeline live show example** (Pharaoh Ep 1) | Sheet ID `1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE` |
| **Sibling scripts to study** | `auth.py`, `storyboard_build.py`, `refs_audit.py`, `fal_vidgen.py`, `flora_run.py` |
| **Sibling slash commands to study** | `/Users/raymuschang/Documents/Shotlist Workflows/.claude/commands/storyboard-build.md`, `set.md`, `vidgen.md` |

Open the schema reference sheet first — it's the fastest way to absorb the parallel video architecture before designing the post equivalent.

---

## Authentication / dependencies (same as video pipeline)

- `auth.py` handles Drive + Sheets via OAuth (`token.json` valid; do not re-run flow)
- `.env` carries: `FAL_KEY`, `REVE_API_KEY`, `FLORAFAUNA_API_KEY` (FLORA likely not needed for posts; we're image-only, no video)
- Higgsfield via connected MCP (used for gpt-image-2, nano-banana-pro)
- Provider routing rule (from user's MEMORY): characters → gpt-image-2 (fal.ai); locations → Reve direct API; typography/templates/palettes → propose nano-banana-pro (cheaper, fine for design ref)

---

## What NOT to do

- **Don't pre-populate B3 (Campaign theme) or B4 (Setting global)** in `post_build.py`. They are per-show optional — same rule as video pipeline (B3/B4 of Video Prompts). Filling them by default causes context bleed across panels.
- **Don't fold all 3 new bibles into a single "DESIGN_SYSTEM" tab.** Keep them as separate bibles so the auto-detect logic stays clean and per-bible match rules don't collide.
- **Don't reuse the video pipeline's `Storyboard Prompts` tab name** for the carousel rollup. Use `Post Prompts` so the auto-detection of "shotlist tab vs storyboard tab" logic doesn't get confused if a Sheet ever holds both.
- **Don't ship without the `--confirm` gate.** It was the single highest-leverage guardrail added on the video side after ref-bleed cost ~$3-5 in wasted gens. Bake it in from day 1 on the post side.

---

## Success criteria

When done, Raymus should be able to type:

```
/post-build <sheet-id>
# → 3 tabs scaffolded, 3 new bibles created, anyone-with-link reader on Drive

/post-gen carousel-001 iter 1
# → 5 panels generated, refs auto-detected, --confirm prints them, [y/N] gate fires,
#   iter 1 URLs written to AA col, composite written to Post Prompts col H

/post-compose carousel-001
# → review grid PNG written to Post Prompts col J
```

…and the cost-per-carousel should be **<$1 in platform credits** (vs ~$2-3/set on the video side; statics + carousels are cheaper because no Seedance video gen).
