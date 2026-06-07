---
description: Pull the canonical BRIZO show bible (4-episode underwater sci-fi/horror, James Thoo collab) and render the current state of the slate — IDs, shots, storyboards, vidgen status, cast, locations, and the locked global style.
argument-hint: "[optional: ep number, or 'status' / 'style' / 'vidgen <ep> <set>']"
---

User invoked /brizo. Args: `$ARGUMENTS`

## What BRIZO is

**BRIZO** — a 4-episode vertical microdrama, **underwater sci-fi / horror**. The crew lives aboard a
submerged research/mining vessel, **The Brizo**, that sways with the deep-sea current; a sister vessel
**The Asteria**; an **alien entity** threat; an alien ship crash site on the deep sea floor.
PocketShow Brand slate **slot #2 — collab directed by James Thoo, with Indo team support**
(PONDOK-INDAH runs under this slot for the Indo team).

Drive project folder: **`Brizo/`** = `1n-GZOfepmDNEAJGx5jxLcOKjuJNh1hTY`
(contains the 4 ep sheets, `ep_01..04_script.txt`, `script.pdf`, bible ref subfolders, `videos/`, `storyboards/`).

## The 4 episodes (sheet IDs)

| Ep | Sheet | ID | Shots | Storyboards |
|----|-------|----|------|-------------|
| 1 | Ep 1 — Brizo | `1KiXiKcOhRqcxq0S9Qzop8SC6hMzLkLr7wtLSg7BFZP8` | 70 | 14 sets |
| 2 | Ep 2 — Bedroom | `1YDq2W8WJvFxYDOJ7GmoorsBmfJjgxoVoMknMhEx_3Og` | 68 | 14 sets |
| 3 | Ep 3 — Brizo | `1kn7mo43SdfqGkEPp6pBVUOPE3IjG8rtcLk6lBst9YPA` | 69 | 14 sets |
| 4 | Ep 4 — Ocean | `1gN65OUnnWt8LuD44fEVe-cjHxe2ybxEPWXbKtYJIlgM` | 59 | 12 sets |

All sheets use the v2.2 schema (Shotlist / Storyboard Prompts / Video Prompts / CHARACTERS / LOCATIONS /
COSTUME / PROPS / EFFECTS / Asset Library). Dashboard slug: `brizo_ep01` (and per-ep).

## Cast

- **JULIA** — lead (in Eps 1, 2, 4)
- **HAYLEY** — (Eps 1, 2, 4)
- **JOHN** — (Eps 1, 2, 3)
- **ALIEN CREATURE / "The Entity"** — (Eps 1, 4)

## Locations (across eps)

The Brizo (Hallway, Cockpit, Docking Port, Changing Room, Greenhouse, Kitchenette, Interior, Exterior),
The Asteria (Interior, Exterior, Bedroom), Julia's Bedroom, Corridor outside bedroom, Alien Ship Crash Site,
The Ocean – Deep Sea Floor, Underwater environment.

## Locked global style (lighting + palette — no characters/props)

> Cinematic deep-sea sci-fi thriller look. Very low-key, high-contrast lighting with crushed near-black
> shadows. Dominant desaturated teal and cyan-green palette, cool steel-white highlights, and only small
> sparing warm accents (dim amber and signal-red practical/warning lights) for contrast — no bright or
> saturated colour elsewhere. Hard, cool practical light sources (fluorescent strips, ring lights, instrument
> glows) cutting through darkness, with strong rim/edge light separating forms from the black. Claustrophobic,
> damp, submerged atmosphere: volumetric haze, fine mist, soft bloom around lights, condensation and moisture
> on surfaces. Anamorphic widescreen, shallow depth of field, fine film grain, gentle filmic contrast,
> naturalistic exposure in cold light. Moody, oppressive, tense.

## Action — render current state

Default (no args, or `status`): print the slate table above, then read each ep's LIVE state and report:
- shot count (Shotlist col A digits)
- storyboard sets + how many `Done` (Storyboard Prompts col F)
- vidgen progress (sets with a Video Iter URL in SP col M or N)

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 - <<'PY'
import gspread
from auth import get_credentials
gc=gspread.authorize(get_credentials())
EPS=[("Ep 1 — Brizo","1KiXiKcOhRqcxq0S9Qzop8SC6hMzLkLr7wtLSg7BFZP8"),
     ("Ep 2 — Bedroom","1YDq2W8WJvFxYDOJ7GmoorsBmfJjgxoVoMknMhEx_3Og"),
     ("Ep 3 — Brizo","1kn7mo43SdfqGkEPp6pBVUOPE3IjG8rtcLk6lBst9YPA"),
     ("Ep 4 — Ocean","1gN65OUnnWt8LuD44fEVe-cjHxe2ybxEPWXbKtYJIlgM")]
for name,sid in EPS:
    sh=gc.open_by_key(sid)
    a=sh.worksheet("Shotlist").col_values(1)
    nshots=len([x for x in a[1:] if x.strip().isdigit()])
    sd=sh.worksheet("Storyboard Prompts").get("A10:N60")
    sets=[r for r in sd[1:] if r and r[0].strip()]
    done=sum(1 for r in sets if len(r)>5 and r[5].strip().lower()=="done")
    vid=sum(1 for r in sets if (len(r)>12 and r[12].strip()) or (len(r)>13 and r[13].strip()))
    print(f"{name}: {nshots} shots | storyboards {done}/{len(sets)} | vidgen {vid}/{len(sets)} sets")
PY
```

- `/brizo style` → just print the locked global style block.
- `/brizo <ep>` → focus one episode (print its ID, cast, locations, and live status).
- `/brizo vidgen <ep> <set>` → hand off to the vidgen flow for that episode sheet + set (BytePlus Seedance, v2.2 path). Use the locked global style as the look unless told otherwise.

## Current blocker — Asset Library not populated

vidgen needs the Asset Library (col C `asset://` codes) filled so character/location refs bypass face
moderation. As of 2026-05-26 it is mostly empty:
- **Ep 1 — Brizo:** partial — 2 CHARACTERS, 2 COSTUME, 1 LOCATIONS uploaded (cast is 4 chars + ~8 ship
  locations → still incomplete).
- **Ep 2 / 3 / 4:** empty (header/instruction rows only).

So before Brizo vidgen: generate bible refs (`/imggen-all-assets`), upload to BytePlus
(`/byteplus-upload-all`), and confirm the Asset Library rows show `Uploaded` with codes. Storyboards are
already done, so the only gate to vidgen is refs.

## Notes

- All 4 eps currently: shotlists + storyboards COMPLETE; **no video generated yet** — vidgen is the next
  stage, blocked only on the Asset Library above.
- There is also an **Ep 3 — Brizo** (kept the Brizo name); Eps 2 & 4 are named by setting (Bedroom / Ocean).
- Trash holds older `*— SOT` Brizo sheets — ignore them; the 4 above are canonical.
