# EDB Concept 02 — Detailed Text-to-Video Prompts

Three Seedance-2-ready prompts for the "wrong answer" rebuttal beats. Each one is a 15s vertical 16:9 cut that opens on a talking-head, hard-cuts to the same person working at the actual location, and lands a strikethrough text-overlay wipe to debunk the cliché.

**Global format directives** (prepend to every prompt before firing):

```
Documentary editorial photography aesthetic. Shot on Arri Alexa 35, anamorphic 1.55x lenses, Kodak Vision3 250D color science. Natural skin texture with visible pores and small natural imperfections, no airbrushing. Subtle 35mm film grain. 16:9 horizontal cinematic format. No music. Diegetic sound only — room tone, equipment hum, breath. Color grade: muted, desaturated highlights with cool shadows. Cinéma vérité framing — let the operator find the moment, no overlit "corporate sizzle".

TEXT OVERLAY TREATMENT (applies to all three — read carefully, this is NOT a lower-third):
The text is BIG. Tall vertical type that occupies ~70% of the frame's vertical height — top to near-bottom. Set in a heavy condensed sans-serif (think Druk Wide Heavy, or Söhne Breit Kraftig — wide bold uppercase). Each word stacks vertically, one word per line, letter-spacing/tracking pushed to +50 to +100. Color: bone white (#F5F2EA), no drop shadow. Text is keyed INTO the scene — sits flush against the talent's foreground, not floating above it. Treat the text like architectural typography — like the title cards in a Spike Jonze film or a Vox explainer. The talent should be partially obscured by the text or framed alongside it, never behind a "graphic safe area."

ANIMATION: text snaps in on a single frame at the cut point (no fade — instant). Holds for ~24 frames (0.8s). Then a thick red strikethrough line draws across HORIZONTALLY through the geometric center of the entire stacked text block over 12 frames (~0.4s) — crisp, fast, mechanical. Strike line is 12-16px thick, blood-red (#D91E1E), runs the full width of the text block + 5% padding either side. Strike holds for 18 frames (0.6s) showing the text struck-through. Then text+strike whip-cut out together on a single frame.

POSITION: type stack is anchored to one side of the frame — not centered. For Wrong #1 (cleanroom) the text stack is hard-LEFT, with talent framed on the right half. For Wrong #2 (wafer) the stack is hard-RIGHT, with talent on the left half. For Wrong #3 (AI room) the stack is hard-LEFT again. Asymmetric framing throughout — DON'T center the type.
```

---

## Prompt 1 — CLEANROOM REBUTTAL ("IT'S LOUD AND DIRTY")

**Shot count:** 5 atomic shots, 3s each = 15s total
**Talent:** SG Chinese woman, late 20s, hair pulled back, no makeup, intelligent calm expression. Wears white cleanroom bunny suit with hood and goggles in working scenes; wears plain dark grey crew-neck tee in talking-head.
**Location ladder:** ASMR-quiet cleanroom corridor → wafer transfer station

