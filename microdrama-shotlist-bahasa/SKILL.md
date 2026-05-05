---
name: microdrama-shotlist-bahasa
description: Bahasa Indonesia / Jakarta variant of the microdrama shotlist skill. Produce per-shot production shotlists for vertical microdrama set in Indonesia, on the Nanobanana 2 → Seedance 2 pipeline. v2.2 schema with required Bahasa Prompt column (Q). Jakarta-only localization (Gojek, Pertamina, Pajero Sport, Sudirman, KPK, miliar rupiah). Trigger when the show is set in Indonesia, characters speak Bahasa Indonesia, dialogue uses Jakarta Bahasa with or without Mandarin code-switch, or the user explicitly says "Bahasa", "Indonesian", "Jakarta", "Indonesia". Also trigger on shotlist, shot list, shot breakdown, storyboard, atomize, merge candidate, camera movement, shot type, beat color, prompt column, sfx, microexpression for Indonesian-set shows. For non-Indonesian shows (Manila, Seoul, Bangkok, HCMC), use the generic `microdrama-shotlist` skill instead. Do NOT trigger on "write a script", "draft a synopsis", "outline a season", "beat sheet" — those belong to the `microdrama-scriptwriter` skill.
---

# Microdrama Shotlist (Bahasa Indonesia)

Production-grade per-shot documents for vertical microdrama set in Indonesia. Takes a locked Bahasa script or synopsis as input, outputs a shotlist in the v2.2 schema with required Bahasa Prompt column, Jakarta localization locked, ready for the Nanobanana 2 → Seedance 2 pipeline.

This skill is the **Bahasa Indonesia variant** of the generic `microdrama-shotlist` skill. Use this when:

- The show is set in Indonesia (Jakarta, Bandung, Surabaya, etc.)
- Characters speak Bahasa Indonesia, with or without Mandarin code-switch
- The production team works in Indonesian and needs the Bahasa Prompt column populated
- Brand integration uses Indonesian brands (Gojek, Pertamina, Indofood, Telkomsel, Tokopedia, etc.)

Use the generic `microdrama-shotlist` skill instead for shows set in Manila, Seoul, Bangkok, Ho Chi Minh City, or other non-Indonesian markets.

This skill is shotlist-only. Script/synopsis/outline work belongs to the separate `microdrama-scriptwriter` skill. The two chain — scriptwriter upstream, shotlist downstream.

## When to use this skill

- "Turn this script into a shotlist"
- "Atomize these shots"
- "Add merge candidates to this shotlist"
- "Shotlist for Ep 3"
- "Storyboard this scene"
- "Trim this shotlist to 90 seconds of final runtime"
- "Retrofit this show to v2.2"
- "Translate this shotlist to Bahasa"
- "Fix the Prompt formula in this sheet"

If the user hasn't given you a script yet, ask for one — OR invoke the scriptwriter skill first. Don't try to write the script from this skill.

## The v2.2 schema (16 columns + required column Q)

The 16-column core is locked. Every production shotlist in this Bahasa variant uses exactly these columns in this order, **plus a required column Q (Bahasa Prompt)**. The SEA production team relies on Q for every brief and review pass — it's not optional in this variant.

| # | Column | Source | Feeds Prompt? |
|---|--------|--------|---------------|
| A | Shot # | sequential integer | yes |
| B | Duration (s) | 3 or 4 | yes |
| C | Shot Type | CU, MCU, MS, WS, OTS, Insert, POV | yes |
| D | Camera Movement | Static, Dolly In, Pan R/L, Tilt U/D, Handheld, Tracking, Rack Focus, Handheld Push, etc. | yes |
| **E** | **Merge Candidate** | **metadata note (see Merge Candidate rules)** | **NO — metadata only** |
| F | Shot Description | English, one action per row | yes |
| G | Dialogue/VO | source language (Bahasa, Tagalog, Korean, etc.) | yes |
| H | Accent | per-row (e.g., "Jakarta Bahasa", "Manila Tagalog", "Jakarta Bahasa with Mandarin code-switch") | yes |
| I | Microexpression | English; empty if no face in shot | yes |
| J | SFX | English, short — "tire screech; rain ambience" | yes |
| K | Props/Wardrobe | metadata | NO |
| L | Brand Integration | metadata — which brand appears, how | NO |
| M | Transition | Cut, Smash Cut, Fade to Black, etc. | NO |
| N | Beat | HOOK, JOLT 1-4, CLIFF, PAYOFF, FLASHBACK, BRIDGE | NO (but gets color fill) |
| O | English Translation | metadata — only if dialogue isn't in English | NO |
| **P** | **Prompt** | **auto-formula; see formula below** | — |
| **Q** | **Bahasa Prompt** | **REQUIRED — `=GOOGLETRANSLATE(P{r},"en","id")`** | — |

