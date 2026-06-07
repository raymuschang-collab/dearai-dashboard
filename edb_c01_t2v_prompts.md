# EDB Concept 01 — Detailed Text-to-Video Prompts (Match-Cut Sets)

Three Seedance-2-ready prompts for the emotional match-cut sets that link each engineer to their device setup. Each one is a 5-shot atomized cut (15-17s) that lands the chip-in-hand → chip-in-device → end-user-callback emotional pivot — the structural backbone of "Every chip has a story."

**Global format directives** (prepend to every prompt before firing):

```
Documentary editorial photography aesthetic. Shot on Arri Alexa 35, anamorphic 1.55x lenses, Kodak Vision3 250D color science. Natural skin texture with visible pores and small natural imperfections, no airbrushing, no game-engine rendering, no movie-poster polish. Subtle 35mm film grain. Muted, desaturated palette. Cinéma vérité framing — handheld is fine where noted. 16:9 horizontal cinematic format. No music. Diegetic sound only. Match-cuts are the structural lens — every "MATCH CUT" beat must perfectly align the on-screen object's silhouette, scale, and screen position across the cut so the eye flows seamlessly between the engineer's chip and the device's chip.

CALLBACK SHOTS at the end of each set must visually echo earlier setup shots in framing/lighting — the callback is the emotional payoff, the audience should recognize the face/space without dialogue cueing it.
```

---

## Prompt 1 — SET 4 · E1 + PHONE MATCH-CUT (16-20)

**Total runtime:** 16s · 5 shots
**Engineer (E1):** SG Chinese woman, late 20s, hair pulled back into a neat low ponytail, no makeup, calm intelligent expression. Wears a clean white lab coat over a soft pastel-blue blouse. ESD wrist strap visible. Quiet pride in her face when she looks at her work.
**Device user callback:** SG Chinese girl, 8 years old (the daughter from Setup 01, shot 2), shoulder-length hair, soft natural expression. Wears a casual t-shirt.
**Location ladder:** ASMR-quiet IC test bench → callback to a domestic interior (the family living room from Setup 01)

```
SHOT 16 (3s) — CU, static, eye-level. SG Chinese woman late 20s engineer, white lab coat, at her IC test bench in a clean test room. Lighting: even diffused fluorescent overhead, 5500K, soft fill from a desk LED at camera-left providing warm 3200K accent on her face — gives her a subtle warmth against the otherwise cool sterile environment. Background slightly blurred — silver-grey test equipment racks, dim status LEDs. Her face in focus, focused half-smile, faint pride.
Dialogue (English, light Singapore accent, soft and quiet): "Mine starts in this room."
Microexpression: faint pride; the half-smile holds through the line.

SHOT 17 (3s) — Insert, static, top-down 45° angle. Her hand (clean white nitrile glove) reaches into a black anti-static IC tray. The tray holds rows of identical small power-management ICs (PMICs), each ~5mm square in a QFN package. She picks ONE chip up between thumb and forefinger. Lighting: focused warm desk LED illuminates the tray, gold-plated contact pads on the chip flash as it lifts — single specular highlight catches the camera. Faint reflection in the polished bench surface. SFX: very soft metal-on-tray ting as the chip clears the tray rim.

SHOT 18 (3s) — CU, static, eye-level. Same engineer's gloved hand now holds the chip up to the desk lamp at near-camera distance, palm flat. The chip occupies the center of frame, perfectly readable — small black QFN with gold pad ring. Soft warm key light from camera-right makes the gold pads catch fire. Behind the chip: her face, slightly out of focus, watching it. Quiet room tone — server fan hum, distant, sub-30dB.

SHOT 19 (4s) — Insert, MATCH CUT, slow dolly-back 1.2m over duration. The frame opens locked on the SAME chip in the SAME palm position from shot 18 — but as the dolly retreats, the lighting shifts from warm desk-lamp to cool 6500K phone-screen blue. The hand is no longer the engineer's gloved hand; it's a different hand (the daughter's mum) holding a smartphone. The chip's black silhouette in shot 18 perfectly aligns with the smartphone's black bezel as the cut lands — that's the match. As the dolly pulls back, the phone's wakeup lock-screen illuminates: time reads 7:42 AM, wallpaper is a family photo. SFX: a single soft "wake-tone" chime exactly on the cut frame.

SHOT 20 (3s) — CU, static, eye-level. CALLBACK. SG Chinese girl, 8 years old, scrolling the same phone in soft natural daylight from a window camera-left (warm 4500K morning light). Background: a clean modern Singapore HDB living room, slightly soft focus. Her thumb glides over the screen — content, easy delight, faint smile. Her eyes track the screen. SFX: soft phone-scroll haptic click; very faint domestic ambience (kitchen distant, no dialogue).
```

**Why this works:** Shot 18→19 is the load-bearing match cut — chip-in-palm to chip-behind-phone-screen. The lighting flip (warm engineer-bench to cool phone-screen-glow) is the visual cue that we've teleported, but the chip's silhouette holds. Shot 20 closes the emotional loop without a single explainer line.

---

