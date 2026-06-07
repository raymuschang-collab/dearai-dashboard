# HANDOFF — Shotlist Workflows pipeline

**Date**: 2026-05-02
**From**: Pharaoh Ep 1 production session
**For**: another Claude session in a different working directory
**Owner**: Raymus / dearai.com (SEA microdrama producer)

---

## TL;DR

Episode 1 of "Strike! Pharaoh King" is shipped. The video-shotlist pipeline is mature and battle-tested. There are 3 open loops on this side, and 1 active design conversation (carousel/static post schema) that hasn't been built yet. **No urgent work** — the main session can pick up cleanly anytime.

---

## What's live and stable

### Pipeline (3 tabs canonical, 5 bibles canonical)

- **Shotlist tab** (per-episode show-name tab) — atomic shot list with Tone of Voice (col H), Refs Detected — Chars (S), Refs Detected — Loc/Prop/Costume/FX (T)
- **Storyboard Prompts** — set-of-5 rollup; row = 10 + set_num
- **Video Prompts** — per-show globals (B1 camera, B2 audio REQUIRED; B3 scale, B4 setting OPTIONAL — leave blank by default)
- **Bibles**: CHARACTERS, LOCATIONS, PROPS, COSTUME, EFFECTS

### Skills (slash commands, all working)

- `/storyboard-build <sheet>` — scaffolds Storyboard Prompts + Drive folders (idempotent)
- `/storyboard-gen <sheet>` — fires fal.ai storyboard gens (idempotent, ~$0.40/episode)
- `/set <N> iter <M>` — fires Higgsfield Seedance 2.0 vidgen (default; ~135 cr/run)
- `/vidgen set <N> iter <M> --provider flora` — FLORA fallback (2 iters, 1218 cr/run, 18× pricier; use only when Higgsfield is stalling)

### Source-of-truth references

| Artifact | URL/ID |
|---|---|
| **Live Pharaoh Sheet** | `1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE` |
| **Schema reference Sheet (DUMMY)** | `1dVY9X4D0jGouASUgHgsdE3FXL0Id3m2DFOJDTPAxpIw` |
| **Pharaoh Gallery HTML** | `/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html` |
| **Working dir** | `/Users/raymuschang/Documents/Shotlist Workflows/` |

The schema reference sheet is the canonical study/clone template — open it to see the 9-tab layout populated with a tiny dummy script.

---

## Open loops on the Pharaoh side (do these when you come back)

1. **Run `refs_audit.py`** to populate shotlist S+T cols with detected bible refs per shot (auto-detect transparency).
   ```bash
   cd "/Users/raymuschang/Documents/Shotlist Workflows"
   python3 refs_audit.py
   ```

2. **Rebuild gallery with click-to-play patch live**:
   ```bash
   cd "/Users/raymuschang/Documents/Shotlist Workflows"
   python3 build_pharaoh_gallery_production_v2.py
   open "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html"
   ```

3. **Update `microdrama-shotlist` skill docs** to reflect the new Tone of Voice column position (col H) and the new Refs Detected cols (S, T). Skill file lives in `~/.claude/`.

These are all idempotent and safe to fire without confirmation.

---

## Recent design decisions (this session)

- **CHARACTERS!T = iter-1 white bg**, **CHARACTERS!U = iter-2 white bg REPRODUCTION** (cache-bypass dup, NOT a different angle). 9 of 9 char rows now populated.
- **Shotlist col H = Tone of Voice** — bracketed before dialogue when assembling final prompt: `KHENSU (gravely): "..."`.
- **Shotlist cols S+T = Refs Detected** — auto-populated by `refs_audit.py` for human review before vidgen fire.
- **`fal_vidgen.py --confirm`** — new gate that prints detected refs and waits for `[y/N]` before submission. Catches ref bleed early.
- **Click-to-play gallery** — replaced eager iframes with thumbnail + play overlay. ~10× faster initial render.
- **Video Prompts B3/B4 NOT defaults** — left blank in `/storyboard-build`; only fill per-show when context genuinely persists. Pharaoh's ISFET SPAWN (2) override is **show-specific, not pipeline-canonical**.

---

## Cost learnings (Episode 1 retro)

- **Total platform spend: ~$30-40 USD** (Higgsfield ~$10, FLORA ~$24, fal.ai ~$3-5, Reve ~$1-3)
- **~30-40% burned on iteration/errors** — main culprits:
  - ISFET SPAWN scaled at 1m initially (no human anchor) → forced (2) override system
  - No confirm gate on early vidgens → set 11 ISFET SPAWN bleed required 3 regen rounds
  - fal.ai moderation cache trap (deterministic same-payload-hash reject) → solved with iter-1↔iter-2 swap + iter-2 reproduction
  - Set 6 location drift (rooftop → pyramid base) → 3-4 regen rounds
  - Bible-system thrashing (Nano Banana 2 → Pro → GPT Image 2)