```
SHOT 1 (3s) — WS, static, locked off.
Cleanroom corridor, deep depth, vanishing point at a sealed airlock door 8m back. Sterile fluorescent overhead lighting, color temperature 5500K, evenly diffused — no shadows, no falloff, no hot spots. Walls are matte white epoxy panels. Polished epoxy floor reflects the lighting as soft elongated rectangles. The corridor is empty. Faint blue HEPA filter glow visible at ceiling vents. SFX: very low ambient HVAC hum, sub-50dB, no machinery clatter.

SHOT 2 (3s) — MS, eye-level, locked off, SG Chinese woman late 20s, dark grey crew-neck tee, neutral background (matte concrete dark grey wall), single soft key light from camera-left (3/4 fill), Kino Flo daylight with diffusion. She speaks directly to camera, calm conviction, slight smile.
Dialogue (English with light Singapore accent): "People think a fab is loud and dirty."
Microexpression: knowing half-smile, brows neutral.

SHOT 3 (3s) — CU, eye-level, same talking head setup. She continues, deadpan.
Dialogue: "It's the cleanest, quietest room you'll ever stand in."
TEXT OVERLAY: massive vertical type stack hard-LEFT side of frame, occupying ~70% of frame height — three stacked words, one per line:
  IT'S
  LOUD
  AND
  DIRTY
Set in heavy condensed sans-serif (Druk Wide Heavy or similar), bone-white #F5F2EA, tracking +80, all caps, NO drop shadow. The talent's MS framing shifts to the right half of frame so she's framed alongside the type, NOT behind it. Type snaps in instantly on cut frame (frame 1). Holds 24 frames. Horizontal blood-red (#D91E1E) strikethrough draws fast across the entire block over frames 25-36, 14px thick. Strike holds frames 37-54. Whip-cut the type+strike out on frame 55 (still on this shot). Talent and shot continue clean for the remaining 18 frames.
Microexpression: holds eye contact, single slow blink right as the strike draws.

SHOT 4 (3s) — MS over-the-shoulder, handheld with subtle stabilization. SAME woman, now in white cleanroom bunny suit, hood up, clear safety goggles, blue nitrile gloves. She stands at a wafer transfer station — a polished steel handling platform with a SECS-II load port. She is loading a FOUP (front-opening unified pod) onto the port with both hands, slow deliberate motion. Lighting: cleanroom fluorescent 5500K from overhead PLUS soft cyan rim light from the load-port indicator LEDs. Reflections of her goggles in the FOUP's polycarbonate window. SFX: pneumatic hiss as the FOUP seals, no other sound.

SHOT 5 (3s) — Insert, locked off, top-down 30° angle on the FOUP as it docks. Single overhead fluorescent. The pod's status LED transitions from amber to green. Her gloved fingers retreat from frame slowly. SFX: soft mechanical click as the load-port latches; the cleanroom HVAC hum returns to the foreground.
```

**Why these specs:** the cleanroom's signature is the *absence* of grit — every frame must privilege scale, emptiness, surgical lighting. The cut from shot 3→4 is the punch: she just told you it's not loud and dirty, then we show you it isn't. Goggles + bunny suit ensure she's recognizable as the same person despite the cover-up.

---

## Prompt 2 — WAFER FAB / PROCESS ENGINEER ("IT'S REPETITIVE")

**Shot count:** 5 atomic shots, 3s each = 15s total
**Talent:** SG Malay-Chinese man, mid-30s, neat dark hair, slight stubble, observant intelligent eyes. Wears yellow cleanroom suit (lithography area protocol) in working scenes; wears plain navy henley in talking-head.
**Location ladder:** Lithography bay with stepper machines → close-up at a stepper interface