## Prompt 2 — SET 6 · E2 + PACEMAKER MATCH-CUT (26-30)

**Total runtime:** 17s · 5 shots
**Engineer (E2):** SG Indian man, mid-30s, neat short black hair, slight stubble, glasses, focused composed presence. Wears a clean white lab coat over a charcoal grey button-down. ESD wrist strap. Works in a wafer/failure analysis context — quiet authority.
**Device user callback:** SG Chinese grandfather, late 70s (from Setup 02, shot 5), thinning silver hair, weathered hands, wearing a pale blue pajama-style shirt, lying back in a hospital bed or recliner in soft daylight.
**Location ladder:** Wafer inspection bench → callback to grandfather's bedside → engineer at control panel → wide of failure analysis lab

```
SHOT 26 (4s) — Insert, static, top-down 30° angle. CU on a 300mm silicon wafer held flat on a black inspection chuck. The wafer's mirror-polished surface is silver, with the regular grid of die rectangles tessellating across it — hundreds of tiny dies visible, each catching a faint rainbow diffraction. Lighting: a single ring-light (cool 5500K) circles the wafer evenly, with no harsh hot spot — preserves the wafer's mirror character. The wafer's edge has a precision-cut notch at six o'clock. Background out of focus, quiet equipment shapes. SFX: very low equipment hum, sub-40dB.

SHOT 27 (4s) — Insert, MATCH CUT, slow dolly-back 1.5m over duration. Locked on the same silver mirror surface from shot 26 — but as the dolly retreats, the silver disc is revealed to be the polished titanium case of a pacemaker, NOT a wafer. The match holds because the wafer's silver-mirror finish in shot 26 perfectly mirrors the pacemaker case's titanium finish at the cut frame — same circular silhouette, same mirror sheen, same scale at the cut. As the dolly pulls back further, we see the pacemaker is now in a chest cavity — soft natural skin tones surround it (the grandfather's chest from shot 5). Lighting flips from cool ring-light to warm 3200K bedside lamp glow + faint window daylight. SFX: a soft electronic pacemaker beep falls EXACTLY on the cut frame, then continues in steady rhythm.

SHOT 28 (3s) — CU, static, eye-level. CALLBACK. SG Chinese grandfather's weathered hand, palm down, resting on his own chest where the pacemaker sits beneath the skin. His pajama shirt, slight rise-fall of breath. Lighting: soft warm window daylight from camera-right, the hand half-lit. He's settled — face out of frame but the breath rhythm is calm. SFX: pacemaker beep continues at the same rhythm; faint birdcall outside.

SHOT 29 (3s) — MS, static, eye-level. Engineer (E2) at a wafer-inspection control panel — a high-end industrial workstation with three monitors showing wafer maps + a tactile control surface with rotary encoders and physical buttons. He reaches forward and turns one rotary encoder a quarter-turn — small, precise, deliberate adjustment. Lighting: the monitor glow (cool blue-cyan) lights the left side of his face; a warm desk LED provides counter-fill on the right. He doesn't look at the camera. Faint pride in his expression. SFX: a single soft mechanical click as the encoder detents.

SHOT 30 (4s) — WS, static, slight low angle. Failure analysis lab interior. High-res scanning electron microscopes anchor the foreground (left and right), with their tall white-and-grey housings reaching ceiling height. In the middle ground, a row of inspection screens shows wafer cross-sections at extreme magnification — colored false-tone images of layers and defects. The lab is otherwise empty of people. Lighting: balanced cool 4500K overhead with cyan accents from the SEM screens — the room reads as deliberate and clinical. SFX: continuous quiet room tone; soft fan hum from the SEMs.
```

**Why this works:** Shot 26→27 is the wafer-to-pacemaker match — both circular silver mirrors at exact same scale at the cut frame. The pacemaker beep landing on the cut is the audio match that locks it. Shot 28's grandfather hand is the callback that says "this chip exists for him." Shots 29-30 then return us to the engineer's world to ground the feature.

---

## Prompt 3 — SET 9 · E4 + HEARING AID MATCH-CUT (41-45)

**Total runtime:** 18s · 5 shots
**Engineer (E4):** SG Malay-Chinese man, late 20s, short neat hair, glasses, intense focused expression — the algorithm-side engineer (defect prediction / yield AI). Wears a dark hoodie unzipped over a casual tee — this is an algorithm role, not a cleanroom role, so no lab coat. Works at a defect-prediction monitor station.
**Device user callbacks:**
- Toddler "Aiden": SG Chinese boy, 18 months old, soft round face, wearing a small behind-the-ear hearing aid, casual toddler clothing.
- Mum: SG Chinese woman, early 30s, soft kind face, casual home clothes.
**Location ladder:** Defect-prediction monitor (algorithm room, dark) → match cut to toddler's hearing aid → callbacks to family domestic scene

