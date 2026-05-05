# Atomization v2.3 — Prompt Texture Rules (Layer 1)

**Status**: PROPOSED. Drop-in addition to `atomization_rules.md` in both `microdrama-shotlist/` and `microdrama-shotlist-bahasa/` skills.
**Source**: Pharaoh Ep 1 rewrite diffs — 11 sets, 9 patterns identified, 6 codifiable enough to bake into the skill.
**Scope**: Per-shot prompt texture only. **Atomization stays atomic.** This file does NOT introduce shot collapsing or merge-candidate execution — those decisions stay manual via col E.

---

## What changed (in one line)

The atomization output should now match the texture of a manually-rewritten shotlist by default — adding 6 mechanical transforms that the producer was previously layering in by hand.

---

## The 6 transforms — apply at atomization time

Each transform is a string-level rule. None of them require taste or directorial judgment.

### 1. ALL CAPS for bible-anchored character names

Every reference to a CHARACTERS-bible name in `Shot Description (F)`, `Dialogue/VO (G)`, and `Microexpression (I)` is uppercase.

| Where | OLD | NEW |
|---|---|---|
| Description | `Close-up of Tehuti, OTS of Khensu` | `Close-up of TEHUTI, OTS of KHENSU` |
| Dialogue speaker | `Tehuti: It's time.` | `TEHUTI: It's time.` |
| Microexp | `Khensu's eyes drop` | `KHENSU's eyes drop` |

**Why**: ref-detect logic does whole-word matching against CHARACTERS!A. Uppercase makes the match unambiguous and removes the "name buried in lowercase prose" failure mode. Also: Seedance reads ALL CAPS as bible-tagged entities and pulls the iter-1 ref harder.

**Rule**: at atomization, every name that exists in the show's CHARACTERS bible gets uppercased on every occurrence in F/G/I. Do not uppercase in metadata cols (K Props/Wardrobe, L Brand) — those are tags, not generation prose.

---

### 2. Triad microexpression format (col I)

Microexpression is always **3 anatomy fragments, semicolon-separated**, when the col is non-empty.

| OLD | NEW |
|---|---|
| `Jaw sets; fear gives way to fire` | `Jaw sets; eyes harden; breath gives way to fire` |
| `Eyes hollowed; mouth slack` | `Eyes hollowed; mouth slack; jaw unhinged` |
| `Brow knits in unease` | `Brow knits; eyes narrow; breath catches` |

**Anatomy triad** = pick one from each of three buckets:
- **Eyes**: pupils, gaze, blink, lid (e.g., "eyes wide", "pupils dilate", "gaze drops")
- **Face muscle**: jaw, brow, mouth, lip, cheek (e.g., "jaw clenches", "brow knits")
- **Breath/body**: breath, throat, neck cords, shoulders (e.g., "breath catches", "cords stand on neck")

**Rule**: when atomizing a face shot (CU/MCU), write microexpression as three semicolon-separated fragments — one from each anatomy bucket. If only two come naturally, add a breath/body fragment to round out.

**Skip**: if the shot has no face (WS, Insert), leave Microexpression empty.

---

### 3. Camera-as-verb with parenthetical role tag (col D)

Camera Movement is no longer just a style label. Each entry gets a parenthetical role tag describing what the camera is FOR in this specific shot.

| OLD | NEW |
|---|---|
| `Handheld` | `Handheld tracking (follow-run)` |
| `Handheld` | `Handheld low-angle (impact + vault)` |
| `Handheld` | `Handheld tracking (over-shoulder follow-sprint)` |
| `Tracking` | `Tracking (continuous, no cut)` |
| `Pan R` | `Pan R (reveal)` |
| `Tilt U` | `Tilt U (escalation)` |
| `Rack Focus` | `Rack Focus (foreground → background reveal)` |
| `Static` | `Static` (default — no parenthetical needed) |

**Common role tags:**
- `(follow-run)` — character running, camera following
- `(reveal)` — pan or tilt to reveal something off-frame
- `(escalation)` — tilt up = power rising
- `(impact)` — handheld at moment of physical hit
- `(reaction)` — push-in or rack to a face response
- `(continuous, no cut)` — sustained move bridging multiple atomic actions

**Rule**: at atomization, if Camera Movement is anything other than `Static`, append a parenthetical role tag describing the camera's job in this shot. If Static, leave bare.

---

### 4. Block-position descriptors when ≥2 characters in a single shot (col F)

When the shot has 2 or more characters in frame, the Description must explicitly state who is screen-left, who is middle, who is screen-right.

| OLD | NEW |
|---|---|
| `MCU of Tehuti, OTS of Khensu` | `MCU of TEHUTI (middle position, with SESHET visible left and KHENSU right)` |
| `Wide of Khensu, Tehuti, Seshet on the rooftop` | `Wide of KHENSU (screen-left), TEHUTI (middle), SESHET (screen-right) on the rooftop` |
| `OTS Henry watching Arif` | `OTS from HENRY's shoulder (screen-right) onto ARIF's face (screen-left)` |

**Rule**: at atomization, count characters in the shot's action. If 2+ characters are co-present, append `(screen-left)` / `(middle position)` / `(screen-right)` after each name on first mention in the Description col.