### Prompt formula (column P)

This formula assembles columns A–D and F–J into a single Nanobanana 2 / Seedance 2 prompt, intentionally skipping the Merge Candidate metadata column:

```
="No music. Dialogue in "&H{r}&" accent."&CHAR(10)
&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}
&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))
&IF(J{r}="",".", ", "&J{r}&".")
```

Where `{r}` is the row number. The formula handles four cases:

- Dialogue + microexpression → `..., shot desc, dialogue (microexp), sfx.`
- No dialogue, has microexpression → `..., shot desc, (microexp), sfx.`
- Has dialogue, no microexpression → `..., shot desc, dialogue, sfx.`
- Neither → `..., shot desc, sfx.`

If SFX is empty, the trailing period closes the sentence cleanly.

**Important:** the Prompt column must be a LIVE formula, not typed text. Edit any feeder column and the prompt regenerates. The human editor in the pipeline reads this column; keep it generated.

### Common failure mode — Prompt formula missing on shipped shotlists

A shotlist is NOT delivered until column P contains the formula on EVERY row. The most common production failure is a shotlist where:

- All 16 column headers exist in row 1 ✓
- Columns A–O are populated for every shot ✓
- **Column P has the header but no formula in any row ✗**

This breaks the entire downstream pipeline:
- Storyboard prompts (which INDIRECT into P) render only the preamble — no per-shot content
- Bahasa Prompt column Q (which translates P) renders empty in Indonesian
- Image generation produces useless output because the prompts are stubs

**Pre-delivery check, non-negotiable:** sample-render P2, P25, and P{last} before declaring the shotlist done. If any of them render blank, the formula was never dropped in. Fix by writing the v2.2 formula above into every data row of column P, then verify rendered output is non-empty and contains the Indonesian dialogue + English description.

If you're adding the formula via gspread / Sheets API:

```python
def prompt_formula(r):
    return (
        f'="No music. Dialogue in "&H{r}&" accent."&CHAR(10)'
        f'&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
        f'&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))'
        f'&IF(J{r}="",".", ", "&J{r}&".")'
    )

# Write to P2:P{last_row} with value_input_option="USER_ENTERED"
```

### Bahasa Prompt (column Q) — REQUIRED in this variant

Column Q is required in every shotlist this skill produces. Auto-translates the English Prompt (column P) into Bahasa Indonesia so the SEA production team can read and validate intent without parsing English.

**Header (locked):** `Bahasa Prompt`

**Formula (locked):**
```
=GOOGLETRANSLATE(P{r},"en","id")
```

Do not change the locale code — this skill is Bahasa-only. For other locales (Tagalog, Korean, Thai, Vietnamese, Chinese, Japanese), use the generic `microdrama-shotlist` skill which has the multi-locale table.

**Properties:**
- Live formula, never typed text. Edit any feeder column (A–D, F–J) → P regenerates → Q regenerates.
- Source-language Bahasa dialogue in column G passes through cleanly (Google detects it as Indonesian and leaves it alone).
- Column Q is downstream of P. It does NOT feed anything upstream. Adding or removing Q never affects the Prompt formula or the Storyboard Prompts tab.

**V1 quality expectations:** GOOGLETRANSLATE handles 80–90% of rows cleanly. The remaining 10–20% read awkwardly — usually because of camera-term anglicisms (`Insert` → `Sisipkan`, `Stick figure` → `figur tongkat`, `Dolly In` → `Dolly Masuk`). For V1, leave the formula in place and let the team polish in-line if a specific row reads badly. For V2 (locked deliverable), commission a manual translation pass.