```
SHOT 41 (4s) — Insert, static, monitor-CU. Tight on a high-res monitor showing a defect prediction visualization: a circular wafer-shaped heatmap, base color deep navy, predicted failure points pulsing in saturated red — one specific red dot, slightly off-center, pulses at a steady 1.2Hz rhythm, brighter with each pulse. The heatmap UI has thin cyan grid overlays and a "PREDICTION CONFIDENCE: 0.94" readout in small mono text. Lighting: the monitor IS the only light source in frame; the room around it is dark. Reflection of the heatmap in the engineer's glasses just barely visible at frame edge. SFX: soft software chime each time the red dot pulses brighter.

SHOT 42 (4s) — Insert, static, slow zoom-in 0.4x over duration. Same monitor, but now the camera pushes IN on the pulsing red dot. As we zoom, the red dot doesn't just enlarge — it morphs. The dot's shape gradually deforms from a circle into a curved organic silhouette that suggests the pinna of a tiny ear — the curl of the helix, the lobule. The morph is smooth, NOT cutty — a single 4-second transformation. By the end, the shape has reshaped fully into an ear-suggestive graphic but is still rendered in the heatmap's red-on-navy palette. SFX: soft synthesized morph tone — pitch slowly bending upward as the shape transforms.

SHOT 43 (4s) — Insert, MATCH CUT, slow dolly-back 1.8m over duration. The frame opens locked on the same red ear-shape from shot 42's final frame — but as the dolly retreats, the red ear-graphic resolves into a real toddler's ear, with a small flesh-tone behind-the-ear hearing aid clipped onto it. The match holds because the ear shape at the end of shot 42 perfectly aligns silhouette+scale with the real ear at the cut frame — and the lighting flips from monitor-glow red to warm soft household daylight at the same instant. As the dolly pulls back, we see the toddler's profile — round cheek, soft hair, head turning. Lighting: warm 3500K window light from camera-left, soft fill from a white wall. SFX on cut: ambient room tone + an off-camera mum's voice softly: "Aiden?" — Singapore-accented, gentle, tender.

SHOT 44 (3s) — CU, static, eye-level. CALLBACK. Toddler "Aiden" — face turning from profile (end of shot 43) to camera-front (look toward off-screen mum). Recognition dawns in his eyes — the small expression shift is the entire shot: pupil dilation, brows lifting half a millimeter, mouth softening into the start of a smile. Lighting: same warm window daylight from shot 43. SFX: very faint domestic room tone, no dialogue.

SHOT 45 (3s) — WS, static, eye-level, neutral domestic interior. CALLBACK. SG Chinese mum (early 30s) on the left side of frame, kneeling on the floor at toddler-height, both arms reaching toward the toddler. Aiden is on the right side of frame, taking his first uncertain step forward toward her, hands raised. Lighting: same warm 3500K window daylight, soft and even, household ambience — slightly desaturated to keep the documentary feel. Both their faces are partially visible — both smiling, mum's eyes glistening. SFX: ambient room tone, a single soft breath; the moment lands without dialogue.
```

**Why this works:** This is the longest and emotionally heaviest set — three layered transformations (algorithmic dot → ear-shape → actual hearing aid) culminating in a wordless mother-child reunion. The audio match (the off-screen "Aiden?" cue across shot 43) is what makes the visual match-cut land emotionally instead of just technically. Shot 45's "tears of joy" callback is left to silence and natural light to do the work — no music dictated.

---

## Firing notes

- **Format:** all three are 16:9 horizontal at 1080p, ready for the EDB pitch deck.
- **Match-cut alignment is the riskiest single thing for Seedance to nail** — chip silhouette in shot 18→19, wafer-disc silhouette in shot 26→27, ear-shape silhouette in shot 42→43. If the model misses the alignment on first generation, run a second iteration with the explicit instruction "the object's silhouette and screen position MUST be identical at the cut frame" appended.
- **Reference assets to attach** (when uploading via @ system, EDB asset library):
  - Set 4: `@SG_CHINESE_WOMAN_LATE_20S_E1`, `@PMIC_CHIP`, `@SETUP_01_PHONE`, `@DAUGHTER_8YO`, `@HDB_LIVING_ROOM`
  - Set 6: `@SG_INDIAN_MAN_30S_E2`, `@WAFER_300MM`, `@PACEMAKER`, `@GRANDFATHER_70S`, `@FAILURE_ANALYSIS_LAB`
  - Set 9: `@SG_MALAY_CHINESE_MAN_LATE_20S_E4`, `@DEFECT_HEATMAP_UI`, `@HEARING_AID`, `@TODDLER_AIDEN`, `@MUM_30S`, `@DOMESTIC_INTERIOR`
- **Callback shots** depend on whether the original setup shots (shots 1-12) have already been generated. If yes, attach those frames as `first_frame` reference for the callback to ensure visual continuity. If not, fire text-only and accept that the callback face/space will be fresh.
- **Mum's "Aiden?" line in Set 9** — Seedance 2 handles English with Singapore accent natively; no voice ref needed unless a specific mum voice is in the asset library.

## Cost estimate

3 prompts × 1 iter each at Seedance 2 1080p (15-18s each) ≈ 480-540 BytePlus credits (~US\$0.55-0.75 total). Match-cuts may need a 2nd iter to land precisely → budget 1000 credits / ~US\$1.10 to safely deliver all three.
