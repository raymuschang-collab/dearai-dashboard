# Storyboard Prompts + Video Prompts Tabs (v2.2 schema addendum)

Every episode Sheet in the v2.2 schema has THREE tabs:

1. **Tab 1 — Shotlist** (e.g., `Ep 1 - Ponsel Itu`) — the 16-column atomized shotlist with the Prompt formula in column P. **Source of truth.**
2. **Tab 2 — Storyboard Prompts** — bunches every 5 consecutive shots into ONE storyboard prompt for image generation (Nanobanana 2 / similar). One row per *set*.
3. **Tab 3 — Video Prompts** — one row per *shot*, with a per-shot video prompt for video gen (Seedance 2 / similar). Adds video-specific preamble.

Tabs 2 and 3 both INDIRECT into Tab 1's column P. Tab 1 is the single source of truth; the other two are derived workspaces with different preambles for different generators.

## Why two derived tabs instead of one

- **Storyboard image gen** (e.g., Nanobanana 2) takes a single composite prompt and produces ONE image. Bunching 5 shots per request gives the director a 5-panel storyboard for fast coverage validation. Preamble: "stick figure pencil storyboard" + "create a 5 panel storyboard".
- **Video gen** (e.g., Seedance 2) takes one prompt at a time and produces ONE video clip per shot. The "5-panel" and "stick figure" preambles are useless or actively harmful here. Preamble: "Shot with arri 35" only.

Same per-shot prompt (Tab 1 P) → two different wrappings for two different APIs. No duplication, clean separation.

## Why bunch shots into 5-panel storyboards

- Atomized shots are great for video generation (Seedance 2 takes one shot at a time).
- For storyboards, the human director benefits from seeing 5 sequential panels at once — establishes flow, character continuity, and visual rhythm.
- ChatGPT 2's image gen and Nanobanana 2 both produce strong 5-panel composite images when given a single prompt that lists 5 shots in order.
- The editor uses the storyboard to validate the planned coverage before greenlighting per-shot video generation (which is more expensive).

## Tab structure (9 columns)

| Col | Header | Content |
|---|---|---|
| A | Set # | 1, 2, 3... 14 (14 sets for a 70-shot episode); formula `=ROW()-1` |
| B | Shot Range | "1-5", "6-10", "11-15"...; formula `=((ROW()-2)*5+1)&"-"&((ROW()-2)*5+5)` |
| C | Storyboard Prompt | English. Auto-formula. Bunches the global preamble + 5 per-shot prompts into one cell. |
| D | Bahasa Prompt | Auto-formula. `=GOOGLETRANSLATE(C{r},"en","id")` — Indonesian version for SEA team comprehension. |
| E | Drive Folder | Link to the per-set Drive subfolder (e.g., `/Show/Ep N/storyboards/set-01/`) |
| F | Status | "Pending" / "Generating" / "Done" / "Failed" — auto-updated by the generator |
| G | Iter 1 URL | Link to the first generated 5-panel storyboard image (variation A) |
| H | Iter 2 URL | Link to the second generated 5-panel storyboard image (variation B) |
| I | Error | Filled only when Status = "Failed". Specific error message for triage. |

**Why 2 iterations per set:** the downstream video-prompter benefits from variety. Same prompt, different fal.ai seed, two different sketch interpretations of the same beats. The director picks one (or merges takes from both) before video gen.

**Why the Bahasa column:** the SEA production team works in Indonesian. The English Prompt feeds the API, but the team needs the Bahasa version to validate intent, catch translation issues, and brief contractors. `GOOGLETRANSLATE(...,"en","id")` is good enough for V1 — it's a comprehension aid, not a deliverable. Manual polish only if a specific row reads weirdly.

## The Storyboard Prompt formula (column C)

This formula lives in row 2+ of the Storyboard Prompts tab. For row N, it pulls shotlist rows `(N-2)*5+2` through `(N-2)*5+6` (covering shots `(N-1)*5+1` through `N*5`).

