#!/usr/bin/env python3
"""
Replace the old PROPS tab with three Reve-API-ready bibles:
  - COSTUME  — character/group attires, weapons, signature items consolidated
  - PROPS    — small handheld / interactive items not absorbed into the location ref
  - EFFECTS  — magical and creature-secretion VFX

Each tab gets the same global-header treatment as LOCATIONS:
  Row 1: A=label, B=value (Type of reference)
  Row 2: A=label, B=value (Style)
  Row 3: A=label, B=value (Layout)
  Row 4: empty
  Row 5: column headers
  Row 6+: data + prompt formula

PROMPT FORMULA (column F, per row):
  =$B$1 & " - " & $B$2 & ", " & $B$3 & ", " & {Name} & " (" & {Worn By/Used By} & "): " & {Description}

What got merged:
  Old rows 2-12 (costume + Sun-Guard weapons) → consolidated into 6 COSTUME entries
  Old rows 17, 20, 21, 24-30 (locational architecture / set dressings) → DROPPED, baked
    into the LOCATIONS reference instead
  Tehuti's measuring staff → merged into Tehuti's COSTUME entry (signature item)
  Magical / creature effects (rows 31-37) → moved to EFFECTS tab
  Remaining handheld interactive items (rows 18, 19, 22, 23) → kept in PROPS
"""
from __future__ import annotations
import gspread
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"

# Globals shared across COSTUME / PROPS / EFFECTS
GLOBAL_STYLE = "flat lighting, against white background"
GLOBAL_LAYOUT = "no human figure, suspended in the air for visibility and reference"

# Column structure (11 cols, same for all 3 tabs)
HEADERS = [
    "Name",                     # A
    "Worn By / Used By",        # B
    "Description",              # C  (combined items + materials + signature)
    "First Shot #",             # D
    "Notes",                    # E
    "Prompt",                   # F  (auto-formula)
    "Iter 1 URL",               # G
    "Iter 2 URL",               # H
    "Status",                   # I  (hidden)
    "Error",                    # J  (hidden)
    "Feedback",                 # K  (team-editable, free text — written by review team, read by Claude)
]


COSTUMES = [
    (
        "Sun-Guard attire (rank and file)",
        "Sun-Guard infantry, archers, chariot corps (anonymous soldiers)",
        "White linen battle kilt with sharp ironed pleats and dust at the hem, "
        "rope ties at the waist; polished bronze chest plate with embossed sun-disc "
        "insignia (hammered finish, scratches and battle nicks); curved bronze blade "
        "at the hip and bronze spear in hand. Archer subset adds a wooden recurve bow "
        "and bronze-tipped arrows. Chariot corps operates wooden war chariots with "
        "bronze plating, drawn by horse pairs. Bronze plates catch sunlight in formation.",
        "14",
        "Standard military uniform across the Sun-Guard.",
    ),
    (
        "Ahmose, Captain of the Sun-Guard",
        "AHMOSE",
        "Sun-Guard base kit (white linen battle kilt + polished bronze chest plate "
        "with embossed sun-disc insignia) layered with a leopard cape draped from the "
        "shoulders — fur slightly matted with travel dust, brass clasp at the throat. "
        "Cape is rank-earned, not decorative. Carries a bronze spear and a curved "
        "bronze blade. Old battle scars across bare chest and arms visible above the "
        "chest plate.",
        "15",
        "Leopard cape distinguishes him from rank-and-file Sun-Guard. Wields Ma'at "
        "conjuring magic (hand outstretched in invocation).",
    ),
    (
        "Khensu, Son of Ra",
        "KHENSU",
        "Torn linen loincloth — sun-bleached, frayed at the edges, woven linen fibers "
        "visible up close, faint stains from work; rope belt at the waist; bare-chested "
        "with bronze sun-darkened skin; barefoot or simple sandals with worn straps. "
        "Signature prop: ox-hide whip — heavy braided leather, thick and worn from "
        "labor use. Transforms during the episode into a Lash of Solar Fire — long "
        "braided whip of living sunfire, bright, hot, almost too luminous to look at "
        "directly, cracks like thunder when used.",
        "22",
        "Humble laborer attire that marks Khensu as not-a-fighter. Whip transforms in "
        "the climax beat (shot 58).",
    ),
    (
        "Tehuti, Old Surveyor",
        "TEHUTI",
        "Weathered linen robe in layered desert tones (sand, ochre, dusty rose) — "
        "heavy hand-spun thread, frayed seams, dust-coated hem, faint ink stains at "
        "the cuffs from scrolls; rope belt; bare feet in worn leather sandals. "
        "Signature prop: carved wooden measuring staff with surveyor's notches, "
        "leaned upon for support and used to gesture during instruction.",
        "24",
        "Mentor archetype. Measuring staff is the visual identifier.",
    ),
    (
        "Seshet, Priestess",
        "SESHET",
        "Flowing caftan in muted desert tones (dusty rose, ochre, faded gold) — fine "
        "woven linen with subtle weave texture, layered drape, brass thread embroidery "
        "at the cuffs; thin priestly veil — sheer, drifts in the breeze across her "
        "face; brass amulet at the throat; minimal jewelry, refined.",
        "25",
        "No carried prop — the veil itself is her visual signature.",
    ),
    (
        "Merchant / bazaar peasant attire",
        "MERCHANT and bazaar background extras",
        "Sun-bleached linen wrap (peasant) — frayed at the hem, faded ochre, "
        "dust-stained; rope belt; bare feet in old leather sandals; sun-darkened skin "
        "with visible pores; dust streaked across forehead and neck; weathered hands "
        "with cracked knuckles.",
        "4",
        "Common attire for bazaar background characters.",
    ),
]