- **Guards now in place**: `--confirm`, refs_audit cols, iter-2 reproductions, FLORA auto-skip-merchant + progressive ref-drop, B3/B4 blank defaults

Episode 2 target: **<10% rework**.

---

## Active design conversation — NOT yet built

User wants a granular shotlist-equivalent for **carousels and static posts**. We agreed on the architecture but haven't written code yet. Capture below so the next session can pick up:

### Three-tab post pipeline (mirrors video architecture)

1. **Posts** (per-panel atomic list, 31 cols) — `Panel #`, `Carousel ID`, `Panel Position`, `Panel Function` (hook/proof/cta/payoff), `Format`, `Aspect Ratio`, `Composition`, `Visual Brief`, `Tone`, `Headline`, `Subhead`, `Body Copy`, `CTA`, `Type Hierarchy`, `Setting/Backdrop`, `Mood/Lighting`, `Characters`, `Costume`, `Props`, `Effects`, `Continuity Anchor`, `Swipe Trigger`, `Hook Score (1-5)`, `Refs Detected — Chars`, `Refs Detected — Loc/Prop/Cost/FX/Type`, `Prompt`, `Iter 1 URL`, `Iter 2 URL`, `Final URL`, `Notes`, `Status`

2. **Post Prompts** (carousel rollup, ~16 cols) — analogous to Storyboard Prompts. Has `Caption`, `Hashtags`, `CTA URL`, `Approved date`, `Posted date`.

3. **Post Globals** — B1 brand voice + visual system, B2 platform constraints (REQUIRED). B3 campaign theme, B4 setting global (OPTIONAL — leave blank by default).

### New bibles (post-specific, alongside existing 5)

- **TYPOGRAPHY** — H1/H2/body styles, font/weight/size/kerning. Match logic: first-word.
- **TEMPLATES** — recurring layouts ("full-bleed quote", "split-vertical 60/40", "9-grid"). Match: substring.
- **COLOR_PALETTES** — named brand palettes with hex codes. Match: first-word.

### Net new scripts to write

- `post_build.py` — analog of `storyboard_build.py`, scaffolds the 3 tabs + new bibles
- `post_generate.py` — fires panel gens (gpt-image-2 / nano-banana-2 / Reve)
- `post_compose.py` — builds review grid composite (new — no video equivalent)

### Net new slash commands to define

- `/post-build <sheet>`
- `/post-gen <carousel-N> iter <M>`
- `/post-compose <carousel-N>`

### Two open design calls flagged for the user

1. **One rolling Posts tab per brand** vs **one per campaign** — recommended rolling with namespaced IDs (`dearai-launch-001`, `pharaoh-promo-001`)
2. **Iter-2 = deliberate alt composition** vs **near-identical cache-bypass dup** — recommended hybrid: alt comp by default, collapse to near-dup only when moderation forces it

---

## Files modified today (2026-05-02)

| File | Change |
|---|---|
| `fal_vidgen.py` | Added `--confirm` flag with `[y/N]` gate before submit |
| `refs_audit.py` | NEW — sweeps shotlist tab and writes S+T cols |
| `build_pharaoh_gallery_production_v2.py` | Click-to-play patch (thumbnail + play overlay + `playVideo()` JS) |
| `.claude/commands/storyboard-build.md` | Added "Video Prompts globals — per-show, NOT defaults" section; B3/B4 left blank |
| Live Pharaoh Sheet | Inserted col H (Tone of Voice), appended cols S+T (Refs Detected); CHARACTERS T+U renamed; CHARACTERS!U2-U10 populated with 9 cache-bypass reproductions |
| NEW reference Sheet | `1dVY9X4D0jGouASUgHgsdE3FXL0Id3m2DFOJDTPAxpIw` — 9-tab schema study reference |

---

## Authentication notes

- `auth.py` handles Drive + Sheets via OAuth (`token.json` valid; do not re-run flow)
- `.env` has `FAL_KEY`, `REVE_API_KEY`, `FLORAFAUNA_API_KEY`
- Higgsfield via connected MCP — uses Higgsfield credits, no API key needed
- Current Higgsfield balance: **4,269.86 cr** on Creator plan (cycle started 2026-04-23 with 6,000 cr grant)

---

## When you come back

If continuing Pharaoh wrap-up: do the 3 open loops above (refs_audit + gallery rebuild + skill doc update). 5 minutes total.

If continuing the post-pipeline design: confirm the two open design calls (rolling vs per-campaign; iter-2 alt vs dup), then build the post-pipeline reference Sheet first as a study artifact (same pattern as the Pharaoh schema reference), then `post_build.py` second.

If new request entirely: clean slate, no blockers.