```
="Shot with arri 35."&CHAR(10)
&"No Music."&CHAR(10)
&"Stick figure pencil storyboard with foreground, midground and background depth."&CHAR(10)
&"Create a 5 panel storyboard based on the following shots. Ensure each shot is labelled by number, with a label of the camera angle/movement centred at the bottom of the panel. The storyboard should be divided by black lines. And the panels should flow sequentially:"&CHAR(10)&CHAR(10)
&TEXTJOIN(CHAR(10)&CHAR(10),TRUE,
  IF(INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+2))<>"",
     "Shot "&INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+2))&": "
            &INDIRECT("'Ep 1 - Ponsel Itu'!P"&((ROW()-2)*5+2)), ""),
  IF(INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+3))<>"",
     "Shot "&INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+3))&": "
            &INDIRECT("'Ep 1 - Ponsel Itu'!P"&((ROW()-2)*5+3)), ""),
  IF(INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+4))<>"",
     "Shot "&INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+4))&": "
            &INDIRECT("'Ep 1 - Ponsel Itu'!P"&((ROW()-2)*5+4)), ""),
  IF(INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+5))<>"",
     "Shot "&INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+5))&": "
            &INDIRECT("'Ep 1 - Ponsel Itu'!P"&((ROW()-2)*5+5)), ""),
  IF(INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+6))<>"",
     "Shot "&INDIRECT("'Ep 1 - Ponsel Itu'!A"&((ROW()-2)*5+6))&": "
            &INDIRECT("'Ep 1 - Ponsel Itu'!P"&((ROW()-2)*5+6)), "")
)
```

**Replace `'Ep 1 - Ponsel Itu'` with the actual shotlist tab name** for each episode. The single quotes are required because tab names contain spaces.

The IF wrappers handle the partial-last-set case gracefully (e.g., if an episode is 73 shots, set 15 will have only 3 shots — the last 2 IFs return empty and TEXTJOIN skips them).

## The fixed global prompt preamble (V1 — stick-figure storyboards)

V1 produces low-fidelity, fast-iteration storyboards: pencil stick figures with depth cues, no character likenesses, no location detail, no production lighting. The point is coverage validation — does the planned cut flow? — not visual reference.

Three lines come before the per-shot prompts on every storyboard set:

```
Shot with arri 35.
No Music.
Stick figure pencil storyboard with foreground, midground and background depth.
```

Notes on each line:

- **`Shot with arri 35.`** — kept even though the storyboard is a sketch. Tested: does not affect the stick-figure aesthetic. Useful continuity tag for downstream video gen.
- **`No Music.`** — kept for the same reason. Music direction is irrelevant to a static sketch but the line carries forward when the same prompt gets reused for video gen.
- **`Stick figure pencil storyboard with foreground, midground and background depth.`** — the V1 visual spec. The depth cue (foreground / midground / background) gives the editor a cleaner read of spatial composition than flat 2D stick figures.

The full preamble that gets prepended:

```
Shot with arri 35.
No Music.
Stick figure pencil storyboard with foreground, midground and background depth.
Create a 5 panel storyboard based on the following shots. Ensure each shot is labelled by number, with a label of the camera angle/movement centred at the bottom of the panel. The storyboard should be divided by black lines. And the panels should flow sequentially:
```

## V2 (future) — full-fidelity production storyboards

V2 swaps the V1 stick-figure line for a full cinematography stack pulled from a per-show "Show Spec" tab: camera body, lens, color profile, master lighting prompt, plus character bibles + location refs. V2 requires those spec assets to exist from the START of the show — they're not retrofittable mid-production. Build V2 only after V1 storyboards have been validated for the show's coverage logic.

Until V2 is scaffolded, the V1 preamble is the standard. If a project needs custom cinematography for V1 (e.g., "Shot with Cooke S4i" or "Color graded for Kodak 250D"), edit the formula in C2 of the storyboard tab and copy-fill down — but expect the result to drift from the stick-figure aesthetic.

## Drive folder convention

Each episode has a `storyboards/` subfolder, with one `set-NN/` per storyboard set:

```
[Show name]/
  Ep N/
    [shotlist Sheet]
    storyboards/
      set-01/        ← will hold the generated 5-panel image for shots 1-5
      set-02/        ← shots 6-10
      ...
      set-14/        ← shots 66-70 (or partial for last set)
```

Each set's folder URL goes in column D of the storyboard tab. The generated image (single PNG/JPG of the 5-panel composite) gets saved into the corresponding folder, and the public URL pasted into column F.

## Per-set folder count by episode length

| Episode shots | Sets | Last-set count |
|---|---|---|
| 50 | 10 | 5 |
| 60 | 12 | 5 |
| 65 | 13 | 5 |
| 70 | 14 | 5 |
| 73 | 15 | 3 (partial) |
| 80 | 16 | 5 |

Always create one subfolder per set, even if the last set is partial.

## Generation workflow

### Manual workflow (single set at a time)

1. Open the Storyboard Prompts tab in the episode Sheet
2. Pick the next "Pending" row
3. Copy the cell content from column C (the bunched prompt)
4. Paste into ChatGPT 2 / Nanobanana 2 / Higgsfield UI
5. Wait 30–60 seconds for image generation
6. Download the generated 5-panel storyboard image
7. Upload to the Drive folder in column D
8. Paste the public image URL into column F
9. Update column E from "Pending" to "Done"
10. Repeat for next set

### Automated workflow (multi-set batch)

For 1–3 sets per night automation: Claude drives ChatGPT via the Chrome MCP using the user's logged-in account. Claude reads each Pending row from the Sheet, generates via ChatGPT, saves to Drive, updates the Sheet. The user just stays logged in to Chrome + ChatGPT and Drive.

Future state (when API access is available): Python orchestrator runs nightly via cron, reads Sheet → calls API → saves to Drive → writes URL back. Cost at OpenAI's image gen tier: ~$0.04/image × 14 sets/episode = $0.56 per episode in storyboards.

## Setting up the Storyboard Prompts tab on a new episode

In production, this is fully automated by the `storyboard_build.py` script (or `/storyboard-build` slash command). The manual steps below are kept as documentation of what the automation does so anyone can replicate the layout in a fresh Sheet by hand.

When building a new episode Sheet manually:

1. Build the shotlist tab as usual (16-column v2.2 schema, name it `Ep N - [Title]`)
2. Add column Q to the shotlist tab: header `Bahasa Prompt`, formula `=GOOGLETRANSLATE(P{r},"en","id")` filled down for every row.
3. Add a second tab named `Storyboard Prompts`
4. Headers in row 1: `Set # | Shot Range | Storyboard Prompt | Bahasa Prompt | Drive Folder | Status | Iter 1 URL | Iter 2 URL | Error`
5. Row 2 column A: `=ROW()-1`
6. Row 2 column B: `=((ROW()-2)*5+1)&"-"&((ROW()-2)*5+5)`
7. Row 2 column C: the long formula above (replacing `'Ep 1 - Ponsel Itu'` with the actual shotlist tab name)
8. Row 2 column D: `=GOOGLETRANSLATE(C2,"en","id")`
9. Copy A2:D2, paste-fill down to A3:D[K+1] where K = number of sets needed (i.e., ceil(shot count / 5))
10. Pre-create Drive subfolders: `storyboards/set-01/` through `storyboards/set-K/` inside the episode's Drive folder
11. Paste the K Drive folder URLs into E2:E[K+1] (one URL per row, separated by newlines, single Cmd+V distributes them down)
12. Fill F2:F[K+1] with "Pending"
13. Leave G2:I[K+1] empty for now — the generator fills them as work completes

## Reference template Sheet

Jakarta Last Ride Ep 1 has the canonical Storyboard Prompts tab built. Use it as a template:
https://docs.google.com/spreadsheets/d/1-EPcY1YXstCfJm81MpVCpmuCdvN6O3awXWZ5H885T78/edit

---

# Tab 3 — Video Prompts (8 columns)

One row per shot. Each row is a single video gen request.

## Tab structure