PROPS = [
    (
        "Copper trinkets",
        "Bazaar merchants",
        "Hanging copper jewelry and ornaments waved at passing customers — bracelets, "
        "pendants, coin-shaped charms, scarab figurines; aged copper patina, "
        "hand-hammered finish, occasional verdigris green at edges.",
        "2",
        "Bazaar wares; visual texture of marketplace abundance.",
    ),
    (
        "Dyed fabric stacks",
        "Bazaar merchants",
        "Stacks of dyed cloth in jewel tones (lapis blue, ochre, faded crimson, dusty "
        "rose) — hanging from poles, draped on stalls, woven linen with visible weave "
        "texture, slight fade where direct sun has bleached the fibers.",
        "2",
        "Bazaar wares; color contrast against the sun-bleached linen of peasant attire.",
    ),
    (
        "Salted fish slabs",
        "MERCHANT (the wares he hawks)",
        "Slabs of dried, salt-crusted fish hanging from ropes at the merchant's stall "
        "— pale flesh underneath, white salt crystals visible across the surface, dark "
        "cured edges, slightly translucent at the thinnest sections.",
        "4",
        "Merchant's specific wares; he yells 'Salted fish! Best in the kingdom!' to "
        "establish bazaar life.",
    ),
    (
        "Collapsed fruit cart",
        "KHENSU (parkour interaction)",
        "Wooden cart tipped on its side — figs and pomegranates spilled out across "
        "the sand, splintered wheel, leather lash strap dangling, rough-hewn planks "
        "with iron nails, sun-bleached wood grain visible.",
        "33",
        "Used by Khensu as a vault during the parkour descent from the rooftop.",
    ),
]


EFFECTS = [
    (
        "Magical fire arrows (volley)",
        "Sun-Guard archers (Ahmose's volley command)",
        "Hundreds of arrows mid-flight with arrowheads igniting in gold-and-red "
        "magical flame; bronze-tipped, wood shafts; flame trail behind each arrow; "
        "arc descending toward the Spawn from a high arc; magical heat shimmer; "
        "subtle gold particles trailing.",
        "44",
        "Cracks the Spawn's obsidian shell but releases the tiny scorpion swarm.",
    ),
    (
        "Wall of Sand (Ma'at conjuring)",
        "AHMOSE (caster)",
        "Massive ring of sand erupting from the desert floor, swirling upward in a "
        "perfect ring around the Spawn like a moving fortress; sand particles caught "
        "in mid-spin; gold-tinged light from invocation; height of a multi-story "
        "building; ground cracks at the base where the wall emerges.",
        "64",
        "Fails when Spawn slams its pincer through the wall, sand exploding outward.",
    ),
    (
        "Golden veins of light",
        "KHENSU (solar magic)",
        "Molten sunlight veins racing from the earth up Khensu's fingers, wrist, and "
        "forearm — subtle internal glow under the skin (not external lights), pulsing "
        "warm gold beneath bronze flesh; faint shimmer; magical resonance, like "
        "lava-light moving through cracks in stone.",
        "57",
        "Power-up animation. Reignites in the crater scene.",
    ),
    (
        "Black frost",
        "KHENSU (final-strike effect)",
        "Layer of black frost spreading over the mini-scorpions in mid-leap — "
        "crystalline, glittering, dark obsidian-tinged ice; freezes them solid in the "
        "air with a creep-pattern outward from a center point; faint blue undertone.",
        "75",
        "Tied to the whip-yank that snaps the Spawn's stinger. Mini-scorpions then "
        "shatter into black glass shards.",
    ),
    (
        "Golden vortex / sun flare",
        "KHENSU (CLIFF moment)",
        "Brilliant golden flare around Khensu's silhouette — swirling vortex of light, "
        "ribbons of sand and dust caught in the spin, eclipsing the desert sun behind "
        "him; warm gold core, blinding bright at the center, ribbons trailing outward; "
        "subtle internal light source (Khensu himself).",
        "82",
        "Final beat of Episode 1; Khensu vanishes into this in Episode 2's opening.",
    ),
    (
        "Yellow bile (Spawn secretion)",
        "ISFET SPAWN",
        "Thick yellow bile dripping from the Spawn's twitching mandibles; sizzles and "
        "smokes on contact with sand; viscous, glowing slightly with internal heat; "
        "acid-eaten craters in the sand where it lands; sulfurous yellow-green tint.",
        "10",
        "Acidic; visual menace beat early in the Spawn reveal.",
    ),
    (
        "Toxic steam (Spawn emission)",
        "ISFET SPAWN",
        "Burst of toxic steam released from the creature's tail; hisses through the "
        "heat like poison from a furnace; pale yellow-green tint; coiling vapor; "
        "writhing, dense, low-lying like ground fog; seems to dissolve sand it touches.",
        "21",
        "Released during the chariot-smash beat.",
    ),
]


