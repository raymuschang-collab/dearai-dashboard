# AGENTS.md — instructions for Claude Code (and other coding agents) on this repo

> **READ THIS BEFORE EDITING ANY GOOGLE SHEET.** Several columns in the
> production SOT sheets are FORMULAS, not user-entered text. If you paste a
> static string into one of those cells you silently break the living-document
> chain — globals stop propagating, translations stop updating, the dashboard
> shows stale data, and a future agent has to re-run the formula reapply
> script to fix it. Don't be that agent.

This file is read by Claude Code and other coding agents at session start.
Treat it as binding instructions for any work that touches the SOT sheets,
the dashboard, or generation pipelines.

---

## Series Sheets — Living Document Schema

The 6 episode SOT sheets follow a strict v2.2 schema. Tab order, column
order, and **which cells are formulas** are all load-bearing. The dashboard,
storyboard generator, video generator, and reference auditor all assume this
exact layout.

### Shotlist tab (per-episode)

| Col | Field | Type | Owner |
|---|---|---|---|
| A | Shot # | data | user |
| B | Duration (s) | data | user |
| C | Shot Type | data | user |
| D | Camera Movement | data | user |
| E | Merge Candidate | data | user |
| F | Shot Description | data | user |
| G | Dialogue | data | user |
| H | (reserved) | — | — |
| I | Speech Accent | data | user |
| J | Microexpression | data | user |
| K | SFX | data | user |
| L | Location (per-shot) | data | user |
| M-P | (reserved) | — | — |
| **Q** | **Prompt** | **FORMULA** | **`=IF(A{r}="","","No music. Dialogue in "&I{r}&...")`** |
| **R** | **Bahasa Prompt** | **FORMULA** | **`=IF(A{r}="","",GOOGLETRANSLATE(Q{r},"en","id"))`** |

**DO NOT paste resolved text into Q or R.** Q assembles the per-shot prompt
from cols A, B, C, D, F, G, I, J, K every time the row is read. R is the
auto-translation of Q. If you see plain text in those cells, the formulas
were overwritten — run the reapply script (see below).

### Storyboard Prompts tab (per-episode)

| Row | Content |
|---|---|
| 1-8 | Globals: Camera, Music, Drawing Style, Panel Framing, Aspect, Language, Accent, Style Anchor (col A = label, col B = value) |
| 9 | **BLANK** (separator — required, do not delete) |
| 10 | Header row |
| 11+ | Set rows (set 1 at row 11, set 2 at row 12, …) |

| Col | Field | Type | Owner |
|---|---|---|---|
| A | Set # | data | user |
| B | Shot Range | data | user |
| **C** | **Storyboard Prompt** | **FORMULA** | **assembles globals B1-B8 + 5 shots from Shotlist via INDIRECT** |
| **D** | **Bahasa Prompt** | **FORMULA** | **`=IF(A{r}="","",GOOGLETRANSLATE(C{r},"en","id"))`** |
| E | Drive Folder | data | auto-filled by repair script |
| F | Status | data | written by storyboard_generate.py |
| G | Iter 1 URL | data | written by storyboard_generate.py |
| H | Iter 2 URL | data | written by storyboard_generate.py |
| I | Error | data | written by storyboard_generate.py |
| J | Body | data | user (per-set body, used by vidgen) |
| K | Bahasa Body | data | user |
| L | Location | data | user |
| M | Video Iter 1 URL | data | written by vidgen pipeline |
| N | Video Iter 2 URL | data | written by vidgen pipeline |

**DO NOT paste resolved text into C or D.** Both reference live data — C
pulls from globals + Shotlist!Q via INDIRECT, D translates C. Overwrite =
broken propagation. Range Protection (warningOnly) is enabled; if Sheets
asks "you sure?" the answer is almost certainly NO.

---

## Recovery: if formulas got overwritten

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 -c "$(grep -A 200 '# Reapply formulas' AGENTS.md | tail -200)"
# OR re-run the inline script from the conversation that created this file
```

Better: use the `_create_blank_sot.py` formula functions — they're the
canonical source:
- `shotlist_q_formula(row)`
- `storyboard_prompt_formula()`  → SP!C
- `=GOOGLETRANSLATE(C{r},"en","id")` → SP!D

---

## Other rules

1. **Episode SOT sheets are SOT.** The Plotly Dash dashboard reads from
   these via `dash_app/bible_reader.py`. If you change a column position
   in the sheet, you must also update the column-index logic in
   `_read_storyboards_impl()`.

2. **`auth.py` raises SystemExit on bad creds.** The dashboard wraps reads
   in `try/except` to convert that to RuntimeError. Don't change auth.py
   to swallow the SystemExit — the wrappers exist for a reason.

3. **The `.byteplus_expense.json` and `.dash_jobs.json` files are local
   state.** They live in repo root but are gitignored. Don't commit them.

4. **`render-build.sh` installs Higgsfield CLI to a project-local prefix**
   (`/opt/render/project/src/.npm-global/bin/higgs`). That's the only path
   that survives Render's build → runtime container handoff. If you change
   the install location, also update `resolve_higgs_bin()` in `higgs_gen.py`
   and `storyboard_generate.py`.

5. **Sheets API has a 60/min/user read quota.** All bible reads route
   through `_cached_read()` in `bible_reader.py` (10-min TTL). Subprocess
   scripts use `sheets_retry.with_429_retry()` for self-recovery. Don't
   bypass the cache.

6. **CHARACTERS bible has multiple TARA rows** (`TARA ANJANI (TIED HAIR)`,
   `(BUN HAIR)`, `(CASUAL)`, `(LUSUH)`) and a `MANAGER` row. Auto-detect
   in vidgen does case-insensitive whole-word match against col A — don't
   collapse the TARA variants.

7. **Locations route via Reve direct, not Higgsfield.** Storyboards +
   characters + costumes + props + effects route via Higgsfield CLI.
   Confirmed working as of 2026-05-06.

---

## When in doubt

- Read `dash_app/app.py` SERIES_CONFIG for the canonical sheet IDs.
- Read `_create_blank_sot.py` for the canonical schema definitions.
- Check `bible_reader.py:_read_storyboards_impl` for what cell positions
  the dashboard reads.
- If you're about to write static text into a cell that other code reads,
  first check whether that cell is supposed to be a formula. The 4 known
  formula cells (Shotlist Q, R; Storyboard Prompts C, D) are listed above.
