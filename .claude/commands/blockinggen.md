---
description: Generate pencil BLOCKING MASTERS (wide establishing shots, stick-figure actors) for a microdrama's locations, written to the LOCATIONS bible. Synthesizes the blocking from the shotlist, then renders via gpt_image_2 + the location reference image.
argument-hint: --sheet <id-or-url> [--location "<name>"] [--force]
---

User invoked /blockinggen. Args: `$ARGUMENTS`

## What this does

Produces one **pencil blocking master** per location: a single wide establishing
shot (WS master) that locks the geography + actor positions for every shot staged
there. Detailed pencil ENVIRONMENT (from the location's reference image) + featureless
STICK-FIGURE actors at their blocking positions + name labels. Written to the LOCATIONS
bible's **"Blocking (pencil) URL"** column (R).

This is the location-conditioned pencil/stick engine (same as `--locref` storyboards),
specialized to a single WS master per location.

## Step 1 — synthesise the blocking prompt per location (YOU do this)

The script renders from a **"Blocking Prompt"** column (Q) in the LOCATIONS bible.
That column is synthesised by Claude, NOT auto-derived. For each location that needs a
blocking master:

1. Find the shotlist shots staged in that location (via the per-set `Location` column /
   `Shotlist!T` location detection, or by reading the shot descriptions).
2. Extract which characters are present and roughly where they stand / sit / move.
3. Write a WS-master blocking description in this shape:
   > "Wide master establishing shot of <location>. <CHARACTER> — a stick figure —
   > <position/action>; <CHARACTER2> — a stick figure — <position>. <key geography>.
   > Label the figures <NAMES>."

Write each location's blocking description into LOCATIONS col **Q (Blocking Prompt)**.
If the columns Q/R don't exist yet, add them (headers "Blocking Prompt" /
"Blocking (pencil) URL").

## Step 2 — render

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
/usr/bin/python3 blocking_generate.py --sheet "<sheet>" $ARGUMENTS
```

For each LOCATIONS row with a Blocking Prompt (Q) + an Iter 1 reference image (J) and no
Blocking URL (R), it threads the location image as `--image`, prepends the
single-WS-master pencil + stick-figure preamble, renders gpt_image_2, uploads the pencil
master to Drive, and writes the URL to col R. Idempotent — `--force` regenerates.

`--location "<name>"` restricts to one location (name substring).

## Notes

- Reference image quality matters: a clean single location still works best; a multi-angle
  collage can dilute the master. Prefer the cleanest Iter-1 location image per row.
- Default aspect 16:9, resolution 1k, model gpt_image_2 (standard).
- Where this lands in the UI: currently the LOCATIONS bible col R. Surfacing blocking in
  the Storyboards tab (replacing the Iter columns) is a separate dash_app change + redeploy.
