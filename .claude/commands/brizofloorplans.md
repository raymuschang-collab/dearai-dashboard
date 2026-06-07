---
description: The locked BRIZO / ASTERIA vessel design bible — spherical-habitat floorplans, OCR'd spec sheets, and the per-vessel prompt vocabulary that governs how every Brizo location is generated.
argument-hint: "[optional: 'asteria' / 'brizo' / 'map' (per-ep location→vessel mapping)]"
---

User invoked /brizofloorplans. Args: `$ARGUMENTS`

> Companion to `/brizo`. That command holds the slate (eps, cast, sheet IDs, locked global style).
> THIS command holds the **physical design of the two vessels** so location prompts stay consistent.
> Both vessels are **spheres**, not elongated submarines — this is the single most important visual rule.

## Source concept sheets (James Thoo)

- **The Asteria** — `/Users/raymuschang/Desktop/Brizo (James)/hf_20260529_141431_98df24df-8c7a-4d88-8e7d-41b2a46022d0 (1).png`
- **The Brizo** — `/Users/raymuschang/Desktop/Brizo (James)/hf_20260529_141909_e1fddfc1-f482-4301-96d5-7a3e46bd04e2.png`

(Text on the sheets is partly AI-render gibberish; the spec below is the OCR'd + cleaned canonical reading.)

---

## THE ASTERIA — Rotating Spherical Deep-Sea Habitat

The **large mother vessel**. The sister/primary habitat the crew lives aboard.

**1. Entire structure (deep sea):** A single, self-contained **spherical** habitat that *floats* in the
deep sea — maintains stability through **internal rotation**, requiring no spine or tether to the seabed.
Hull = titanium alloy + ceramic composite, built for abyssal pressure.

**2. Plan view of interior:** A **ring/wheel of twenty "Living Quarter Spheres" (1 of 20) arranged radially
around a Central Hub.** Each living-quarter sphere doubles as a self-sufficient escape pod in a catastrophic
failure. The central hub holds main facilities, engineering, and docking access. Think bicycle wheel: hub +
spokes + 20 rim-mounted habitat spheres.

**3. Side view of interior:** The whole habitat **rotates to simulate artificial (spin) gravity** and reduce
psychological stress over long isolation; rotation also drives water circulation. Living quarters are
**spacious and natural** — multi-level, glass observation domes/ports, common areas, and **green spaces /
hydroponic greenery**. The sheet marks a clear "**Direction of Rotation**".

**4. Surface:** Smooth, seamless sphere. Interlocking lattice of fibers + ceramic tiles. Coated for low drag
/ laminar flow. Shell layering (outer→inner): 1. Ceramic Tile Surface → 2. Fiber Weave Layer →
3. Structural Composite Core → 4. Titanium Alloy Substrate.

### Asteria prompt vocabulary (use these words)
> Vast spherical deep-sea habitat interior; gently **curving** walls and floors following the sphere; a
> **rotating wheel of radial living-quarter pods around a central hub**; spin-gravity architecture; multi-level
> mezzanines; large **glass observation domes/ports** looking into black water; lush **hydroponic green
> spaces**, common lounges; spacious, breathable, almost utopian-but-isolated; smooth seamless titanium-ceramic
> surfaces. Wide, open, vertical volume. A subtle sense of the whole structure slowly **turning**.

Apply the locked deep-sea global style (`/brizo style`) on top — but the Asteria reads **more spacious and
less claustrophobic** than the Brizo.

---

## THE BRIZO — Deep Sea Submarine Habitat Concept

The **small single-occupant deployable sphere**. Detaches from the Asteria mother sphere.

**1. Deep sea:** Spherical hull equally distributes external pressure. **Only the air-lock / exit chamber and
the navigational mast protrude** from the otherwise perfect sphere. Built for long-term solo habitation.

**2. Interior plan view — FOUR rooms around a central corridor:**
- **Front (top): Living quarters / living area** — kitchenette, bunk, warm tan/wood tones.
- **Left: Greenhouse** — planted hydroponic bed, the green heart of the pod.
- **Right: Cockpit / navigational control panel** — pilot station, blue instrument glows (it can be flown).
- **Back (bottom): Air lock / Exit chamber** — the dive/dock hatch.
- All four connect via a short **central corridor (hallway)**. All spaces **pressurized and sealed**.

**3. Deployment — escape from Asteria:** Detaches from the **mother sphere** via a pressure-equalized hatch;
**thruster-assisted egress** for safe separation; built for autonomous deployment.

**4. Surface:** Ceramic composite over titanium alloy. **Slightly porous** surface (reduces sonar reflection +
biofouling) → texture reads pitted/barnacled, NOT mirror-smooth like the Asteria. Offset, interlocked seams.

**Specs (estimated):** Diameter **~18 m** · Internal volume **~2,400 m³** · Operating depth **10,000+ m** ·
**Crew: 1**.

### Brizo prompt vocabulary (use these words)
> Compact single-occupant spherical sub-habitat; **four small rooms strung along one short central corridor**;
> low curved ceilings hugging the sphere; cramped, intimate, lived-in; wet, damp, condensation-beaded metal;
> pitted/porous barnacled ceramic hull; the **greenhouse** bed, the **cockpit** with glowing nav instruments,
> the **kitchenette/bunk** living quarters, the **air-lock** dive hatch; everything within arm's reach;
> the pod **sways with the deep-sea current**; only the airlock and a thin navigational mast break the sphere.

Apply the locked deep-sea global style (`/brizo style`) on top — the Brizo reads **claustrophobic, wet, and
solo** vs. the Asteria's open spin-gravity grandeur.

---

## Asteria vs. Brizo — the one-line contrast for prompts

| | **ASTERIA** | **BRIZO** |
|---|---|---|
| Scale | huge mother sphere | ~18 m single pod |
| Interior | wheel of 20 radial living spheres + hub | 4 rooms on one corridor |
| Gravity | spin-gravity, rotating | none / handheld float feel |
| Feel | spacious, curved, utopian-isolated | cramped, wet, intimate, solo |
| Surface | smooth seamless ceramic | porous, pitted, barnacled |
| Greenery | large green common spaces | one greenhouse room |
| Motion cue | the whole ring slowly **turns** | the pod **sways** with current |
| Protrusions | none (clean sphere) | air-lock + navigational mast only |

When a location is ambiguous, default Brizo-interior shots to **cramped + curved + wet**, and Asteria-interior
shots to **open + curving + rotating**.

---

## Per-episode location → vessel mapping (from `/brizo` LOCATIONS)

- **The Brizo** (Hallway=central corridor, Cockpit, Docking Port=air-lock/exit chamber, Changing Room,
  Greenhouse, Kitchenette, Interior, Exterior) → **Brizo vocab**. Exterior = small barnacled sphere on the
  seabed, airlock + mast protruding.
- **The Asteria** (Interior, Exterior, **Bedroom**) → **Asteria vocab**. Bedroom = inside one Living Quarter
  Sphere (glass observation dome, spin-gravity floor). Exterior = the giant smooth rotating wheel-sphere.
- **Alien Ship Crash Site / Deep Sea Floor / Underwater** → neither vessel; open abyssal seabed, but keep both
  spheres readable in any establishing shot that frames them against the dark water.

## Action

- Default (no args): print this whole design bible.
- `/brizofloorplans asteria` → just the Asteria block + its prompt vocabulary.
- `/brizofloorplans brizo` → just the Brizo block + its prompt vocabulary.
- `/brizofloorplans map` → just the per-episode location→vessel mapping table.

When generating ANY Brizo/Asteria location ref or vidgen, pull the matching vessel vocabulary from here FIRST,
then layer the locked global style from `/brizo style`. Spheres, not tube-subs — always.
