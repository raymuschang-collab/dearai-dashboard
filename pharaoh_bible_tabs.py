#!/usr/bin/env python3
"""
Add CHARACTERS, LOCATIONS, PROPS bible tabs to the Strike! Pharaoh King Ep 1 sheet.

These are V2 setup tabs — they catalog characters, locations, and props that
appear across the episode, with a Reference Image URL column ready for when
character/location refs become available (the V2 storyboard upgrade).

Pre-populated from the script + shotlist. User can edit/enrich after.
"""
from __future__ import annotations

import gspread
from googleapiclient.discovery import build

from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"


CHARACTERS_HEADERS = [
    "Name", "Role", "Age", "Description",
    "Costume / Wardrobe", "Voice / Accent",
    "Reference Image URL", "First Shot #", "Notes",
]

CHARACTERS = [
    [
        "KHENSU",
        "Son of Ra (protagonist)",
        "20s",
        "Ripped, sculpted body of a man who has spent years dragging stone across the desert. Bronze skin coated in sweat and dust. Quiet hero: humble origins, latent solar magic.",
        "Torn linen loincloth (humble laborer attire, marks him as not-a-fighter)",
        "Heightened English (mythic). Young, fear hardening into resolve over the episode.",
        "",
        "22",
        "Power source: solar magic via golden veins through forearm. Ox-hide whip transforms into Lash of Solar Fire when channeled. Speaks the show's title-card: 'KHENSU, SON OF RA.'",
    ],
    [
        "AHMOSE",
        "Captain of the Sun-Guard",
        "30s",
        "Broad-shouldered, battle-worn. Old scars stretch across his bare chest and arms — carved there by years of war beneath the desert sun. Disciplined and afraid in equal measure.",
        "White linen battle kilt, bronze chest plate, sun-disc insignia, leopard cape (rank-earned, not decorative)",
        "Heightened English (mythic). Hard, commanding when leading; wavers in private moments.",
        "",
        "15",
        "Wields Ma'at conjuring magic ('Ma'at, bring justice and order. Bind this chaos!'). Title-card: 'AHMOSE, CAPTAIN OF THE SUN-GUARD.' Saved by Khensu in finale.",
    ],
    [
        "TEHUTI",
        "Old surveyor / mentor",
        "60s",
        "Gaunt old surveyor with one clouded eye and skin like dried parchment. Calculating, knowing, otherworldly poise.",
        "Weathered linen robe, leans on a carved measuring staff",
        "Heightened English (mythic). Low, certain, prophet-like cadence.",
        "",
        "24",
        "Speaks the call to action: 'Khensu. It's time. You must destroy it.' Mentor archetype; calculates the fate of the world.",
    ],
    [
        "SESHET",
        "Priestess / mystic",
        "50s",
        "Composed and mysterious. Something priestly and otherworldly about her presence. Veil moves softly in the desert wind.",
        "Flowing caftan, thin priestly veil",
        "Heightened English (mythic). Low, serene, oracular.",
        "",
        "25",
        "Delivers the awakening line: 'You carry the power of the first light.' Pairs with Tehuti as Khensu's mentor duo.",
    ],
    [
        "MERCHANT",
        "Bazaar background (speaking)",
        "Unspecified adult",
        "Anonymous peasant trader in the HOOK opening. Shouts wares before chaos erupts.",
        "Sun-bleached linen wrap (peasant)",
        "Heightened English (mythic). Shouting cadence, market din.",
        "",
        "4",
        "One line: 'Salted fish! Best in the kingdom!' Establishes the everyday-life baseline that the Spawn shatters.",
    ],
    [
        "ISFET SPAWN",
        "Monster antagonist",
        "N/A (creature)",
        "Sixty-foot scorpion-like beast. Obsidian-black shell that gleams like volcanic glass, jagged armored plates with oily sheen. Yellow bile drips from twitching mandibles, sizzles on contact with sand. Massive pincers, towering stinger that briefly eclipses the sun.",
        "(creature) — armor plates, pincers, mandibles, segmented tail, stinger",
        "Monstrous shrieks and toxic-steam hisses. No spoken dialogue.",
        "",
        "8",
        "Spawn of Apep. Releases tiny scorpions when shell cracks. Killed by Khensu's solar whip + golden vortex. Dissolves into drifting sand at end of episode.",
    ],
    [
        "TINY SCORPIONS",
        "Swarm spawn (creature)",
        "N/A (creature)",
        "Glistening like shards of wet obsidian. Move as a dense, fast-moving black wave. Climb under armor, into mouths and ears.",
        "(creature) — wet-obsidian carapace",
        "Skittering swarm sound, no dialogue.",
        "",
        "47",
        "Released from Spawn's broken shell. Frozen and shattered by black frost from Khensu's whip strike.",
    ],
]


