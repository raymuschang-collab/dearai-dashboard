# Atomization Rules

Each shotlist row = one generation on Nanobanana 2 / Seedance 2. The editor picks the best 1–2 seconds from each 3–4s clip. That's why atomization matters: compound shots lock the AI into doing multiple things at once, which it's bad at.

## The Five Rules

1. **One action per row.** If the script says "Henry hangs up and bolts from the car", that's two rows — "Henry ends the call" + "Henry throws open the door and bolts".
2. **One subject per row.** Character A's action and Character B's reaction are separate rows. Cut them.
3. **One angle per row.** Don't describe a shot that zooms from WS to CU. That's two shots.
4. **Dialogue cuts back-and-forth.** Each spoken line gets its own row. Put listener reactions between speakers.
5. **Duration 3 or 4 seconds only.** Never 1–2s (too short for coherent generation). Never 5+s (wastes generation budget — editor only uses 1–2s anyway).

## Before/after examples

### Example 1 — Compound dialogue exchange → atomic

**Before (compound):**
```
1. [CU rearview] Henry on phone, panicked. Arif watches uneasy. Henry: "Mereka sudah menemukan semua rekeningnya. Bro, saya butuh — tidak, dengarkan saya —"
```

**After (atomic):**
```
1. [CU rearview] Henry's panicked eyes, phone to ear.  
   Dialogue: "HENRY: Mereka sudah menemukan semua rekeningnya. Semuanya."
2. [CU rearview] Arif's eyes watching Henry, unsettled.  
   Dialogue: (none)  
   Microexp: brow knits in unease
3. [CU rearview] Henry, voice cracking mid-plea.  
   Dialogue: "HENRY: Bro, saya butuh — tidak, dengarkan saya —"
```

One compound shot → three atomic shots. The editor cuts between them for rhythm.

### Example 2 — Compound action → atomic

**Before:**
```
3. [MCU handheld] Henry ends his call, stuffs papers into briefcase, car stops at red light, Henry bolts from the car.
```

**After:**
```
5. [MCU] Henry yanks the phone from his ear, ends the call with a trembling thumb.
6. [Insert] Henry's hands stuffing papers into a leather briefcase, zipper ripping shut.
7. [WS] Exterior: the Avanza stopped at a red light on Sudirman, rain streaking the windshield.
8. [MS] Henry throws open the rear door and bolts, vanishing into the crowd.
```

One compound beat → four atomic shots. Total: 13 seconds of coverage (3+3+3+4). Editor assembles.

### Example 3 — Reveal pan (stays atomic even though it "feels like one shot")

**Before:**
```
43. [MS handheld] Arif crosses to the window and parts the curtain — sees Pajero Sport parked across the alley.
```

**After:**
```
43. [MS Handheld] Arif crosses to the kost window and parts the curtain a finger's width.
44. [Insert] POV through the curtain: a black Mitsubishi Pajero Sport parked across the alley, tinted windows, lights off.
```

Two atomic shots. The AI generates each; the editor can choose to cut (traditional coverage) OR to glue them with a camera move (handheld push from the curtain to the Pajero). The merge candidate note in E44 tells the editor this is an option.

## What NOT to atomize

Some shots are already atomic. Don't split them.

- **Insert shots** — a phone screen, a sign, an object close-up. Already one thing.
- **Wide establishers** — "Exterior: Sudirman at night, rain on the pavement." One shot, one description.
- **Single-character reaction beats** — a face reacting to something that happened off-screen. Already atomic.

## Duration guide

| Duration | When to use |
|----------|-------------|
| 3s | Default. Dialogue CUs, reaction beats, most inserts. |
| 4s | Slower/held moments: landscape reveals, dramatic cliffhanger CUs, environmental establishers, rack focus pulls. |

Never 1s, 2s, or 5s+. Stay in the 3–4s window. The editor can always cut to 1s in post, but they can't stretch a short clip.

## Shot count targets

| Episode runtime | Target shot count |
|-----------------|-------------------|
| 60s | 50–65 atomic shots |
| 75s | 60–75 atomic shots |
| 90s | 65–80 atomic shots |
| 120s | 80–100 atomic shots |

If you're well below target, the atomization is too loose — compound shots slipped through. If you're well above, either you're over-covering (cut redundant reactions) or the episode's too long.

## Atomization checklist

Before declaring the shotlist done:

- [ ] Every row is one action
- [ ] No row has two characters doing two things
- [ ] No row has a camera that zooms, pans, AND dollies in one shot
- [ ] Dialogue exchanges are cut between speakers (not two-shot)
- [ ] Durations are all 3 or 4
- [ ] Shot count is within episode-length target range
