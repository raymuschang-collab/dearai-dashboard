# Channel 8 Underwater — Technical Specs & Production Notes

Production notes locked from the underwater reskin test (Star Awards pipeline). These
constraints + directives apply to every Seedance fire on this show, and to future
reskin tests using the same workflow.

---

## 1. Hard constraints (API-level, BytePlus Seedance 2.0)

- **Max 3 video refs per content payload.** A 4th video ref returns `InvalidParameter`. Image refs and audio refs are separate from this cap.
- **15s total video-ref duration budget.** Sum of all video-ref durations must be ≤ 15s. Fast-forward (speed-ramp) source clips when you need to fit more identities — 4 chars × 4.4s busts the cap; 4 chars × 3s = 12s fits, but you still hit the 3-video cap first.
- **3-video cap workaround for a 4th character:** extract a still frame, upload as `Image` asset, attach as `reference_image`. Doesn't burn the video slot.
- **Image asset URLs must be `lh3.googleusercontent.com/d/<id>=w2048` format**, never Drive `/view` URLs (BytePlus rejects those as `UnsupportedImageFormat`).
- **Audio: mp3 or wav only.** `.m4a` returns `Unsupported audio format: mov`. Convert before upload.
- **Asset URI scheme is `asset://asset-<id>`** — bypasses face moderation. Bare asset codes or TOS URLs from `GetAsset` trigger `PrivacyInformation` rejections.

---

## 2. Quality directives (prompt-level, locked across show)

### Composition
- **Match the animatic / storyboard composition 80–100%** for a seamless conversion. The whole point of the reskin is fidelity to the locked director's frame — not the model's stochastic improv.
- **Use a location-collage IMAGE ref as the composition anchor** when you want camera angle + depth + staging to echo across shots. Cite it explicitly in the prompt's "Reference identities" block.

### Integration (★ where this pipeline shines)
The reskin is dramatically stronger on environment + actor integration than alternative pipelines we benchmarked. Locked observations:
- **SFX integration is significantly better** — underwater bubbles, pressure rumble, armor clink, kelp sway all bind to the visual content correctly; the model doesn't decouple SFX from frame action.
- **Lighting integration is significantly better** — refracting underwater light, wave caustics on faces and clothing, ambient streaming, and key/fill consistency hold up across cuts.
- **Proportion is significantly better** — characters scale correctly relative to thrones, columns, soldiers, and one another; no floating heads, no wrong-size soldiers in the background.
- **Robes, hair, water current, bubbles around the body** — characters are physically present in the medium, not composited.
- **Actor integration in MS / CU is the gold standard for this pipeline** — bodies + clothing + water + light interact realistically. Pair every MS/CU with a video ref of the character speaking/acting.

### Staging
- Footsoldiers **stand behind the principal characters and in front of the throne**, motionless at attention, helmets and spears upright, facing forward. They do NOT move and do NOT enter foreground unless the shot calls for an OTS over them.

---

## 3. Director freedom (★ the headline)

**The director has full control and creative freedom to do anything within the prompt.** Camera moves, lens choices, blocking, dialogue, gestures, color palette, SFX — all dialable per shot. This is the workflow's strongest selling point: when the animatic locks the frame, the reskin executes it faithfully, and when the director wants to deviate, the prompt accommodates.

In practice:
- Dialogue can be inaudible (SFX-only bridges) or fully lip-synced from an audio ref.
- Camera moves: static, dolly, jib, OTS, overhead, low-angle, side-on tracking — all reliably supported.
- Scenes can revisit the same physical location across shots without drift, **as long as the same location-collage image ref is reused as the composition anchor on every fire** (see §5).

---

## 4. Known compromise — wide shots with multiple acting principals

**The model cannot reliably capture actor performance in wide shots with multiple principals.** Faces are too small, identity binding degrades, and any nuanced acting (microexpressions, eye-line beats, breath work) is lost in the wide.

**Production rule used on the Star Awards video, locked here too:**
- **Wide shots should be neutral, muted, purely transitory / bridging shots** — geography establishment, group blocking, scale, mood. Not "performance" shots.
- **All acting beats live in MS and CU** with video refs locked per character. This respects the artistes' craft — their performance is captured where it can actually be seen, not in a wide where it gets washed out.
- **Cut from a wide (geography) into MS/CU (performance) and back to wide (geography)** as your default coverage pattern. It's the same grammar broadcast drama uses.

This was the locked approach for the **Star Awards video** and is the locked approach for every Channel 8 reskin going forward.

---

## 5. Locking a consistent location across revisits

**The single biggest win of this pipeline** vs. text-only or unanchored gens: you can revisit the same physical location across many shots in an episode (or across episodes) without drift.

Recipe:
1. **Build a location-collage image** in NanoBanana / Higgsfield gpt_image_2 — 4–6 panels showing the location from different angles (wide, MS-frontal, OTS, overhead). High res, anyone-with-link reader on Drive.
2. **Upload the collage as an `Image` asset on BytePlus.** Use `lh3.googleusercontent.com/d/<id>=w2048`.
3. **Attach the collage as a `reference_image` on every fire** for that location. Cite it in the "Reference identities" block as `composition + location anchor`.
4. **Result:** color palette, lighting style, column architecture, throne dressing, soldier wardrobe, bubble density, and depth-of-field characteristics all carry across shots. Editor cuts feel like they were shot the same day on the same set.

This locked the underwater palace setting across shots 1, 7, 8, and the emperor-2-subjects free-fire — same palette, same scale, same lighting language across all of them. Same recipe will work for any location we want to revisit (rooftop, alley, courtroom, etc.).

---

## 6. TL;DR — when pitching this pipeline

- ✅ Director has full creative control and freedom.
- ✅ MS / CU acting performance lands at broadcast quality (SFX, lighting, proportion all dramatically improved over baseline).
- ✅ Location consistency across shots is achievable (collage-image anchor pattern).
- ⚠️ Wide shots with multiple principals are neutral-bridging only — keep performance beats in MS/CU.
- ⚠️ Hard API caps: 3 video refs, 15s video budget, mp3/wav audio, `asset://` URIs only.

Used in production: Star Awards video. Locked for Channel 8 Underwater reskin and future reskin shows.
