#!/usr/bin/env python3
"""
Migrate the CHARACTERS tab on the Strike! Pharaoh King sheet to the expanded
22-column schema that maps 1:1 to the character-bible prompt fields.

Deletes the existing CHARACTERS tab and rebuilds with the new schema and
fully-populated data for all 7 characters. LOCATIONS and PROPS are untouched.

The Speech accent column is preserved (was tab col F in the old schema, now
col P in the new schema — concept retained, position changed).
"""
from __future__ import annotations

import gspread

from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"

CHARACTERS_HEADERS = [
    "Name",                          # A
    "Alias",                         # B
    "Role / Archetype",              # C
    "Age",                           # D
    "Gender / Pronouns",             # E
    "Ethnicity / Heritage",          # F
    "Height",                        # G
    "Weight / Build",                # H
    "Hair",                          # I
    "Eyes",                          # J
    "Distinguishing features",       # K
    "Wardrobe",                      # L
    "Signature accessory / prop",    # M
    "Personality",                   # N
    "Core theme",                    # O
    "Speech accent",                 # P  ← preserved per user request
    "Mood / aura",                   # Q
    "First Shot #",                  # R
    "Notes",                         # S
    "Iter 1 URL (off-white bg)",     # T  ← workflow / output
    "Iter 2 URL (dark bg)",          # U  ← workflow / output
    "Status",                        # V  ← workflow
    "Error",                         # W  ← workflow
    "Feedback",                      # X  ← team-editable, free text
]


# Pre-fill KHENSU's existing iter URLs since they're already generated.
# Format: (iter1_url, iter2_url, status, error)
KHENSU_ITER1 = "https://drive.google.com/file/d/1Q2QKJFKuwa29UEpAW1lW_aHvxGGYoSFc/view?usp=drivesdk"
KHENSU_ITER2 = "https://drive.google.com/file/d/1-BtrIEDYRyDMHfdw06bkfjr3Wonj6uT0/view?usp=drivesdk"