LOCATIONS_HEADERS = [
    "Name", "Type (INT/EXT)", "Description",
    "Lighting / Mood", "Time of Day",
    "Reference Image URL", "First Shot #", "Notes",
]

LOCATIONS = [
    [
        "Peasant Bazaar",
        "EXT",
        "Sprawling desert marketplace. Narrow aisles twist between rows of low wooden stalls draped in faded cloth canopies. Goats, copper trinkets, dyed fabrics, salted fish, clay jars.",
        "Ruthless white sun, midday glare, harsh shadows. Dust haze rising once the Spawn erupts.",
        "Day",
        "",
        "1",
        "HOOK setting. Gets attacked by the Isfet Spawn. Cycles from alive-and-crowded to chaos.",
    ],
    [
        "Desert Plateau / Great Pyramid",
        "EXT",
        "Beyond the bazaar — a half-finished pyramid towers over the desert, pale limestone blocks glowing under the sun. Immense, sacred, unfinished — like a monument caught between earth and heaven.",
        "High noon glare, sand reflecting light. Spawn casts a giant death-shadow across the pyramid mid-battle.",
        "Day",
        "",
        "13",
        "Sun-Guard formation in front of the structure. Sacred site they're protecting from the Spawn.",
    ],
    [
        "Rooftop",
        "EXT",
        "Flat mud-brick rooftop above the bazaar. Khensu's vantage point, looking down on the slaughter. Tehuti and Seshet stand behind him.",
        "Direct sun + dust haze rising from the chaos below. Wind through cloth.",
        "Day",
        "",
        "22",
        "Site of the call-to-action dialogue. Khensu leaps from here in JOLT 2.",
    ],
    [
        "Pyramid Field",
        "EXT",
        "Battlefield between the bazaar and the pyramid. Sand floor, debris of war: shattered spears, overturned bodies, war chariots in pieces.",
        "Dust haze, dramatic shadows from the Spawn, magical fire-arrow glow at the volley moment.",
        "Day",
        "",
        "38",
        "Main battle space. Sun-Guard vs. Spawn here. Khensu's solar whip strike happens here.",
    ],
    [
        "Base of Pyramid",
        "EXT",
        "Sand floor at the foot of the pyramid. Fallen supply carts, broken oxen yokes, scattered wreckage. Where Khensu lands.",
        "Long pyramid shadow + Spawn shadow both falling across the space.",
        "Day",
        "",
        "53",
        "Where Khensu finds the ox-hide whip and channels solar magic to transform it.",
    ],
    [
        "Impact Crater",
        "INT (within EXT)",
        "Crater of broken stone and dust. Khensu lies half-buried, struggling to breathe.",
        "Dim, dusty, claustrophobic vs. the bright battle around it. Recovery beat.",
        "Day",
        "",
        "67",
        "Khensu's awakening moment. POV shot from his blurred vision to the frozen scorpions inches from Ahmose.",
    ],
]


PROPS_HEADERS = [
    "Name", "Category", "Description", "Used By",
    "Reference Image URL", "First Shot #", "Episode", "Notes",
]