def build_tab(sh, *, title: str, type_value: str, data: list[tuple]):
    """Build a global-headered bible tab (COSTUME / PROPS / EFFECTS).

    Layout: rows 1-3 globals, row 4 empty, row 5 headers, row 6+ data.
    """
    existing = next((w for w in sh.worksheets() if w.title == title), None)
    if existing:
        sh.del_worksheet(existing)
        print(f"  removed existing {title!r}")

    n_data = len(data)
    n_cols = len(HEADERS)
    last_col = chr(ord("A") + n_cols - 1)  # 'J'
    total_rows = 5 + n_data + 5

    ws = sh.add_worksheet(title=title, rows=total_rows, cols=n_cols)

    # Globals (rows 1-3)
    ws.update(range_name="A1:B1", values=[["Type of reference", type_value]])
    ws.update(range_name="A2:B2", values=[["Style", GLOBAL_STYLE]])
    ws.update(range_name="A3:B3", values=[["Layout", GLOBAL_LAYOUT]])

    # Headers (row 5)
    ws.update(range_name=f"A5:{last_col}5", values=[HEADERS])

    # Data + prompt formula (rows 6+)
    rows_with_formula = []
    for i, row in enumerate(data):
        sheet_row = 6 + i
        prompt_formula = (
            f'=$B$1&" - "&$B$2&", "&$B$3&", "&A{sheet_row}'
            f'&" ("&B{sheet_row}&"): "&C{sheet_row}'
        )
        # name, worn_by, description, first_shot, notes, prompt_formula, iter1, iter2, status, error, feedback
        new_row = [row[0], row[1], row[2], row[3], row[4], prompt_formula, "", "", "Pending", "", ""]
        rows_with_formula.append(new_row)

    ws.update(
        range_name=f"A6:{last_col}{5 + n_data}",
        values=rows_with_formula,
        value_input_option="USER_ENTERED",
    )

    # Formatting
    sh.batch_update({
        "requests": [
            # Bold global label cells (A1:A3)
            {
                "repeatCell": {
                    "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 3,
                              "startColumnIndex": 0, "endColumnIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            # Soft fill on global value cells (B1:B3)
            {
                "repeatCell": {
                    "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 3,
                              "startColumnIndex": 1, "endColumnIndex": 2},
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.96, "green": 0.96, "blue": 0.92}}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            },
            # Bold headers (row 5)
            {
                "repeatCell": {
                    "range": {"sheetId": ws.id, "startRowIndex": 4, "endRowIndex": 5,
                              "startColumnIndex": 0, "endColumnIndex": n_cols},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            # Freeze rows 1-5 (globals + headers)
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 5}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Hide Status (col I, idx 8) + Error (col J, idx 9)
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 8, "endIndex": 10},
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            },
        ]
    })

    print(f"  ✓ {title!r}: {n_data} rows ready (globals at rows 1-3; data from row 6)")


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")

    # Drop the old PROPS tab — it's being replaced by the 3-way split
    existing_props = next((w for w in sh.worksheets() if w.title == "PROPS"), None)
    if existing_props:
        sh.del_worksheet(existing_props)
        print("  removed old PROPS tab (replaced by 3-way split)")

    print()
    print("Building bible tabs...")
    build_tab(sh, title="COSTUME", type_value="Costume reference", data=COSTUMES)
    build_tab(sh, title="PROPS",   type_value="Prop reference",    data=PROPS)
    build_tab(sh, title="EFFECTS", type_value="Effect reference",  data=EFFECTS)

    print()
    print("Final tab list:")
    for w in sh.worksheets():
        print(f"  - {w.title!r}")

    print()
    print("Sample COSTUME prompt for Sun-Guard (row 6):")
    print(f"    Costume reference - {GLOBAL_STYLE}, {GLOBAL_LAYOUT}, "
          f"Sun-Guard attire (rank and file) (Sun-Guard infantry, archers, chariot corps "
          f"(anonymous soldiers)): White linen battle kilt...")


if __name__ == "__main__":
    main()