## Atomization rules (v2.2)

Each row is ONE action, ONE subject, ONE angle. No bunching.

**Why atomize:** each row becomes one Nanobanana 2 generation. The editor picks the best 1–2 seconds from each 3–4s clip. Atomization gives the editor flexibility; bunching collapses the edit into the prompt, which is not the AI's strength.

**Rules:**

1. **One action per row.** "Henry hangs up the phone" and "Arif watches in the rearview" are two rows, not one.
2. **One subject per row.** Don't combine Character A's action with Character B's reaction in the same row. Cut them.
3. **One angle per row.** Don't describe a shot that moves from a WS to a CU in the same row. That's two shots.
4. **Dialogue cuts back-and-forth.** When two characters speak, each line gets its own row (plus potentially a listener reaction row between them). Editor-friendly coverage, not stagey two-shots.
5. **Duration window 3–4 seconds.** Never 1s or 2s (too short for Nanobanana to generate coherently). Never 5s+ (too long — editor won't use most of it). Use 3s as default, bump to 4s for slower/held moments.
6. **Total runtime math:** atomized Ep typically has 60–80 rows × 3–4s = 180–320s of generated footage. Editor cuts to ~60–90s final. This ratio is intentional.

**What NOT to atomize (keep as one shot):**

- Single-action insert shots (phone screen, sign, object close-up) — already atomic.
- A static exterior wide that establishes geography — one shot, one description.

## Merge Candidate rules (column E)

Column E is editor metadata. It suggests which atomic rows could collapse into one continuous shot with a camera move, if the human editor prefers. It does NOT feed the Prompt formula.

**Merge is appropriate ONLY when all five are true:**

1. **Same continuous space.** One room, one vehicle, one sightline. No cuts to different locations.
2. **Single camera motion.** Pan, tilt, dolly, push, pull, track, or rack focus. Not compound moves.
3. **Beat is not HOOK, JOLT, or CLIFF.** Those need hard cuts to land the impact.
4. **Not a dialogue exchange.** Two speakers stay cut for editor flexibility.
5. **Merged runtime fits 3–5 seconds.** Soft extension beyond the 4s atomic cap because camera moves need breathing room.

**Format of the merge note** (goes in column E of the LATER row):

```
Merge w/ {earlier shot #}; {camera move description ending at the current row's subject}.
```

Examples:

- `Merge w/ 11; OTS push-in as Arif reaches over the seat to pick up the phone.`
- `Merge w/ 43; handheld push through the parting curtain, landing on the Pajero Sport.`
- `Merge w/ 66; rack focus from the SMS on Henry's phone to Arif's trembling hands.`

**Typical ratio:** ~10% of shots carry merge candidates. More than 20% means you're over-suggesting. Less than 5% means you're being too timid.

**My spatial reasoning caveat** — the AI does not have embodied spatial intuition. Merges are suggested based on film grammar conventions (eyeline match, 180-degree rule, reveal pans), not on how the space actually feels to a camera operator. The human director has final say.

## Beat color legend (column N)

Apply solid fill to the Beat cell (column N) only:

| Beat | Hex | Purpose |
|------|-----|---------|
| HOOK | `#FCD34D` (amber) | First 3s hook — drop into mid-action |
| JOLT 1 / 2 / 3 / 4 | `#93C5FD` (blue) | The four jolts per episode — new threat, reveal, escalation, etc. |
| CLIFF | `#FCA5A5` (red) | Final cliffhanger |
| CLIFF SETUP / CLIFF TAG / TAG | `#FECACA` (pale red) | Leading into or tagging the cliff |
| PAYOFF | `#A7F3D0` (green) | Resolution / catharsis |
| FLASHBACK | `#DDD6FE` (purple) | Flashback sequence |
| BRIDGE | `#E5E7EB` (gray) | Connective tissue — non-beat shots |

Not every row has a beat color. Most atomized shots are unfilled — only the structural peaks get color-tagged so the editor can see the episode's rhythm at a glance.

## Shotlist workflow

### 1. Confirm you have a locked script or synopsis

If the user hands you a script, read it and play it back in 3–5 sentences so they know you tracked the plot and tone. If they only have a pitch or logline, tell them to invoke the scriptwriter skill first — this skill does not write scripts.

### 2. Break the script into atomic shots

For each scripted beat, plan the coverage. Typical ratios:

- Dialogue line: 1 speaker shot + 1 listener reaction shot (cut back if the line is long)
- Action beat: 2–4 atomic shots (subject action → object insert → reaction → environment beat, pick whichever apply)
- Reveal: 2–3 shots (setup → reveal insert → reaction)
- Cliffhanger: 3–5 shots with escalating CU push-ins

Count target: a 90s episode lands around 60–80 atomized rows.

### 3. Populate the 16 columns per shot

Follow the column definitions above. Principles:

- **Shot Description (F):** imperative present tense, one action, English. "Henry's hands stuff papers into a leather briefcase, zipper ripping shut." NOT past tense, not paragraphs.
- **Dialogue (G):** source language ONLY. No translation in this column. Prefix with character name: `ARIF: Pak! Pak, uangnya—`
- **Accent (H):** per-row; most rows share the episode default (e.g., "Jakarta Bahasa"), but switch per-row when a character code-switches or accents differ.
- **Microexpression (I):** English, 1–2 clauses, only if the shot has a visible face. Skip if the shot is an insert with no face. Example: `Jaw drops; blood drains from cheeks`.
- **SFX (J):** English, short. Multiple SFX separated by semicolons. Example: `Phone buzz; ominous bass drop`.
- **English Translation (O):** only populate if dialogue is non-English.

### 4. Flag merge candidates (column E)

After the shotlist is built, re-read it and mark merge candidates per the 5-rule gate above. Typical 7–10 merges per episode.

### 5. Color-code beats

Apply the beat color legend to column N only.

### 6. Drop in the Prompt formula

Column P formula per row (see above). Paste once, fill down.

### 7. Deliver as a Google Sheet

The XLSX → Sheet conversion path in Google Drive can be finicky with custom openpyxl output. For reliability:

**Path A — CSV upload (safest):** write the shotlist as CSV, upload via Drive `create_file` with `mimeType: text/csv`. Drive auto-converts to a native Sheet. Loses formulas and formatting, but guaranteed to convert cleanly. Formulas have to be pasted in afterward.

**Path B — Direct XLSX (richer):** openpyxl writes XLSX with formulas, fills, column widths, frozen header. Upload via `create_file` with `mimeType: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. The file stays as XLSX in Drive. User clicks "Open with → Google Sheets" to convert. If conversion fails with "Could not open file", the XLSX probably has a feature Sheets' converter doesn't like — fall back to Path A.

**Path C — Edit an existing native Sheet:** if the user has already converted an earlier version to a native Sheet, add changes directly via Chrome automation (Name Box navigation + keyboard shortcuts). The Google Sheet's auto-formula-adjustment on column insert handles reference shifts for free.

**Link format:** always use `https://drive.google.com/file/d/{id}/view` for XLSX files. Use `https://docs.google.com/spreadsheets/d/{id}/edit` only for native Google Sheets.

### 8. Build the Storyboard Prompts + Video Prompts tabs

Every episode Sheet has THREE tabs total:

- **Tab 1 — Shotlist** (built in steps 1–7 above): source of truth, v2.2 schema with column P (Prompt formula) feeding both downstream tabs.
- **Tab 2 — Storyboard Prompts**: 9 columns. Bunches every 5 atomized shots into ONE storyboard prompt for image gen. One row per set.
- **Tab 3 — Video Prompts**: 8 columns. One row per shot. Adds a video-specific preamble ("Shot with arri 35.") to the per-shot Prompt from Tab 1.

See `references/storyboard_prompts.md` for the full schemas, formulas, and per-shot Drive folder conventions.

**Pipeline summary (storyboards):**
1. Build shotlist tab (steps 1–7 above)
2. Add `Storyboard Prompts` tab with 9-col schema and per-set formulas
3. Pre-create Drive subfolders: `storyboards/set-NN/` per set
4. Run image generation (fal.ai nano-banana-2 / similar) — 2 iterations per set, 21:9 aspect, V1 stick-figure preamble
5. Upload generated images to per-set Drive folders, set sharing to anyone-with-link reader
6. Write public URLs back to Iter 1 / Iter 2 columns of the storyboard tab; Status → Done

**Pipeline summary (video):**
1. Storyboards reviewed; director picks Iter 1 or Iter 2 per set
2. Add `Video Prompts` tab with 8-col schema and per-shot formulas
3. Pre-create Drive subfolders: `videos/shot-NN/` per shot
4. Run video gen (Seedance 2 / similar) — 1 iteration per shot by default, optional iter 2 on demand
5. Upload generated MP4s to per-shot Drive folders
6. Write public URLs back to Iter 1 URL column of the Video Prompts tab; Status → Done

**V1 vs V2:**
- **V1** (current): stick-figure pencil sketches with foreground/midground/background depth cues. No character refs, no location refs, no production cinematography. Used for coverage validation only — does the cut flow?
- **V2** (parked): full-fidelity production storyboards with character bibles, lens specs, color grade, master lighting prompt. Requires a separate "Show Spec" tab populated from the start of the show.

### 9. Generate a team brief (if requested)

See the pipeline_handoff pattern in the scriptwriter skill's legacy references. The brief explains:

- Link to the Sheet (with both tabs)
- 5 shots per Nanobanana 2 storyboard prompt (atomic — fixed 5-shot grouping)
- 2 storyboard iterations per set, both saved to `storyboards/set-NN/`
- Pipeline: Shotlist → V1 storyboards (sketch coverage) → Seedance 2 (final video, one shot at a time)
- Each atomized row is ONE Seedance 2 generation at 3–4s
- Editor assembles final 60–90s from the best 1–2s of each clip

Deliver in the team's working language (Bahasa Indonesia default for this user).

## Localization — Jakarta, Indonesia (locked)

This variant is Jakarta-locked. All shows use the Jakarta pack consistently — no half-localizing (Manila streets with Jakarta brands is a dead giveaway).

**Ride-hailing:** Gojek (primary), Grab (secondary)
**Vehicles:**
- Economy: Toyota Avanza, Honda Mobilio, Daihatsu Xenia
- Executive: Toyota Fortuner, Mitsubishi Pajero Sport (signature elite convoy)
- Luxury: Lexus LX, BMW 5-Series
- Motorbikes: Honda Beat (masses), Vespa (hipster middle class)

**Fuel:** Pertamina (state-owned), Shell, BP
**News:** Kompas, Tempo, Detik, Jakarta Post (English), CNN Indonesia
**Anti-corruption / investigation:** KPK (Komisi Pemberantasan Korupsi), Polri
**Streets & areas:**
- Financial / corporate: Sudirman, SCBD (Sudirman Central Business District), Mega Kuningan, Thamrin
- Old town: Kota Tua, Glodok (Chinatown)
- Middle-class residential: Grogol, Tanjung Duren, Pluit
- Kampung: Tebet, Menteng Dalam

**Religious / cultural props:**
- Muslim: tasbih (prayer beads), doa sticker on dashboard, prayer rug
- Chinese-Indonesian: Buddhist altar with oranges, joss sticks
- Christian-Indonesian: rosary, cross pendant

**Currency:** Rupiah (Rp); amounts over a billion use "miliar" (Rp 70 miliar = 70 billion rupiah)
**Brands for product placement:** Indofood, Telkomsel, Tokopedia, GoFood, Bank BCA, Bank Mandiri
**Dialect:**
- Default: Jakarta Bahasa (casual, loose, Betawi-inflected)
- Chinese-Indonesian characters often code-switch with Mandarin under stress
- Elite / corporate: more formal Bahasa, English loanwords
- Kampung: heavier Betawi slang

**Common Jakarta plausibility red flags:**
- Using "taxi" generically when Gojek / GrabCar would be the actual choice
- Showing Christmas decorations in a Muslim-majority neighborhood (or vice versa, with religious assumptions)
- Wrong police hierarchy (KPK vs. Polri confusion — KPK does anti-corruption only)
- Currency in million rupiah for a "huge" amount (usually too small — should be miliar for billion)
- Non-Indonesian brands sneaking in (Petron, Grab+Beep, Kakao T)

See `references/localization_packs.md` for the full Jakarta pack.

## Flags and checks (pre-delivery)

### Shotlist tab (tab 1)

- [ ] All 16 columns + column Q (Bahasa Prompt) populated correctly
- [ ] Prompt column (P) contains live formula, not typed text
- [ ] **Column Q (Bahasa Prompt) has the locked formula** `=GOOGLETRANSLATE(P{r},"en","id")` — REQUIRED in this variant
- [ ] Q renders Indonesian text on every row (sample-check 5 rows)
- [ ] Every row has Shot #, Duration, Shot Type, Camera Movement, Shot Description
- [ ] Dialogue rows have Accent populated (Jakarta Bahasa default; flag if a non-Indonesian accent appears)
- [ ] Duration is 3 or 4 only (no 1s, 2s, 5s+)
- [ ] At least 60 rows for a 90s episode; rejection-worthy below 50
- [ ] Merge Candidate column populated on 5–15% of rows, not more
- [ ] Beat colors applied on structural peaks (HOOK, JOLT 1-4, CLIFF at minimum)
- [ ] Character name consistency (Arif vs. Arif Saputra vs. Sapu)
- [ ] **Jakarta localization locked** — no Manila / Seoul / Bangkok / HCMC props sneaking in
- [ ] Currency in rupiah, amounts use "miliar" for billions
- [ ] Brand integrations are Indonesian (Gojek, Pertamina, Indofood, Telkomsel, Tokopedia, etc.) — flag any non-Indonesian brand

### Storyboard Prompts tab (tab 2)

- [ ] 9 columns: Set #, Shot Range, Storyboard Prompt, Bahasa Prompt, Drive Folder, Status, Iter 1 URL, Iter 2 URL, Error
- [ ] Set count = ceil(shot count / 5); last set may be partial
- [ ] All Drive folders pre-created and linked in column E
- [ ] Storyboard Prompt formula references the actual shotlist tab name (single quotes around tab names with spaces)
- [ ] V1 preamble in column C: `Shot with arri 35.` / `No Music.` / `Stick figure pencil storyboard with foreground, midground and background depth.` / `Create a 5 panel storyboard...`
- [ ] Bahasa Prompt column D is hidden by default
- [ ] If generation has run: Status = Done on completed rows, URLs in G/H, no orphaned "Generating" status

### Video Prompts tab (tab 3)

- [ ] 8 columns: Shot #, Video Prompt, Bahasa Prompt, Drive Folder, Status, Iter 1 URL, Iter 2 URL, Error
- [ ] Row count = total shot count (one row per shot)
- [ ] All per-shot Drive folders pre-created (`videos/shot-NN/`) and linked in column D
- [ ] Video Prompt formula in column B: `="Shot with arri 35."&CHAR(10)&INDIRECT("'<shotlist tab>'!P"&ROW())`
- [ ] No "stick figure" or "5 panel" boilerplate in column B render — that's storyboard-only
- [ ] Bahasa Prompt column C is hidden by default (REQUIRED in this Bahasa variant)
- [ ] If generation has run: Status = Done, MP4 URL in F (Iter 1)

## References

- `references/schema_v22.md` — The locked 16-column schema with worked examples, formula breakdown, and edge cases
- `references/atomization_rules.md` — Full atomization rulebook with annotated before/after examples (compound shot → atomic shots)
- `references/merge_candidates.md` — The 5-rule gate for merge candidates, with examples of what to merge and what to keep cut
- `references/localization_packs.md` — Jakarta-only localization pack (brands, props, dialects, streets, plausibility red flags)
- `references/build_templates.md` — openpyxl Python template for generating v2.2 XLSX files, with the proven formula, fills, and column widths
- `references/storyboard_prompts.md` — The Storyboard Prompts tab (second tab in every episode Sheet, 9-column schema) that bunches every 5 atomized shots into one prompt for Nanobanana 2 image generation. Includes the V1 stick-figure preamble, Bahasa column convention, the auto-formula, Drive folder convention, the 2-iterations-per-set generation workflow, and the V1/V2 split.