**Why**: locks screen-direction continuity across consecutive shots. Without it, vidgen flips geography between cuts (e.g., Tehuti suddenly screen-right in shot 27 when he was middle in shot 26).

**Skip**: solo character shots, environmental wides with no foregrounded humans.

---

### 5. Sequenced audio in SFX col (col J)

SFX is written as a comma-separated **temporal sequence** describing the audio timeline within the shot, not a label list.

| OLD | NEW |
|---|---|
| `Wood crack; foot impact.` | `wood crack on impact, fruit splat, vendor shouts, cloth tearing, sandals scuffing stone` |
| `Whoosh of body through air; cloth snapping.` | `body whoosh, cloth snap, sharp exhale, market din swelling on descent` |
| `Battle ambience.` | `distant battle rumble, scattered screams, wind across sand` |

**Rule**: at atomization, write SFX as a comma-separated list **in temporal order** matching the action arc within the shot. Each item is a discrete sound event. Leading/trailing periods optional.

**Why**: vidgen's audio path reads SFX in order. A list ordered by time produces a coherent audio ramp; a list of labels produces audio mush.

---

### 6. Set-scope anchor block (manual override — Storyboard Prompts col C)

**This one is NOT auto-applied during atomization.** It's a manual override at the Storyboard Prompts body level, documented here so the producer remembers the option and the format stays consistent.

When ≥4 of 5 shots in a set share the same Location AND the model has historically drifted on that setting, prepend an anchor block before the auto-generated body:

```
*** SETTING ANCHOR ***
ALL 5 SHOTS in this set take place ON A FLAT MUD-BRICK ROOFTOP above the
Peasant Bazaar. KHENSU, TEHUTI, and SESHET stand on the rooftop overlooking
the bazaar carnage below. NOT on a pyramid. NOT on the battlefield ground.
The setting is the rooftop — sun-baked mud bricks, low parapet wall, sky and
dust above the bazaar visible.

[auto-generated 5-shot body follows]
```

**Format conventions:**
- `*** SETTING ANCHOR ***` or `*** CRITICAL VISUAL GUARDRAIL ***` as the marker
- ALL CAPS the key location words
- Use NOT statements to exclude the drift target ("NOT on a pyramid")
- Include the bible-anchored character names ALL CAPS

**When to add**: only when a prior gen has drifted on setting OR refs are bleeding from neighboring scenes. Default = no anchor block. Anchor blocks are anti-pattern when over-applied (model fatigue from too many set-scope guards).

**Why this stays manual**: the decision of WHEN to add the block requires reading prior gen failures. The atomizer doesn't have that context. Document the format here so the prepend is consistent when the producer does add one.

---

## What stays manual (do NOT auto-apply at atomization)

These patterns appeared in the rewrite but require taste / context the atomizer lacks. Leave them to the producer's manual pass:

| Pattern | Why manual |
|---|---|
| **Negative guards** ("NO scorpion in BG") | Requires knowing which refs are bleeding from prior gen runs |
| **Mid-line dialogue cut directives** (`[MID-LINE CUT to ~1.5s CU LISTENER]`) | Requires feeling for where dialogue should break |
| **Oner-merge body collapse** (5 shots → 3) | Requires reading the action arc + camera capabilities + emotional pacing — pure director taste |

The Merge Candidate column (col E) flags merge OPTIONS at atomization time. The body collapse stays manual: the producer reviews flagged candidates and decides per-set whether to keep atomic or rewrite as a oner.

---

## Updated atomization checklist (replaces v2.2 checklist)

Before declaring the shotlist done:

- [ ] Every row is one action (v2.2 rule)
- [ ] No row has two characters doing two things (v2.2 rule)
- [ ] No row has a camera that zooms, pans, AND dollies in one shot (v2.2 rule)
- [ ] Dialogue exchanges are cut between speakers (v2.2 rule)
- [ ] Durations are all 3 or 4 (v2.2 rule)
- [ ] Shot count is within episode-length target range (v2.2 rule)
- [ ] **All bible-anchored character names are ALL CAPS in F/G/I** ← v2.3
- [ ] **Microexpression cells follow the 3-fragment anatomy triad** ← v2.3
- [ ] **Non-Static Camera Movement entries have a parenthetical role tag** ← v2.3
- [ ] **Multi-character shots have explicit screen-position descriptors** ← v2.3
- [ ] **SFX cells are sequenced (temporal order) not labeled** ← v2.3

---

## Where to apply this

If accepted, this content gets appended to **both** of:
- `/Users/raymuschang/.claude/skills/microdrama-shotlist/references/atomization_rules.md`
- `/Users/raymuschang/.claude/skills/microdrama-shotlist-bahasa/references/atomization_rules.md`

After insertion, the existing v2.2 "Five Rules" + "Before/after examples" + "Duration guide" sections stay intact. The v2.3 transforms slot in as a new section between "What NOT to atomize" and "Atomization checklist".

---

## Estimated impact

Based on Pharaoh Ep 1 rewrite data:
- **70% of manual rewrite work absorbed** at atomization time
- **30% remains taste-driven** (negative guards, mid-line cuts, oner merges) — kept explicitly manual
- **Zero risk of over-collapsing** — atomization stays atomic; merge decisions stay in col E flag-only