CHARACTERS = [
    [
        "KHENSU",
        "Son of Ra",
        "Hero / chosen one (protagonist)",
        "Mid-20s",
        "Male / he",
        "Ancient Egyptian; sun-dark bronze skin",
        "5'10\" / 178cm",
        "Ripped, sculpted, hard physical body of a man who has spent years dragging stone across the desert; lean muscle, no body fat, sinewy forearms",
        "Short, dark, dust-coated; close-cropped; sand grains visible at temples; sweat-damp behind the ears",
        "Brown, sharp; gold flares when channeling solar magic; visible iris detail, no cosmetic enhancement",
        "Bronze skin coated in sweat and dust with visible pores; sun-coarsened on shoulders and back; faint sunburn line at the loincloth waistband; thin pale scar across left forearm from a stone-cutting accident; dust embedded in skin creases at the elbows; golden veins of light appear on right forearm when magic activates (subtle internal glow under the skin, not external lights)",
        "Torn linen loincloth — sun-bleached, frayed at the edges, woven linen fibers visible up close, faint stains from work; rope belt; bare-chested; barefoot or simple sandals with worn straps",
        "Ox-hide whip (transforms into a long braided Lash of Solar Fire when channeled — bright, hot, almost too luminous to look at directly)",
        "Hesitant, humble, fierce, awakening, resolute",
        "Power born of stone and sun",
        "Heightened English (mythic); young; transitions from fear to resolve over the episode",
        "Quiet hero finding his fire; humble laborer with hidden god-blood",
        "22",
        "Power source: solar magic via golden veins through forearm. Speaks the show's title-card line. Vanishes in golden vortex at episode end.",
        KHENSU_ITER1, KHENSU_ITER2, "Done", "", "",
    ],
    [
        "AHMOSE",
        "Captain of the Sun-Guard",
        "Battle commander / mentor-foil",
        "Mid-30s",
        "Male / he",
        "Ancient Egyptian",
        "6'1\" / 185cm",
        "Broad-shouldered, battle-worn, muscular; thick chest, broad neck; calloused hands; tan-line at biceps where armor sits",
        "Short, dark, military-cut; sweat-damp at temples; faint salt traces from desert wind",
        "Hard, dark brown; sun-deepened crow's feet; small lashes catching dust",
        "Old battle scars stretch across bare chest and arms — pale on bronzed skin, irregular healing lines, some raised keloid; dust caked into scar tissue; sun-deepened crow's feet; one nicked ear-tip; pore-visible weathered skin on cheekbones; salt-crystal residue at hairline",
        "White linen battle kilt — sharp ironed pleats, dust at the hem, rope ties at the waist; polished bronze chest plate with embossed sun-disc insignia, hammered finish, scratches and battle nicks; leopard cape from shoulders, fur slightly matted with travel dust, brass clasp at throat",
        "Bronze spear and curved bronze blade",
        "Disciplined, commanding, afraid, honor-bound, reverent",
        "Order against chaos",
        "Heightened English (mythic); commanding when leading; wavers in private moments",
        "Battle-worn, deeply afraid, ready to die for the sacred shrine; pious devotion to Ma'at",
        "15",
        "Wields Ma'at conjuring magic ('Ma'at, bring justice and order. Bind this chaos!'). Saved by Khensu in the finale; first to recognize him as god-touched.",
        "", "", "Pending", "", "",
    ],
    [
        "TEHUTI",
        "The Old Surveyor",
        "Mentor / oracle (calculator of fate)",
        "Late 60s",
        "Male / he",
        "Ancient Egyptian",
        "5'8\" / 173cm (slightly stooped)",
        "Gaunt, frail, parchment-skin; thin shoulders; bony wrists; arthritic knuckles",
        "White, sparse, wisps; receding hairline; uneven length; wind-blown",
        "Left eye clouded (cataract); right eye sharp, calculating; rheumy lower lids; visible iris detail in the right eye",
        "Clouded left eye (full cataract); skin like dried parchment with deep creases at mouth and forehead; age spots scattered on temples and hands; gnarled arthritic knuckles; thin papery skin; pore-visible weathering on cheekbones; faint white stubble at chin",
        "Weathered linen robe in layered desert tones (sand, ochre, dusty rose) — heavy hand-spun thread, frayed seams, dust-coated hem, faint ink stains at the cuffs from scrolls; rope belt; bare feet in worn leather sandals",
        "Carved measuring staff with surveyor's notches",
        "Calculating, certain, oracular, patient, knowing",
        "Calculator of fate",
        "Heightened English (mythic); low and certain; prophet-like cadence",
        "Quiet authority; prophetic stillness; calmness in the eye of catastrophe",
        "24",
        "Gives Khensu the call to action. Mentor archetype paired with Seshet. Calculates fate of the world even in mid-battle.",
        "", "", "Pending", "", "",
    ],
    [
        "SESHET",
        "The Priestess",
        "Mystic / oracle (keeper of first light)",
        "Early 50s",
        "Female / she",
        "Ancient Egyptian",
        "5'7\" / 170cm",
        "Slim, poised, regal; long neck; fine bone structure; smooth posture",
        "Concealed under priestly veil; one glimpse of dark, oiled hair beneath; smooth temples",
        "Dark, calm, knowing; visible iris flecks; fine kohl line at the lash base, applied by hand (uneven in a human way)",
        "Thin priestly veil drifts across her face in desert wind; otherworldly poise; faint sun-warming on cheekbones; smooth pore-visible skin without retouch; subtle laugh-lines at the eyes; small mole near the lip",
        "Flowing caftan in muted desert tones (dusty rose, ochre, faded gold) — fine woven linen with subtle weave texture, layered drape, brass thread embroidery at the cuffs; thin priestly veil — sheer, drifts in the breeze; brass amulet at the throat",
        "The veil itself (no carried prop)",
        "Composed, mysterious, serene, knowing, otherworldly",
        "Keeper of first light",
        "Heightened English (mythic); low and serene; oracular",
        "Mystical; oracular; calm; otherworldly grace",
        "25",
        "Speaks the awakening line: 'You carry the power of the first light.' Pairs with Tehuti as the mentor duo.",
        "", "", "Pending", "", "",
    ],
    [
        "MERCHANT",
        "Bazaar Trader",
        "Background bazaar (one-line speaking)",
        "40s",
        "Male / he",
        "Ancient Egyptian",
        "5'8\" / 173cm",
        "Wiry, weathered, lean; ropy forearms; slight pot-belly from middle age",
        "Salt-and-pepper, short; thinning at crown; dust-coated",
        "Brown; deep crow's feet; sun-bleached lashes",
        "Sun-darkened skin with visible pores; dust streaked across forehead and neck; weathered hands with cracked knuckles; salt residue on temple hairline; calluses on palms from heavy goods",
        "Sun-bleached linen wrap (peasant) — frayed at the hem, faded ochre, dust-stained; rope belt; bare feet in old leather sandals",
        "Salted fish (the wares he hawks)",
        "Animated, weary, transactional, vocal",
        "Everyday life before the storm",
        "Heightened English (mythic); shouting cadence; market din",
        "Animated; ordinary; the human texture before the apocalypse",
        "4",
        "One line of dialogue: 'Salted fish! Best in the kingdom!' Establishes the everyday baseline that the Spawn shatters.",
        "", "", "Pending", "", "",
    ],
    [
        "ISFET SPAWN",
        "Spawn of Apep",
        "Monster antagonist",
        "N/A (timeless creature)",
        "N/A (creature)",
        "Mythological — born of Apep, god of chaos",
        "60 feet long (massive)",
        "Massive scorpion-like body; segmented; armored",
        "N/A",
        "Multiple compound eyes (insectoid, alien)",
        "Obsidian-black shell with jagged armored plates and oily sheen reflecting sunlight; yellow bile drips from twitching mandibles, sizzles and smokes on contact with sand; massive pincers; towering stinger that briefly eclipses the sun",
        "(creature) — natural armor of obsidian-black plates",
        "Stinger (towering above its body, briefly eclipses the sun); pincers; tiny scorpion swarm released from cracked shell",
        "Predatory, primal, malicious, ancient",
        "Chaos incarnate",
        "N/A — monstrous shrieks and toxic-steam hisses only",
        "Apocalyptic; nightmare; the desert turned hostile",
        "8",
        "Spawn of Apep. Releases tiny scorpion swarm when shell cracks. Killed by Khensu's solar whip + golden vortex. Dissolves into drifting sand at end of episode.",
        "", "", "Pending", "", "",
    ],
    [
        "TINY SCORPIONS",
        "Swarm of Apep",
        "Swarm spawn (creature)",
        "N/A (timeless creature)",
        "N/A (creature)",
        "Mythological",
        "1 inch each (swarm of hundreds)",
        "Insect-small, glistening, hive",
        "N/A",
        "Multiple compound eyes per scorpion",
        "Glistening like shards of wet obsidian; move as a dense, fast-moving black wave; tiny stingers",
        "(creature) — wet-obsidian carapace",
        "Tiny stingers (deployed in mid-leap at Ahmose's throat)",
        "Hive-mind, predatory, swarming",
        "Death by a thousand cuts",
        "N/A — skittering swarm sound",
        "Skittering nightmare horde; the swarm beneath the armor",
        "47",
        "Released from Spawn's broken shell. Frozen and shattered by black frost from Khensu's whip strike.",
        "", "", "Pending", "", "",
    ],
]


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")

    # Delete existing CHARACTERS tab if present
    existing = next((w for w in sh.worksheets() if w.title == "CHARACTERS"), None)
    if existing:
        sh.del_worksheet(existing)
        print(f"  removed existing CHARACTERS tab")

    # Create fresh with new schema
    ws = sh.add_worksheet(title="CHARACTERS", rows=len(CHARACTERS) + 5, cols=len(CHARACTERS_HEADERS))

    # Last column letter for the 22-col schema = V
    last_col = chr(ord("A") + len(CHARACTERS_HEADERS) - 1)
    ws.update(range_name=f"A1:{last_col}1", values=[CHARACTERS_HEADERS])
    ws.update(
        range_name=f"A2:{last_col}{len(CHARACTERS) + 1}",
        values=CHARACTERS,
        value_input_option="USER_ENTERED",
    )

    # Freeze header
    sh.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        }]
    })

    # Hide just Status (V, idx 21) and Error (W, idx 22). Iter 1 URL (T) and
    # Iter 2 URL (U) stay visible so the team can click straight to the refs.
    sh.batch_update({
        "requests": [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": 21,  # column V (Status)
                        "endIndex": 23,    # through W (Error)
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            },
        ]
    })

    print(f"  ✓ CHARACTERS rebuilt: {len(CHARACTERS_HEADERS)} cols × {len(CHARACTERS)} rows")
    print(f"  Iter 1 URL (T) + Iter 2 URL (U) visible; Status + Error hidden")
    print(f"  Speech accent preserved at column P")
    print(f"  KHENSU pre-populated with existing iter URLs, status=Done")


if __name__ == "__main__":
    main()