```
SHOT 1 (3s) — WS, slow dolly-in 1m over duration. Lithography bay. Two ASML-style stepper machines on the right, beige industrial housings 2.5m tall. Lighting: yellow sodium-vapor safety light at 590nm wavelength (mandatory for photoresist protection — do NOT use white light). The yellow saturates everything; skin reads orange-yellow. Cool blue stepper status LEDs glow through small viewports on each machine, providing the only color contrast. Floor grating glints faintly. The bay extends 12m deep with another bank of machines further in. No people in this shot. SFX: low-frequency turbomolecular pump rumble, occasional pneumatic actuator click.

SHOT 2 (3s) — MS, eye-level, locked off, SG Malay-Chinese man mid-30s, navy henley, neutral matte concrete background, single soft key from camera-right with subtle warm fill. He speaks, slight grin building.
Dialogue (English, Singapore accent, comfortable): "Some people think it's repetitive — like a factory line."
Microexpression: mouth twitch, half-amused. He's heard this one before.

SHOT 3 (3s) — CU, same talking-head setup. Tighter framing — chin to forehead.
Dialogue: "Every wafer is a 600-step puzzle. None of it is the same."
TEXT OVERLAY: massive vertical type stack hard-RIGHT side of frame, occupying ~70% of frame height — two stacked words, one per line:
  IT'S
  REPETITIVE
Set in heavy condensed sans-serif (Druk Wide Heavy or similar), bone-white #F5F2EA, tracking +80, all caps, NO drop shadow. Talent's framing reframes to the left half of frame so he's alongside the type. Type snaps in instantly on cut frame. Horizontal blood-red strikethrough draws across the full block over frames 25-36, 14px thick. Strike holds frames 37-54. Whip-cut both out on frame 55.
Microexpression: brows lift slightly on "puzzle" — genuine engagement.

SHOT 4 (3s) — MCU, handheld, slight breathing motion. SAME man, now in yellow cleanroom suit, hood up, the suit's yellow blending into the bay's sodium light so he reads as part of the environment. He stands at a stepper machine's HMI touchscreen — a 24-inch industrial monitor showing wafer alignment overlays in cyan and magenta against black. The cyan/magenta UI is the dominant cool light source on his face, contrasting the warm sodium. His fingers tap through a process recipe screen. Reflection of the screen UI in his clear safety goggles. SFX: stepper machine cycling — a smooth servo whir as the wafer stage indexes.

SHOT 5 (3s) — Insert, locked off, slight rack focus from the touchscreen UI in the foreground (sharp) to his focused eyes behind goggles in mid-ground (rack to sharp). The screen shows a recipe step counter advancing: "STEP 247 / 612". His pupils track the counter. SFX: soft beep on each step advance; the yellow ambient holds.
```

**Why these specs:** lithography bays are the most cinematically distinctive area of a fab because of the legally-mandated yellow light. Anyone who's been in one knows it. Pairing the yellow with the cyan/magenta of process UIs gives a built-in color contrast that does the dramatic work without theatrical lighting tricks. The "600-step puzzle" line lands because shot 5 literally shows step 247.

---

## Prompt 3 — NEXT-GEN / AI ENGINEER ROOM ("THERE'S NO CAREER PATH")

**Shot count:** 5 atomic shots, 3s each = 15s total
**Talent:** SG Indian man, late 20s, neat short beard, glasses, focused intensity. Wears dark grey hoodie unzipped over a black tee in both talking-head and working scenes (no cleanroom suit — this is an AI/algorithm role, regular engineering office context).
**Location ladder:** Dark engineering room with monitor walls → close-up at a multi-monitor workstation

```
SHOT 1 (3s) — WS, static. Engineering room at 2am. Lights off except for the glow of three monitor walls — one wall is 12 monitors deep showing live wafer-yield heatmaps in red-amber-green. The room is otherwise unlit; ambient color temperature 6500K cool blue from the screens, pooling on the desks and floor. A single empty Aeron chair faces the wall. Faint glow of a coffee machine LED in the back corner. SFX: server fan hum, distant; one keyboard somewhere in the dark, slow typing.

SHOT 2 (3s) — MS, eye-level, locked off, SG Indian man late 20s, dark grey hoodie + black tee, neutral matte dark grey background. KEY LIGHTING for this talking-head is intentionally moodier than the other two: single LED panel at 4500K from camera-left, rim light from camera-right with a deep cyan gel (matching the monitor-glow vibe of his actual work). He speaks, half-smile.
Dialogue (English, Singapore accent, slightly faster cadence): "They tell you there's no career path in semiconductors."
Microexpression: eyebrows raised in mock surprise — he's about to debunk this.

SHOT 3 (3s) — CU, same setup, tighter. He looks down at the floor for a beat, then back up directly into camera.
Dialogue: "I'm 27. I write the algorithms that decide which wafers get scrapped."
TEXT OVERLAY: massive vertical type stack hard-LEFT side of frame, occupying ~70% of frame height — four stacked words, one per line:
  THERE'S
  NO
  CAREER
  PATH
Set in heavy condensed sans-serif (Druk Wide Heavy or similar), bone-white #F5F2EA, tracking +80, all caps, NO drop shadow. Talent's framing reframes to the right half of frame so he's alongside the type. The cool monitor-glow lighting on his face adds a beautiful color contrast against the bone-white type. Type snaps in instantly on cut frame. Horizontal blood-red strikethrough draws across the full block over frames 25-36, 14px thick. Strike holds frames 37-54. Whip-cut both out on frame 55.
Microexpression: small smile, shoulders relax — quiet confidence; eyes hold camera through the strike.

SHOT 4 (3s) — MS, handheld, slight push-in 0.5m. SAME man, now seated at the multi-monitor workstation from shot 1. The 12-monitor wall fills frame-right, screens showing real-time defect classification data. His face is lit entirely by the monitor wash — cool blue and amber falling across him in soft uneven planes. He's leaning forward, glasses reflecting the heatmap data. His hand on the mechanical keyboard, mid-keystroke. SFX: keyboard key clack; a wafer-map UI auto-refreshes with a soft chime.

SHOT 5 (3s) — Insert, locked off, OTS (over his shoulder), focused on the central monitor. The screen shows a Python notebook cell running — output text scrolling: "Model AUC: 0.97 — Yield uplift: +1.4%". His shoulder and hood blur in foreground. SFX: keyboard keypress, then silence. Hold on the screen text for the final beat.
```

