# Schema v2.2 — The Locked 16-Column Shotlist Format

## Column definitions (in order)

| # | Letter | Name | Type | In Prompt? |
|---|--------|------|------|------------|
| 1 | A | Shot # | integer | yes |
| 2 | B | Duration (s) | 3 or 4 | yes |
| 3 | C | Shot Type | enum | yes |
| 4 | D | Camera Movement | enum + free-form | yes |
| 5 | **E** | **Merge Candidate** | free-form metadata | **NO** |
| 6 | F | Shot Description | English, imperative present | yes |
| 7 | G | Dialogue/VO | source language | yes |
| 8 | H | Accent | per-row enum | yes |
| 9 | I | Microexpression | English; empty ok | yes |
| 10 | J | SFX | English, short | yes |
| 11 | K | Props/Wardrobe | metadata | NO |
| 12 | L | Brand Integration | metadata | NO |
| 13 | M | Transition | enum | NO |
| 14 | N | Beat | enum + color fill | NO |
| 15 | O | English Translation | metadata (only if G is non-English) | NO |
| 16 | **P** | **Prompt** | **auto-formula** | — |

## Shot Type enum

- **CU** — close-up (face, object)
- **MCU** — medium close-up (head and shoulders)
- **MS** — medium shot (waist up)
- **WS** — wide shot (full body, environment)
- **OTS** — over-the-shoulder
- **Insert** — tight shot of an object or screen, often no subject face
- **POV** — point-of-view shot
- Special cases allowed: `ECU` (extreme close-up), `Two-shot`, etc.

## Camera Movement enum

- **Static** — locked off
- **Dolly In / Dolly Out** — camera pushes in or pulls out
- **Pan R / Pan L** — horizontal rotation right/left
- **Tilt U / Tilt D** — vertical rotation up/down
- **Handheld** — naturalistic handheld instability
- **Handheld Push** — handheld moving forward
- **Tracking** — camera follows a moving subject
- **Rack Focus** — focus pull from foreground to background (or reverse)
- Free-form allowed for special cases: "Crane Down", "Gimbal Orbit", etc.

## Accent examples

- `Jakarta Bahasa`
- `Jakarta Bahasa with Mandarin code-switch`
- `Manila Tagalog`
- `Manila Tagalog with Chinese Hokkien code-switch`
- `Seoul Korean (formal)`
- `Seoul Korean (casual, 반말)`
- `Bangkok Thai`

Accent is per-row because a character can code-switch within a single scene. The Prompt column reads this to tell the voice model which accent to use.

## Beat enum + colors

| Beat | Hex | Meaning |
|------|-----|---------|
| HOOK | `#FCD34D` | First-3-seconds hook |
| JOLT 1 | `#93C5FD` | First jolt |
| JOLT 2 | `#93C5FD` | Second jolt |
| JOLT 3 | `#93C5FD` | Third jolt |
| JOLT 4 | `#93C5FD` | Fourth jolt |
| CLIFF | `#FCA5A5` | Final cliffhanger |
| CLIFF SETUP | `#FECACA` | Setup into cliff |
| CLIFF TAG | `#FECACA` | Tag after cliff |
| TAG | `#FECACA` | Episode tag |
| PAYOFF | `#A7F3D0` | Catharsis |
| FLASHBACK | `#DDD6FE` | Flashback sequence |
| BRIDGE | `#E5E7EB` | Connective tissue |

Only fill column N (Beat cell). Do not color other cells in the row.

## The Prompt formula

```
="No music. Dialogue in "&H{r}&" accent."&CHAR(10)
&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}
&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))
&IF(J{r}="",".", ", "&J{r}&".")
```

### Four cases handled

**Case 1 — Dialogue + Microexpression:**
```
No music. Dialogue in Jakarta Bahasa accent.
1, 3s, CU, Static, Rearview mirror close-up of Henry Wijaya's eyes, phone to ear, panic-stricken., HENRY: Mereka sudah menemukan semua rekeningnya. Semuanya. (Pupils dilating with panic, sweat beading at the temple), Muffled phone audio; honking Thamrin traffic.
```

