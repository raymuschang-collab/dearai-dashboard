---
description: Toggle prompt enhancement on/off. When OFF, your prompts are sent verbatim — no embellishment, no rewrites.
argument-hint: on | off | status
---

User invoked /enhance. Args: `$ARGUMENTS`

## What this does

Toggles whether Claude is allowed to ENHANCE prompts before firing any generation
(vidgen, storyboard, image). The state persists in a flag file so it survives
across turns and sessions.

Flag file: `/Users/raymuschang/Desktop/Shotlist Workflows/.enhance_state`
(contains the single word `on` or `off`; default = `off`).

## Parse `$ARGUMENTS`

- `on`  → write `on` to the flag file. Reply: "Prompt enhancement: ON".
- `off` → write `off` to the flag file. Reply: "Prompt enhancement: OFF — prompts sent verbatim".
- `status` or empty → read the flag file and report the current state (default `off` if missing).

Write the flag with a plain file write (no trailing prose). Then confirm the new state in one line.

## Behavior contract — Claude MUST honor the flag on every gen

### When OFF (default)
- Send the user's prompt text **VERBATIM**. Do NOT add adjectives, camera moves,
  lens/film-stock anchors, lighting descriptors, "documentary editorial" realism
  preambles, or any rewrite beyond what the user literally wrote.
- For BytePlus vidgen, use the raw/verbatim body path (e.g. `vidgen_freeform.py --raw-prompt`)
  so the script does NOT re-prepend globals / realism preambles the user didn't include.
  Reference assets (`asset://…` / Drive URLs) may still be attached — that's wiring, not
  prompt enhancement.
- Storyboard `--style`/`--locref` preambles are the user's chosen template, not enhancement —
  they still apply when the user asks for that mode. The OFF rule is about Claude inventing
  extra descriptive text.

### When ON
- Claude may enrich prompts: cinematic/style descriptors, realism anchors, assembled
  reference-identity blocks, camera language, etc.

## Separate standing rule (independent of this toggle)

Do NOT auto-upload storyboards (or other gen outputs) to Drive / write URLs back to the
sheet unless the user explicitly asks. Generate locally for review first.
