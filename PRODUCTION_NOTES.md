# Sajangnim Production Notes

Running log of production-side issues, conventions, and asks for the team. Add new entries at the top with date stamps.

> **Show context:** *Diam Diam Aku Cinta Sajangnim* is a **trilingual production** — Bahasa Indonesia, English, and Seoul Korean intermixed across nearly every scene. This adds production complexity at every layer: shotlists need accent annotation per line, vidgen needs voice-cloning per character, post needs subtitle handling for 3 languages. **Treat this show as harder than the typical microdrama.**

---

## 2026-05-05 — open issues + asks for the team

### 1. Logo on chef uniforms — PARTIALLY RESOLVED 2026-05-06 (prompt side fixed; photos still trigger bleed)

**Original problem:** Hanbyeol embroidered crest + name tags caused recurring inconsistency. Seedance also bled binding-block text directly into the chef coat label area.

**Done — prompt-side fixes:**
- Stripped literal-text triggers from CHARACTERS bible Wardrobe fields (TARA: `name tag on chest reading 'TARA — JUNIOR'` → plain; JOON-HO: `Hanbyeol embroidered crest on chest` → plain)
- Added explicit "no markings or text or embroidery" directive to all character Wardrobe entries
- Going-forward convention: avoid "name tag", "embroidered", "label reading", "crest", "logo on chest", or any quoted text strings in CHARACTERS bible Wardrobe column

**REMAINING — needs team action:** Even with prompt cleaned, Seedance still renders garbled text on the chest because the **reference photos themselves show the chef coat with the Hanbyeol logo**. The model picks up the visual feature from the iter-1 image and hallucinates similar shape/text on output. Verified 2026-05-06: gen still produces gibberish embroidery on coats.

**Ask for the team:** redo character + costume reference photos with **completely plain white chef coats** — no Hanbyeol crest, no name tag, no piping, no embroidery, no logo of any kind. Just clean double-breasted whites in studio neutral lighting.

Files needed (re-upload via `_upload_to_byteplus_v2.py` — old asset codes get overwritten):
- TARA: clean front, no name tag
- LEE JOON-HO: clean front, no Hanbyeol crest
- PARK MIN-JUN: clean front
- BU ENDANG: clean front
- GALIH: clean front (line cook style ok, just no logo)
- COSTUME bible "Chef Uniform" entries: same — plain white only

Once new clean photos land:
1. Replace iter-1 images in CHARACTERS / COSTUME bibles (Drive)
2. Re-run `_upload_to_byteplus_v2.py` (deletes old asset codes, uploads clean ones)
3. Vidgen automatically picks up the new asset:// URLs

Until then: every gen will have some level of garbled fake-logo on the chest. Workable for early review, not for client-facing cuts.

### 2. More face videos per character

The Min-jun video face-loop (`asset-20260505210734-ks7jc`, 14s of Ray's face) was a major identity-adherence win — Seedance's identity transfer jumped from ~50% to ~85% with the video ref attached.

**Need from team — 5-15s clean face videos for:**
- TARA ANJANI (face-cam neutral, slight head turns)
- LEE JOON-HO (face-cam neutral, slight head turns)
- PARK MIN-JUN — already have Ray as stand-in, would prefer the actual cast face once locked
- BU ENDANG
- GALIH

**Spec:** 720p mp4, 1.8–15.2s, ≤50MB, plain background, neutral lighting, slight angle changes (no extreme head turns), **no dialogue audio over the face** (leave silent or remove audio track — voice samples go in separately).

Drop in the show's Drive `01. Assets/Character/<NAME>/` folder. I'll handle the BytePlus upload + Asset Library wiring once they land.

### 3. Dialogue accent/language brackets — REQUIRED on every dialogue line

Because the show is trilingual and dialogue switches mid-line in some shots, **every dialogue cell** in `Shotlist!G` needs an explicit accent/language tag in parentheses at the END of the dialogue line. This is what Seedance's voice-clone path uses to choose pronunciation.

**Format:** `<character>: <dialogue text>. (<language/accent>)`

**Examples:**
- `MIN-JUN: Five kilos. Ten minutes. Go. (korean accented english)` ← shot 21, just fixed
- `TARA: Maaf, Sajangnim... (jakarta bahasa indonesia)`
- `JOON-HO: 괜찮아. (seoul korean)`
- `MIN-JUN: 아이구 TARA-ssi, be careful. Dapur Korea bukan tempat anak-anak. (korean-bahasa code-switch)`

**Allowed accent/language tags:**
- `(jakarta bahasa indonesia)` — default for most TARA / Indonesian-staff lines
- `(seoul korean)` — JOON-HO native, MIN-JUN native
- `(korean accented english)` — MIN-JUN, JOON-HO speaking English
- `(indonesian accented english)` — TARA, GALIH, BU ENDANG speaking English
- `(korean-bahasa code-switch)` — MIN-JUN slipping between
- `(bahasa-korean code-switch)` — TARA slipping between
- `(seoul korean with bahasa accent)` — TARA's heritage Korean
- `(reflexive korean code-switch)` — TARA dropping single Korean words mid-Bahasa

This bracket convention is **mandatory going forward** — no dialogue cell ships without it. The vidgen pipeline reads col G verbatim, so missing tags means default voice = wrong character.

---

## Pipeline notes (reference for the team)

- **Source of truth: Google Sheets** — see `dash_app/app.py` SERIES_CONFIG for all 6 episode sheet IDs.
- **Edits flow downstream automatically.** Edit `Shotlist!G` (dialogue) → next vidgen click reads the fresh value. No "republish" step.
- **Bible-level data lives on Ep 1's sheet** (CHARACTERS, LOCATIONS, COSTUME, PROPS, EFFECTS, Asset Library). Same data shared across all 6 eps.
- **Adding a character to the bible** auto-flows to:
  1. Dashboard's CHARACTERS tab card
  2. `refs_audit.py` detection on Shotlist
  3. `byteplus_vidgen.py` Reference identities binding block (auto-built per-click)
- **Asset codes** (BytePlus Private Asset Library) bypass face-moderation only when referenced via `asset://asset-<id>` scheme — not raw HTTPS URLs.
- **Dashboard refresh:** click ↻ Refresh button to invalidate the 60s cache and pull fresh sheet state.

---

## How to add a new entry to this file

Add a new dated H2 section at the top of the file, above the most recent entry. Keep notes scannable:
- One issue per H3
- 1-2 sentences of context, then the action item / decision needed
- If a fix lands, mark the H3 as `[RESOLVED 2026-05-DD]` rather than deleting

---