**Case 2 — No Dialogue, Has Microexpression:**
```
No music. Dialogue in Jakarta Bahasa accent.
2, 3s, CU, Static, Rearview mirror close-up of Arif Saputra's eyes, watching Henry, unsettled., (Brow knits in unease, gaze flicking between road and mirror), Engine idle; muffled phone audio from backseat.
```

**Case 3 — Has Dialogue, No Microexpression:**
```
No music. Dialogue in Jakarta Bahasa accent.
53, 3s, Insert, Static, The Gojek app on the phone mount: Arif taps 'Go Offline.' Status changes., Tap sound; status chime.
```

**Case 4 — Neither (pure insert):**
```
No music. Dialogue in Jakarta Bahasa accent.
4, 3s, Insert, Dolly In, Gojek app on phone mount: trip active, 4.92 rating, 'Henry W.', ETA 3 min SCBD., App notification ping; GPS recalculating.
```

If SFX (J) is empty, the formula ends with `.` — sentence closes cleanly.

### Why the formula skips column E (Merge Candidate)

Merge candidate notes are for the human editor. The AI generating the clip doesn't need them — it just needs to produce a single 3–4s generation of the atomized action. The editor assembles the merges in post.

## Column widths (recommended)

```python
COL_WIDTHS = [6, 10, 10, 14, 32, 46, 40, 28, 36, 28, 30, 26, 14, 12, 36, 78]
```

- A (Shot #): 6 — just enough for 3 digits
- B (Duration): 10
- C (Shot Type): 10
- D (Camera Movement): 14
- E (Merge Candidate): 32 — enough for a one-sentence note
- F (Shot Description): 46 — widest user-editable column
- G (Dialogue): 40
- H (Accent): 28
- I (Microexpression): 36
- J (SFX): 28
- K–O (metadata): 14–30 depending on column
- P (Prompt): 78 — widest so the generated prompt reads cleanly

## Row heights

Header row: 32. Data rows: 80. Text wrap on all cells. Frozen panes at A2.

## Edge cases

- **Empty Dialogue and Empty Microexpression:** the prompt still generates cleanly; the formula's nested IFs handle it.
- **Multi-character dialogue in one row:** don't. Atomize into separate rows — one per speaker line.
- **Subtitles inline:** the formula doesn't include subtitles. If you need them displayed, that's a separate CSV column (keep outside the 16 main).
- **VO (voice-over) vs. on-screen dialogue:** both go in column G. Use `ARIF (V.O.): ...` to signal voice-over. The English Translation (O) can still show the translation.
- **Overlong Shot Description:** if a row's description hits 40+ words, you've got a compound shot — atomize.

## Column Q — Bahasa Prompt (REQUIRED in this variant)

Column Q is required in every shotlist this skill produces. Auto-translates the English Prompt (P) into Bahasa Indonesia so the SEA production team can validate intent without parsing English.

### Header and formula (locked)

| Letter | Header | Formula |
|---|---|---|
| Q | `Bahasa Prompt` | `=GOOGLETRANSLATE(P{r},"en","id")` |

Both the header and the locale code are locked. This skill is Bahasa-only. For other locales (Tagalog, Korean, Thai, Vietnamese, Chinese, Japanese), use the generic `microdrama-shotlist` skill which has the multi-locale table.

### Properties

- **One-way data flow.** Q reads from P. Nothing reads from Q. Adding/removing it never affects upstream — but in this variant it should never be removed.
- **Live formula, never typed text.** Same rule as column P — keep it generated so it stays in sync when feeder columns change.
- **Schema is still v2.2.** Q is treated as a required addendum in this variant; the locked 16-column core (A–P) is unchanged.
- **The Prompt formula does NOT change.** P still produces English; the API call still goes out in English. Q exists only for the human team's comprehension.

### V1 quality expectations

GOOGLETRANSLATE is a comprehension aid, not a deliverable. Expect:

- ~80–90% of rows read cleanly in Indonesian
- ~10–20% have awkward camera-term anglicisms (`Insert` → `Sisipkan`, `Stick figure` → `figur tongkat`, `Dolly In` → `Dolly Masuk`)
- The Bahasa dialogue in column G passes through untranslated (correct behavior)

If a row reads badly enough that the team flags it, the workflow is: **leave the formula intact**, paste a manual override only into the rows that need it. Don't disable the formula globally — most rows are fine and a manual table drifts as the shotlist evolves.