| Col | Header | Content |
|---|---|---|
| A | Shot # | Global shot number, formula `=ROW()-1` |
| B | Video Prompt | Auto-formula. Adds video preamble + INDIRECTs into Tab 1 column P. |
| C | Bahasa Prompt | Auto-formula. `=GOOGLETRANSLATE(B{r},"en","id")` — Indonesian for SEA team. Hidden by default. |
| D | Drive Folder | Link to per-shot Drive subfolder (`videos/shot-NN/`) |
| E | Status | "Pending" / "Generating" / "Done" / "Failed" |
| F | Iter 1 URL | First generated MP4 |
| G | Iter 2 URL | Optional second pass — most shots only need 1 iter |
| H | Error | Filled only when Status = "Failed" |

## The Video Prompt formula (column B)

```
="Shot with arri 35."&CHAR(10)&INDIRECT("'<shotlist tab>'!P"&ROW())
```

For row N in the Video Prompts tab, this references row N in the shotlist tab — Shot 1 → row 2 in both tabs, etc.

Replace `'<shotlist tab>'` with the actual shotlist tab name (e.g., `'Ep 1 - Ponsel Itu'`). Single quotes required because tab names contain spaces.

## What it outputs per shot

```
Shot with arri 35.
No music. Dialogue in Jakarta Bahasa accent.
1, 3s, CU, Static, Rearview mirror close-up of Henry Wijaya's eyes..., HENRY: Mereka sudah menemukan semua rekeningnya. Semuanya. (Pupils dilating with panic), Muffled phone audio; honking Thamrin traffic.
```

Clean, video-gen-ready, no storyboard boilerplate.

## Drive folder convention

Parallel to `storyboards/`, each shot gets its own folder:

```
{Show folder}/
├── storyboards/
│   ├── set-01/   ← 5-panel storyboard images
│   └── ...
└── videos/        ← per-shot video clips
    ├── shot-01/
    │   ├── shot-01-iter-1.mp4
    │   └── (shot-01-iter-2.mp4 optional)
    ├── shot-02/
    └── ... (one folder per shot)
```

For an episode with 82 atomized shots, that's 82 per-shot folders. Created up front by the build script (idempotent — reuses existing).

## 1 iteration vs 2 iterations for video

Unlike storyboards (which always do 2 iterations for variety), video gen typically defaults to 1 iteration per shot:

- **Cost matters.** Video gen is ~$0.30–0.70 per 4s clip vs ~$0.04 per storyboard image. 82 shots × 2 iter = 164 generations × $0.50 = ~$82/episode. Doubling iter is meaningful at this scale.
- **Director already chose.** The selected storyboard panel (one of Iter 1 / Iter 2 from Tab 2) is the reference. Variation A vs B happened upstream.
- **Bad clips are cheaper to rerun.** If iter 1 of a specific shot looks wrong, regenerate just that one — don't pre-generate iter 2 on every shot.

The Iter 2 URL column exists for the cases where you DO want a second variation on a specific shot, but it's not the default.

## Setting up Tab 3 on a new episode

Automated by `storyboard_build.py` (or the `/storyboard-build` slash command). Manual steps for documentation:

1. Build the shotlist tab (Tab 1) and Storyboard Prompts tab (Tab 2) first
2. Add a third tab named `Video Prompts`
3. Headers in row 1: `Shot # | Video Prompt | Bahasa Prompt | Drive Folder | Status | Iter 1 URL | Iter 2 URL | Error`
4. Row 2 column A: `=ROW()-1`
5. Row 2 column B: `="Shot with arri 35."&CHAR(10)&INDIRECT("'<shotlist tab>'!P"&ROW())`
6. Row 2 column C: `=GOOGLETRANSLATE(B2,"en","id")`
7. Copy A2:C2, paste-fill down to row N+1 where N = shot count
8. Pre-create Drive subfolders: `videos/shot-01/` through `videos/shot-N/`
9. Paste the N folder URLs into D2:D[N+1]
10. Fill E2:E[N+1] with "Pending"
11. Hide column C (Bahasa) by default
12. Leave F:H empty for now — the video gen script fills them as work completes