PROPS = [
    # === COSTUMES ===
    ["White linen battle kilt", "Costume — military", "Pleated white linen, knee-length, standard Sun-Guard issue.", "Sun-Guard", "", "14", "Ep 1", "Worn under bronze chest plate."],
    ["Bronze chest plate", "Costume — armor", "Polished bronze plate with sun-disc insignia.", "Sun-Guard, Ahmose", "", "14", "Ep 1", "Catches sunlight in formation shots."],
    ["Sun-disc insignia", "Costume — heraldry", "Golden sun-disc emblem fixed to chest plates and shields.", "Sun-Guard", "", "14", "Ep 1", "Visual marker of Pharaoh's elite military."],
    ["Leopard cape", "Costume — rank", "Fur cape draped from shoulders. Earned through blood and victory, not decorative.", "Ahmose", "", "15", "Ep 1", "Identifies Ahmose as Captain. Snaps in wind during charge."],
    ["Torn linen loincloth", "Costume — laborer", "Humble, frayed loincloth. Marks Khensu as a stonecutter, not a fighter.", "Khensu", "", "22", "Ep 1", "Stays the same throughout the episode — class signal."],
    ["Weathered linen robe", "Costume — elder", "Dust-toned robe, layered, parchment-like wear.", "Tehuti", "", "24", "Ep 1", ""],
    ["Flowing caftan", "Costume — priestly", "Long, flowing fabric in muted desert tones.", "Seshet", "", "25", "Ep 1", ""],
    ["Thin priestly veil", "Costume — priestly", "Sheer veil that drifts across her face in the desert wind.", "Seshet", "", "25", "Ep 1", "Visual signature for Seshet's mystic presence."],
    ["Sun-bleached linen wrap", "Costume — peasant", "Faded, dust-caked linen, common merchant attire.", "Merchants, bazaar background", "", "4", "Ep 1", ""],

    # === WEAPONS ===
    ["Bronze spear", "Weapon — Sun-Guard", "Long bronze-tipped spear. Snaps on impact with the Spawn's shell.", "Sun-Guard, Ahmose", "", "17", "Ep 1", "Doesn't penetrate obsidian armor — establishes the Spawn's invincibility."],
    ["Bronze blade / curved sword", "Weapon — Sun-Guard", "Curved bronze blade. Standard infantry sidearm.", "Sun-Guard", "", "14", "Ep 1", ""],
    ["War chariot", "Vehicle — military", "Wooden chariot with bronze plating, drawn by horse pair. Some carry archers.", "Sun-Guard chariot corps", "", "21", "Ep 1", "One is splintered by the Spawn's pincer; the volley is fired from a row of them."],
    ["Bow + arrows", "Weapon — Sun-Guard archers", "Wooden recurve bow + bronze-tipped arrows. Arrowheads ignite with magical fire (gold and red) in the volley.", "Sun-Guard archers", "", "40", "Ep 1", "Magic-fire arrows momentarily crack the Spawn's shell — but release the swarm."],
    ["Ox-hide whip", "Tool — laborer", "Heavy braided leather whip, thick and worn from labor use. Half-buried under a fallen supply cart.", "Khensu (initially)", "", "54", "Ep 1", "Transforms into Lash of Solar Fire when Khensu channels his power."],
    ["Lash of Solar Fire", "Weapon — magical (transformed)", "Long braided whip of living sunfire. Bright, hot, almost too luminous to look at directly. Cracks like thunder when used.", "Khensu", "", "58", "Ep 1", "Final-strike weapon. Snaps the Spawn's stinger and triggers the black-frost finish."],

    # === SET DRESSINGS — BAZAAR ===
    ["Faded cloth canopies", "Set dressing — bazaar", "Sun-bleached fabric canopies draped over wooden stalls.", "—", "", "1", "Ep 1", ""],
    ["Copper trinkets", "Set dressing — bazaar", "Hanging copper jewelry and ornaments waved at customers.", "Merchants", "", "2", "Ep 1", ""],
    ["Dyed fabric", "Set dressing — bazaar", "Stacks of dyed cloth in jewel tones.", "Merchants", "", "2", "Ep 1", ""],
    ["Clay jars", "Set dressing — bazaar", "Stacked clay storage jars. Tip and shatter when ground swells.", "—", "", "5", "Ep 1", ""],
    ["Goats", "Set dressing — bazaar", "Live goats weaving between sand-caked feet of merchants.", "—", "", "3", "Ep 1", ""],
    ["Salted fish", "Set dressing — bazaar", "Slabs of salted fish hanging from stalls.", "Merchant", "", "4", "Ep 1", "Mentioned in dialogue."],
    ["Collapsed fruit cart", "Set dressing — bazaar", "Wooden cart tipped on its side, figs and pomegranates spilled out.", "—", "", "33", "Ep 1", "Khensu uses as a vault during parkour descent."],
    ["Wooden balcony rail", "Set dressing — bazaar", "Wooden balcony rail in the upper bazaar.", "—", "", "36", "Ep 1", "Khensu slides the length of it during descent."],

    # === SET DRESSINGS — BATTLEFIELD / PYRAMID ===
    ["Limestone blocks", "Set dressing — pyramid", "Pale limestone blocks of the half-finished pyramid.", "—", "", "13", "Ep 1", "Glow under desert sun."],
    ["Mud-brick rooftop", "Set dressing — bazaar", "Flat mud-brick rooftop above the bazaar.", "—", "", "22", "Ep 1", "Tehuti / Seshet / Khensu vantage."],
    ["Brick dwelling", "Set dressing — bazaar", "Low brick houses around the bazaar.", "—", "", "12", "Ep 1", "Crushed by Spawn's pincer in JOLT 1."],
    ["Supply cart wreckage", "Set dressing — battlefield", "Broken cart, oxen yoke, scattered wood.", "—", "", "53", "Ep 1", "Where Khensu finds the ox-hide whip."],
    ["Shattered bronze spears", "Set dressing — battlefield", "Spears snapped at impact, scattered across sand.", "—", "", "38", "Ep 1", ""],
    ["War chariot wreckage", "Set dressing — battlefield", "Smashed chariot, splintered wood, fallen horse tack.", "—", "", "21", "Ep 1", ""],

    # === MAGICAL / CREATURE ===
    ["Tehuti's measuring staff", "Prop — character signature", "Carved wooden surveyor's staff with measurement notches.", "Tehuti", "", "24", "Ep 1", "Iconic identifier for Tehuti."],
    ["Magical fire arrows", "Magic — Sun-Guard volley", "Arrowheads igniting with gold-and-red flame mid-flight.", "Sun-Guard archers", "", "44", "Ep 1", "Cracks Spawn's shell but releases the swarm — dramatic irony."],
    ["Wall of Sand (Ma'at)", "Magic — Ahmose", "Massive ring of sand erupting from the desert floor, swirling around the Spawn like a moving fortress.", "Ahmose (caster)", "", "64", "Ep 1", "Conjured by Ahmose's invocation. Breaks apart when Spawn slams it."],
    ["Golden veins of light", "Magic — Khensu", "Molten sunlight veins racing from the earth up Khensu's fingers, wrist, and forearm.", "Khensu", "", "57", "Ep 1", "Power-up animation. Reignites in the crater scene."],
    ["Black frost", "Magic — Khensu (finishing)", "Layer of black frost spreading over the mini-scorpions. They harden into brittle black glass and shatter against Ahmose's armor.", "Khensu (caster, indirect)", "", "75", "Ep 1", "Final-strike effect. Tied to the whip-yank that snaps the Spawn's stinger."],
    ["Golden vortex / sun flare", "Magic — Khensu (cliff)", "Brilliant golden flare around Khensu's silhouette. Becomes a swirling vortex of light. Frame on which the episode fades to black.", "Khensu", "", "82", "Ep 1", "CLIFF beat. Khensu vanishes in this in Episode 2's opening."],
    ["Yellow bile (Spawn)", "Creature — Spawn secretion", "Thick yellow bile dripping from Spawn's twitching mandibles. Sizzles and smokes on contact with sand.", "Isfet Spawn", "", "10", "Ep 1", "Acidic; visual menace beat."],
    ["Toxic steam (Spawn)", "Creature — Spawn secretion", "Burst of toxic steam released from the creature's tail. Hisses through the heat like poison from a furnace.", "Isfet Spawn", "", "21", "Ep 1", ""],
]