**Why these specs:** the AI/algorithm side of semicon is the answer to the career-ceiling cliché — these are the highest-leverage IC roles, and they look NOTHING like a factory floor. Monitor-glow + dark room is the universal visual shorthand for "deep technical work" and gives us natural color drama without studio lighting. The "27 / scraps wafers" line is specific enough to feel real and punchy enough to recruit.

---

## Firing notes

- **All three** are designed for **Seedance 2 multimodal** at 1080p, 9:16 vertical or 16:9 horizontal — pick per the deck cut. For the EDB pitch deck slides, use **16:9 horizontal**.
- Each prompt is 5 atomic shots × 3s = 15s total. Seedance handles 15s in a single submission cleanly.
- **Reference assets to attach** (when uploading via @ system):
  - Cleanroom prompt: `@SG_CHINESE_WOMAN_LATE_20S` (cast ref), `@CLEANROOM_CORRIDOR` (location ref), `@FOUP_LOAD_PORT` (prop ref)
  - Wafer prompt: `@SG_MALAY_CHINESE_MAN_30S`, `@LITHO_BAY_YELLOW`, `@STEPPER_HMI`
  - AI prompt: `@SG_INDIAN_MAN_LATE_20S`, `@MONITOR_WALL_DARK`, `@HEATMAP_UI`
- If those refs don't exist yet in the EDB asset library: fire text-only first (still produces strong output because the lighting+location specs are explicit), then re-fire with refs once the cast bible is built.
- **Post-production REQUIRED for the type treatment** — this typography is too specific (heavy condensed sans-serif, exact tracking, asymmetric placement, frame-perfect snap+strikethrough timing) to ask Seedance to render. Seedance will produce mush. The right pipeline:
  1. Fire the t2v prompt **without** the text overlay block — get a clean live-action plate of the talking head + working scene cuts
  2. **Reframe the talent in-camera to one side** during the talking-head shots — leave the opposite half of the frame deliberately empty for the type to drop into. The prompt above already calls this out (talent right-side for cleanroom, left-side for wafer, right-side for AI room).
  3. Comp the type stack + strikethrough animation in **After Effects** (or Remotion if you're doing the whole deck programmatically) over the clean plate. Druk Wide Heavy is the type spec.
  4. Strike line is animated with a `linear` wipe mask, NOT a paint-on — keep it mechanical and crisp.

## Cost estimate

3 prompts × 1 iter each at Seedance 2 1080p 15s ≈ 405 BytePlus credits (≈ US\$0.40–0.60 depending on the conversion). Affordable for a sales-deck deliverable; fire all three in parallel.