def hide_column(sh, ws, col_index_zero_based: int) -> None:
    sh.batch_update({
        "requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index_zero_based,
                    "endIndex": col_index_zero_based + 1,
                },
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }]
    })


def freeze_header(sh, ws) -> None:
    sh.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }]
    })


def build_tab(sh, *, title: str, headers: list[str], rows: list[list[str]],
              hide_ref_col_index: int) -> None:
    """Create a fresh tab (or skip if it already exists)."""
    existing = next((w for w in sh.worksheets() if w.title == title), None)
    if existing:
        print(f"  '{title}' already exists — skipping. Delete manually if you want to rebuild.")
        return
    ws = sh.add_worksheet(title=title, rows=len(rows) + 5, cols=len(headers))
    end_col = chr(ord("A") + len(headers) - 1)
    ws.update(range_name=f"A1:{end_col}1", values=[headers])
    ws.update(
        range_name=f"A2:{end_col}{len(rows) + 1}",
        values=rows,
        value_input_option="USER_ENTERED",
    )
    freeze_header(sh, ws)
    hide_column(sh, ws, hide_ref_col_index)
    print(f"  ✓ '{title}' built fresh: {len(headers)} cols × {len(rows)} rows (Reference Image URL hidden)")


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")
    print(f"Existing tabs: {[w.title for w in sh.worksheets()]}")
    print()

    print("Building bible tabs...")
    build_tab(
        sh,
        title="CHARACTERS",
        headers=CHARACTERS_HEADERS,
        rows=CHARACTERS,
        hide_ref_col_index=6,  # column G = Reference Image URL
    )
    build_tab(
        sh,
        title="LOCATIONS",
        headers=LOCATIONS_HEADERS,
        rows=LOCATIONS,
        hide_ref_col_index=5,  # column F = Reference Image URL
    )
    build_tab(
        sh,
        title="PROPS",
        headers=PROPS_HEADERS,
        rows=PROPS,
        hide_ref_col_index=4,  # column E = Reference Image URL
    )

    print()
    print("Final tab list:")
    for w in sh.worksheets():
        print(f"  - {w.title!r}  rows={w.row_count}  cols={w.col_count}")


if __name__ == "__main__":
    main()
