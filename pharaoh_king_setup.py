#!/usr/bin/env python3
"""
End-to-end setup for Strike! Pharaoh King — Episode 1.

Creates:
  1. New Drive folder "Strike! Pharaoh King" in user's root
  2. New Google Sheet "Ep 1 - The Isfet Spawn (v2.2)" inside that folder
  3. Shotlist tab "Strike! Pharaoh King - Ep 1" with the v2.2 schema
  4. ~80 atomized rows from the script
  5. Live Prompt formula (P) and Bahasa Prompt formula (Q)
  6. Beat color fills on N column

Run once. Prints the new sheet ID at the end so we can chain
storyboard_build.py and storyboard_generate.py.
"""
from __future__ import annotations

import gspread
from googleapiclient.discovery import build

from auth import get_credentials


# v2.2 Prompt formula assembled inline so we don't depend on storyboard_build
def prompt_formula(r: int) -> str:
    return (
        f'="No music. Dialogue in "&H{r}&" accent."&CHAR(10)'
        f'&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
        f'&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))'
        f'&IF(J{r}="",".", ", "&J{r}&".")'
    )


def bahasa_formula(r: int) -> str:
    return f'=GOOGLETRANSLATE(P{r},"en","id")'


HEADERS = [
    "Shot #", "Duration (s)", "Shot Type", "Camera Movement", "Merge Candidate",
    "Shot Description", "Dialogue/VO", "Accent", "Microexpression", "SFX",
    "Props/Wardrobe", "Brand Integration", "Transition", "Beat",
    "English Translation", "Prompt", "Bahasa Prompt",
]

ACC = "Heightened English (mythic)"

# 84 atomized rows — Strike! Pharaoh King — Ep 1
# Tuple order matches HEADERS A–O (P and Q are added separately as formulas)
SHOTS = [
    # === HOOK: Bazaar peace then disturbance ===
    (1, 3, "WS", "Static", "",
     "Wide of bustling desert bazaar at midday — narrow aisles, faded cloth canopies, merchants haggling.",
     "", ACC, "", "Crowd ambience; goats bleating; merchant calls",
     "Faded cloth canopies; copper trinkets", "", "Cut", "HOOK", ""),
    (2, 3, "Insert", "Pan R", "",
     "Insert of merchant hands waving copper trinkets and dyed fabrics.",
     "", ACC, "", "Trinket clinks; cloth flutter",
     "Copper trinkets; dyed fabric", "", "Cut", "HOOK", ""),
    (3, 3, "Insert", "Static", "",
     "Insert of goats weaving between sand-caked sandals.",
     "", ACC, "", "Goat hooves on sand",
     "Goats; sand-caked sandals", "", "Cut", "HOOK", ""),
    (4, 3, "CU", "Static", "",
     "Close-up of merchant face mid-shout — sun-bleached linen wrap.",
     "MERCHANT: Salted fish! Best in the kingdom!", ACC,
     "Mouth open mid-call; sweat on brow", "Merchant shouts; market din",
     "Sun-bleached linen wrap", "", "Cut", "HOOK", ""),
    (5, 3, "WS", "Handheld", "",
     "Wide of bazaar floor — packed sand begins to swell in rolling waves underfoot.",
     "", ACC, "", "Low rumbling subterranean groan",
     "Packed sand floor; market stalls", "", "Cut", "HOOK", ""),
    (6, 3, "CU", "Handheld", "",
     "Close-up of merchant eyes going wide — confusion turning to dread.",
     "", ACC, "Brows knit; eyes widen; breath catches",
     "Earth groan continues",
     "Merchant face streaked with dust", "", "Cut", "HOOK", ""),

    # === JOLT 1: The Isfet Spawn reveal ===
    (7, 4, "WS", "Handheld", "",
     "Wide of sand erupting upward in violent bursts — whipping through narrow lanes, swallowing the market in dust.",
     "", ACC, "", "Sand explosion roar; people screaming",
     "Sand cloud; collapsing canopies", "", "Smash Cut", "JOLT 1", ""),
    (8, 4, "WS", "Static", "",
     "Wide of ISFET SPAWN bursting from sand — sixty-foot scorpion, obsidian-black shell gleaming.",
     "", ACC, "", "Monstrous shriek; sand cascading",
     "Isfet Spawn body; obsidian shell plates", "", "Cut", "JOLT 1", ""),
    (9, 3, "Insert", "Tilt U", "",
     "Insert tilting up the Isfet Spawn's jagged armored plates — oily sheen reflecting sunlight.",
     "", ACC, "", "Armor creaking; deep breath rumble",
     "Obsidian armor plates", "", "Cut", "JOLT 1", ""),
    (10, 3, "Insert", "Static", "",
     "Insert of yellow bile dripping from twitching mandibles — sizzles and smokes on contact with sand.",
     "", ACC, "", "Sizzling acid hiss",
     "Yellow bile; mandibles", "", "Cut", "JOLT 1", ""),
    (11, 3, "Insert", "Tilt U", "",
     "Insert of one enormous pincer raising high overhead.",
     "", ACC, "", "Carapace creak; pincer rising whoosh",
     "Pincer; sky behind", "", "Cut", "JOLT 1", ""),
    (12, 4, "WS", "Static", "",
     "Wide of pincer slamming shut on a brick dwelling — stone explodes outward in a shower of debris.",
     "", ACC, "", "Brick explosion; dust roar; people screaming",
     "Pincer; collapsing brick dwelling", "", "Smash Cut", "JOLT 1", ""),

    # === BRIDGE: Sun-Guard establish ===
    (13, 4, "WS", "Pan L", "",
     "Wide pan revealing the half-finished Great Pyramid — pale limestone glowing under the sun.",
     "", ACC, "", "Wind sweeping over desert; distant battle",
     "Great Pyramid limestone blocks; sand plateau", "", "Cut", "", ""),
    (14, 3, "WS", "Static", "",
     "Wide of the Pharaoh's Sun-Guard arrayed in formation — thousands of soldiers in white linen kilts and bronze chest plates.",
     "", ACC, "", "Marching feet on sand; spear butts striking ground in unison",
     "Sun-Guard formation; bronze plates; sun-disc insignias", "", "Cut", "", ""),
    (15, 3, "CU", "Static", "",
     "Close-up of AHMOSE's face — battle-worn, scars across chest, leopard cape on shoulders.",
     "", ACC, "Jaw clenched; eyes hard but afraid", "Wind through leopard cape; quiet breath",
     "Leopard cape; scarred chest; bronze chest plate", "", "Cut", "", ""),
    (16, 3, "CU", "Static", "",
     "Close-up of Ahmose under his breath — dread settling.",
     "AHMOSE: The Isfet Spawn... Apep has declared war on all that is good.",
     ACC, "Eyes narrow; lips barely move", "Quiet whisper; battle in distance",
     "Ahmose's profile", "", "Cut", "", ""),
    (17, 3, "MCU", "Tilt U", "",
     "Medium close-up tilting up as Ahmose lifts his spear high for all to see.",
     "", ACC, "Determination overrides fear", "Spear haft creaking; cape snapping in wind",
     "Bronze spear; leopard cape", "", "Cut", "", ""),
    (18, 3, "CU", "Static", "",
     "Close-up of Ahmose shouting orders.",
     "AHMOSE: Hold the line! Protect the sacred shrine!",
     ACC, "Mouth wide; cords stand on neck", "Battle cry; spear butts hitting ground in response",
     "Ahmose's face", "", "Cut", "", ""),
    (19, 4, "WS", "Tracking", "",
     "Wide tracking the Sun-Guard surging forward toward the beast in unison.",
     "", ACC, "", "Battle cries; pounding feet on sand",
     "Sun-Guard ranks; bronze blades raised", "", "Cut", "", ""),
    (20, 3, "Insert", "Static", "",
     "Insert of bronze spears striking the Isfet Spawn's shell — spear shafts snap on impact.",
     "", ACC, "", "Bronze spear shafts snapping; shell ringing",
     "Bronze spears; obsidian shell", "", "Cut", "", ""),
    (21, 3, "WS", "Tracking", "",
     "Wide of war chariot smashed aside by the Spawn's pincer — wood splinters, horse falls.",
     "", ACC, "", "Chariot splintering; horse whinny; soldier scream",
     "War chariot wreckage; horse tack", "", "Cut", "", ""),

    # === BRIDGE: Rooftop — Khensu's choice ===
    (22, 3, "WS", "Static", "",
     "Wide rooftop establishing — KHENSU stands on flat mud-brick rooftop above the chaos below.",
     "", ACC, "", "Distant battle muffled; wind on roof",
     "Mud-brick rooftop; Khensu's torn linen loincloth", "", "Cut", "", ""),
    (23, 3, "CU", "Static", "",
     "Close-up of KHENSU watching the slaughter — sweat and dust cling to his bronze skin.",
     "", ACC, "Jaw set; eyes haunted", "Distant battle ambience",
     "Khensu's bronze skin; torn loincloth", "", "Cut", "", ""),
    (24, 3, "CU", "Static", "",
     "Close-up of TEHUTI — gaunt old surveyor, one clouded eye, skin like dried parchment.",
     "", ACC, "One clouded eye fixed on Khensu; the other lined with calculation",
     "Wind through cloak", "Carved measuring staff; weathered linen robe", "", "Cut", "", ""),
    (25, 3, "CU", "Static", "",
     "Close-up of SESHET — composed and mysterious, flowing caftan and thin veil moving in desert wind.",
     "", ACC, "Eyes calm and knowing; veil drifts across her face",
     "Veil whisper in wind", "Flowing caftan; thin priestly veil", "", "Cut", "", ""),
    (26, 4, "MCU", "Static", "",
     "Medium close-up of Tehuti speaking to Khensu.",
     "TEHUTI: Khensu. It's time. You must destroy it.",
     ACC, "Jaw firm; voice low and certain", "Distant rumble of battle",
     "Tehuti's measuring staff", "", "Cut", "", ""),
    (27, 3, "CU", "Static",
     "Merge w/ 26; OTS push-in from Tehuti's shoulder onto Khensu's reaction.",
     "Close-up of Khensu pushing back.",
     "KHENSU: Me? If the Sun-Guard can't stop it, how can I?",
     ACC, "Brows draw together; fear flashes", "Battle ambience",
     "Khensu's profile", "", "Cut", "", ""),
    (28, 4, "CU", "Static", "",
     "Close-up of Tehuti with quiet authority.",
     "TEHUTI: Defeat the Isfet Spawn... and you can finally go home.",
     ACC, "Faintest smile crinkles around the clouded eye", "Wind drops to silence",
     "Tehuti's clouded eye lit", "", "Cut", "", ""),
    (29, 3, "CU", "Static", "",
     "Close-up of Khensu in doubt.",
     "KHENSU: But I'm just a stonecutter. I'm not ready.",
     ACC, "Eyes drop; swallow hard", "Distant scream from below",
     "Khensu's face", "", "Cut", "", ""),
    (30, 4, "CU", "Rack Focus",
     "Merge w/ 29; rack focus from Khensu's downcast face to Seshet behind him.",
     "Close-up rack to Seshet — quiet certainty.",
     "SESHET: After all this time, have you forgotten? You carry the power of the first light.",
     ACC, "Eyes serene; voice low", "Wind picks up under her words",
     "Seshet's veil; flowing caftan", "", "Cut", "", ""),
    (31, 3, "CU", "Static", "",
     "Close-up of Khensu — fear hardening into resolve.",
     "KHENSU: Then fight I must.",
     ACC, "Jaw sets; fear gives way to fire", "Khensu's breath steadies",
     "Khensu's eyes blazing with new resolve", "", "Smash Cut", "JOLT 2", ""),

    # === JOLT 2: Khensu's leap and parkour descent ===
    (32, 4, "WS", "Tracking", "",
     "Wide tracking Khensu leaping from the rooftop into open air — body falls fast through blazing sky.",
     "", ACC, "", "Whoosh of body through air; cloth snapping",
     "Khensu's torn loincloth; rooftop edge", "", "Cut", "JOLT 2", ""),
    (33, 3, "Insert", "Static", "",
     "Insert of Khensu's foot landing on a collapsed fruit cart — vaulting off it.",
     "", ACC, "", "Wood crack; foot impact",
     "Collapsed fruit cart; figs and pomegranates", "", "Cut", "", ""),
    (34, 3, "Insert", "Handheld", "",
     "Insert of Khensu's hand and foot planting against a limestone wall mid-leap.",
     "", ACC, "", "Wall scrape; breath out",
     "Limestone wall; bronze skin", "", "Cut", "", ""),
    (35, 3, "MS", "Handheld",
     "Merge w/ 34; handheld continuous from wall plant into a tight spinning twist beneath a swinging clay awning.",
     "Medium of Khensu spinning to dodge a swinging clay awning that breaks loose overhead.",
     "", ACC, "Eyes locked on landing point", "Awning rope snap; clay shatter",
     "Clay awning; rope ties", "", "Cut", "", ""),
    (36, 3, "Insert", "Tracking", "",
     "Insert of Khensu hitting a wooden balcony rail and sliding the length of it in a shower of dust and splinters.",
     "", ACC, "", "Wood splinter scrape; dust whoosh",
     "Wooden balcony rail; splinters", "", "Cut", "", ""),
    (37, 3, "WS", "Static", "",
     "Wide of Khensu dropping from the balcony — clearing a crowd of terrified merchants below who scatter aside.",
     "", ACC, "", "Crowd gasps; feet on sand",
     "Crowd of merchants; sand street", "", "Cut", "", ""),

    # === BRIDGE: Front line collapses, archers form up ===
    (38, 3, "WS", "Static", "",
     "Wide of the front line collapsed — shattered spears and overturned bodies scattered across the sand.",
     "", ACC, "", "Wind through battlefield; distant moans",
     "Shattered bronze spears; bodies in sand", "", "Cut", "", ""),
    (39, 3, "MCU", "Static", "",
     "Medium close-up of Ahmose retreating with surviving Sun-Guard toward base of pyramid.",
     "", ACC, "Sweat and blood on brow; jaw clenched", "Retreating footfalls; orders shouted",
     "Ahmose's bronze plate; shield", "", "Cut", "", ""),
    (40, 4, "WS", "Tracking", "",
     "Wide of archers in war chariots rolling into formation — wheels grinding deep into the sand.",
     "", ACC, "", "Wheel grind on sand; horses snorting",
     "War chariots; archer formation", "", "Cut", "", ""),
    (41, 3, "CU", "Static", "",
     "Close-up of Ahmose's face — calculating the volley.",
     "AHMOSE: Ready...", ACC, "Eyes narrow; brow furrows in command",
     "Bowstrings drawing taut", "Ahmose's face", "", "Cut", "", ""),
    (42, 3, "WS", "Tilt U", "",
     "Wide tilt up as hundreds of bows rise in unison against the sun.",
     "", ACC, "", "Bows creaking taut in unison",
     "Bow ranks; sky", "", "Cut", "", ""),
    (43, 3, "CU", "Static",
     "Merge w/ 42; rack focus from raised bows to Ahmose mid-command.",
     "Close-up of Ahmose shouting fire command.",
     "AHMOSE: FIRE!", ACC, "Mouth wide; command cry from the gut",
     "Battle cry; bowstring release thunderclap", "Ahmose's face", "", "Cut", "", ""),
    (44, 3, "WS", "Tracking", "",
     "Wide of arrows rising into the sky — arrowheads igniting with magical fire glowing gold and red.",
     "", ACC, "", "Whoosh of mass arrow flight; magical fire whoosh",
     "Arrow shafts; magical flame arrowheads", "", "Cut", "", ""),
    (45, 3, "WS", "Tracking", "",
     "Wide of arrow volley arcing downward and slamming into the Spawn's shell — fire bursts across its body.",
     "", ACC, "", "Arrow impact thunder; fire bloom",
     "Spawn shell; fire bursts", "", "Cut", "", ""),
    (46, 3, "Insert", "Dolly In", "",
     "Insert dolly in on cracks spreading through the obsidian armor — red glow pulsing beneath broken plates.",
     "", ACC, "", "Shell cracking like lava stone; deep pulse",
     "Obsidian armor; red inner glow", "", "Cut", "", ""),

    # === JOLT 3: Tiny scorpion swarm ===
    (47, 4, "WS", "Static", "",
     "Wide of the Spawn's shell splitting open — TINY SCORPIONS pour out in a fast-moving black wave.",
     "", ACC, "", "Skittering swarm; shell rupture",
     "Tiny scorpions; obsidian shell breach", "", "Smash Cut", "JOLT 3", ""),
    (48, 3, "WS", "Tracking", "",
     "Wide of the swarm racing across the battlefield — climbing over shields and broken spears.",
     "", ACC, "", "Skittering scorpion swarm; soldiers shouting",
     "Tiny scorpions; shields and spears in sand", "", "Cut", "JOLT 3", ""),
    (49, 3, "Insert", "Handheld", "",
     "Insert of tiny scorpions crawling beneath a soldier's armor — into mouth and ears.",
     "", ACC, "", "Skittering on metal; muffled scream",
     "Bronze armor; sand-caked soldier", "", "Cut", "JOLT 3", ""),
    (50, 3, "CU", "Handheld", "",
     "Close-up of soldier's face mid-scream — eyes wide, jaw rigid.",
     "", ACC, "Eyes blow wide; jaw rigid in horror", "Anguished scream",
     "Soldier's face; bronze helm", "", "Cut", "JOLT 3", ""),
    (51, 3, "WS", "Static", "",
     "Wide of soldiers collapsing into the sand as the swarm engulfs them.",
     "", ACC, "", "Falling armor crashes; muffled screams",
     "Soldiers' bodies; bronze armor", "", "Cut", "JOLT 3", ""),
    (52, 4, "CU", "Static", "",
     "Close-up of Ahmose stunned by the scale of the loss.",
     "AHMOSE: Only the gods can save us now.",
     ACC, "Eyes hollowed; mouth slack", "Wind across battlefield; quiet breath",
     "Ahmose's bloodied face", "", "Cut", "", ""),

    # === BRIDGE: Khensu transforms whip ===
    (53, 3, "WS", "Static", "",
     "Wide of Khensu landing hard and rolling across the sand — coming up on one knee near a fallen supply cart.",
     "", ACC, "", "Body impact; sand whoosh",
     "Supply cart wreckage; broken oxen yoke", "", "Cut", "", ""),
    (54, 3, "Insert", "Static", "",
     "Insert of half-buried OX-HIDE WHIP beneath the wreckage — thick and worn from labor use.",
     "", ACC, "", "Wood creak as cart shifts",
     "Ox-hide whip; broken wood", "", "Cut", "", ""),
    (55, 3, "Insert", "Static", "",
     "Insert of Khensu's hand grabbing the whip and yanking it free.",
     "", ACC, "", "Whip leather scrape; sand sliding",
     "Ox-hide whip; Khensu's hand", "", "Cut", "", ""),
    (56, 3, "Insert", "Tilt D",
     "Merge w/ 55; tilt down following the whip to Khensu's other hand slamming into the ground.",
     "Insert of Khensu's free hand slamming flat into the desert ground.",
     "", ACC, "", "Hand impact thump; sand displacement",
     "Desert ground; Khensu's palm", "", "Cut", "", ""),
    (57, 3, "Insert", "Tilt U", "",
     "Insert tilting up the golden veins of light racing from the earth over Khensu's fingers, wrist, and forearm.",
     "", ACC, "", "Magical hum rising; energy crackle",
     "Golden light veins; Khensu's bronze skin", "", "Cut", "", ""),
    (58, 4, "WS", "Static", "",
     "Wide of Khensu rising — the leather whip transformed into a long braided LASH OF SOLAR FIRE, bright and luminous.",
     "", ACC, "", "Solar fire whoosh; deep magical bass",
     "Lash of Solar Fire; Khensu's stance", "", "Cut", "", ""),

    # === BRIDGE: Spawn rises, Ma'at fails ===
    (59, 4, "WS", "Tilt U", "",
     "Wide tilt up as the Isfet Spawn rises higher and higher out of the sand — towering over the battlefield.",
     "", ACC, "", "Sand cascading; monstrous breath",
     "Spawn body rising; sand falling away", "", "Cut", "", ""),
    (60, 3, "Insert", "Tilt U", "",
     "Insert tilting up the Spawn's enormous stinger curling above its body.",
     "", ACC, "", "Carapace creak; stinger rising",
     "Stinger; Spawn body", "", "Cut", "", ""),
    (61, 4, "WS", "Static", "",
     "Wide of the death-shadow spilling across the pyramid and the soldiers beneath it — sun briefly eclipsed.",
     "", ACC, "", "Sun-flare drop; ominous bass",
     "Pyramid limestone; long Spawn shadow", "", "Cut", "", ""),
    (62, 3, "WS", "Static", "",
     "Wide of Ahmose standing alone in the open before the Spawn.",
     "", ACC, "", "Wind sweeping; quiet breath",
     "Ahmose alone; sand around him", "", "Cut", "", ""),
    (63, 4, "CU", "Static", "",
     "Close-up of Ahmose conjuring — eyes closed in invocation.",
     "AHMOSE: Ma'at, bring justice and order. Bind this chaos!",
     ACC, "Eyes squeezed shut; breath held", "Whispered conjuring; magical hum",
     "Ahmose's face; lifted hand", "", "Cut", "", ""),
    (64, 4, "WS", "Tracking", "",
     "Wide of a massive WALL OF SAND erupting from the desert floor — swirling up in a perfect ring around the Spawn.",
     "", ACC, "", "Sand wall whoosh; magical bass",
     "Sand wall ring; Spawn within", "", "Cut", "", ""),
    (65, 3, "Insert", "Static",
     "Merge w/ 64; dolly out as the pincer slams the wall and sand explodes outward.",
     "Insert of pincer slamming sand wall — barrier breaks apart in a violent burst.",
     "", ACC, "", "Sand wall shatter; pincer impact",
     "Sand wall fracturing; pincer", "", "Cut", "", ""),

    # === JOLT 4: Mini-scorpions leap at Ahmose's throat ===
    (66, 4, "WS", "Static", "",
     "Wide of a dozen mini-scorpions leaping into the air — stingers aimed straight at Ahmose's throat.",
     "", ACC, "", "Skittering leap; stinger whistle",
     "Mini-scorpions mid-leap; Ahmose's bare neck", "", "Smash Cut", "JOLT 4", ""),

    # === BRIDGE: Khensu's awakening in the crater ===
    (67, 3, "WS", "Static", "",
     "Wide of Khensu in a crater of broken stone and dust — half-buried, struggling to breathe, solar whip dark.",
     "", ACC, "", "Dust falling; rasping breath",
     "Crater rubble; Khensu's body; darkened whip", "", "Cut", "", ""),
    (68, 3, "CU", "Rack Focus", "",
     "Close-up rack focus from Khensu's blurred vision to the frozen scorpions inches from Ahmose.",
     "", ACC, "Eyes refocus; pupils sharpen", "Heart-beat thump; rising tone",
     "Khensu's blurred POV; scorpions in air", "", "Cut", "", ""),
    (69, 3, "CU", "Static", "",
     "Close-up of Khensu — eyes sharpen, surge of determination takes hold.",
     "", ACC, "Eyes hard; breath quickens; fists clench", "Magical hum building",
     "Khensu's face; veins on neck", "", "Cut", "", ""),
    (70, 4, "CU", "Tilt U", "",
     "Close-up tilting up as Khensu lets out a raw roar — golden light explodes back through the veins in his arm.",
     "", ACC, "Mouth open in a roar of pain, fear, and resolve",
     "Roar of fury; magical light surge",
     "Khensu's open mouth; golden veins blazing", "", "Cut", "", ""),

    # === BRIDGE → CLIFF SETUP: The whip strike ===
    (71, 4, "WS", "Tracking", "",
     "Wide of the WHIP OF LIGHT lashing across the battlefield like a bolt of living sunfire.",
     "", ACC, "", "Whip crack like thunder; solar fire roar",
     "Lash of Solar Fire; battlefield", "", "Cut", "", ""),
    (72, 3, "Insert", "Tracking", "",
     "Insert of the whip wrapping around the Spawn's colossal stinger.",
     "", ACC, "", "Whip coiling; stinger creak",
     "Whip; stinger", "", "Cut", "", ""),
    (73, 3, "MCU", "Static", "",
     "Medium close-up of Khensu planting his feet and straining with everything he has.",
     "", ACC, "Teeth bared; cords stand on neck", "Strain breath; whip taut creak",
     "Khensu's bronze legs; sand beneath", "", "Cut", "", ""),
    (74, 3, "Insert", "Tracking", "",
     "Insert of the giant stinger snapping under Khensu's yank — CRACK.",
     "", ACC, "", "CRACK of bone-like exoskeleton; whip recoil",
     "Stinger snapping; chitin shards", "", "Smash Cut", "", ""),
    (75, 3, "Insert", "Static", "",
     "Insert of mini-scorpions freezing in mid-leap inches from Ahmose — black frost spreads over their bodies.",
     "", ACC, "", "Frost creep; deep bass freeze",
     "Mini-scorpions; black frost", "", "Cut", "", ""),
    (76, 3, "Insert", "Static", "",
     "Insert of frozen mini-scorpions hardening to brittle black glass and shattering against Ahmose's armor.",
     "", ACC, "", "Glass shatter cascade",
     "Black glass shards; bronze armor", "", "Cut", "", ""),
    (77, 4, "WS", "Static", "",
     "Wide of silence falling — Ahmose gasping for breath, staring across the battlefield.",
     "", ACC, "Eyes wide; chest heaving", "Silence then quiet wind",
     "Ahmose's bronze plate; battlefield ruin", "", "Cut", "", ""),
    (78, 4, "WS", "Tracking", "",
     "Wide of the Isfet Spawn drying, withering, and breaking apart — dissolving into a mountain of drifting sand.",
     "", ACC, "", "Sand cascade; carapace cracking; deep dry rasp",
     "Spawn dissolving; drifting sand", "", "Cut", "", ""),

    # === CLIFF SETUP / CLIFF ===
    (79, 4, "CU", "Static", "",
     "Close-up of Ahmose slowly rising — staring into the settling dust.",
     "AHMOSE: Who... what are you?",
     ACC, "Mouth slack; eyes locked on the distant figure",
     "Quiet wind; Ahmose's breath",
     "Ahmose's bloodied face; leopard cape", "", "Cut", "CLIFF SETUP", ""),
    (80, 3, "WS", "Tracking", "",
     "Wide of Ahmose running through the settling dust toward Khensu.",
     "", ACC, "", "Footfalls on sand; dust whoosh",
     "Ahmose's leopard cape; settling dust", "", "Cut", "CLIFF SETUP", ""),
    (81, 3, "CU", "Static", "",
     "Close-up of Khensu — his glowing whip slips from his hand.",
     "", ACC, "Quiet exhale; eyes faraway",
     "Whip drops with soft thump; magical hum fades",
     "Lash of Solar Fire; bronze hand", "", "Cut", "CLIFF", ""),
    (82, 4, "WS", "Tilt U", "",
     "Wide tilt up as the blazing desert sun erupts into a brilliant golden flare — swirling vortex of light around Khensu's silhouette.",
     "", ACC, "", "Solar vortex roar rising to silence",
     "Golden vortex; Khensu silhouette; pyramid backdrop", "", "Fade to Black", "CLIFF", ""),
]

# Beat color hex map
BEAT_COLORS = {
    "HOOK": "#FCD34D",
    "JOLT 1": "#93C5FD",
    "JOLT 2": "#93C5FD",
    "JOLT 3": "#93C5FD",
    "JOLT 4": "#93C5FD",
    "CLIFF SETUP": "#FECACA",
    "CLIFF TAG": "#FECACA",
    "CLIFF": "#FCA5A5",
    "PAYOFF": "#A7F3D0",
    "FLASHBACK": "#DDD6FE",
    "BRIDGE": "#E5E7EB",
}


def hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)

    # Step 1: Create a folder for the show in user's root
    folder_meta = drive.files().create(
        body={
            "name": "Strike! Pharaoh King",
            "mimeType": "application/vnd.google-apps.folder",
        },
        fields="id,name,webViewLink",
    ).execute()
    folder_id = folder_meta["id"]
    print(f"[1/5] Created folder: {folder_meta['name']} ({folder_id})")

    # Step 2: Create a new spreadsheet inside that folder
    sheet_meta = drive.files().create(
        body={
            "name": "Ep 1 - The Isfet Spawn (v2.2)",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id],
        },
        fields="id,name,webViewLink",
    ).execute()
    sheet_id = sheet_meta["id"]
    sheet_url = sheet_meta["webViewLink"]
    print(f"[2/5] Created sheet: {sheet_meta['name']} ({sheet_id})")

    # Step 3: Open and rename default tab
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheets()[0]
    ws.update_title("Strike! Pharaoh King - Ep 1")

    # Make sure we have at least 17 cols
    if ws.col_count < 17:
        ws.add_cols(17 - ws.col_count)

    # Step 4: Write headers + data
    ws.update(range_name="A1:Q1", values=[HEADERS])

    rows_data = []
    for shot in SHOTS:
        row = list(shot) + ["", ""]  # 15 source cols + P + Q placeholders
        rows_data.append(row)

    # Write A:O for all rows
    last_row = len(SHOTS) + 1
    a_to_o = [list(s) for s in SHOTS]  # 15 cols
    ws.update(
        range_name=f"A2:O{last_row}",
        values=a_to_o,
        value_input_option="USER_ENTERED",
    )

    # Step 5: Drop P + Q formulas per row
    p_formulas = [[prompt_formula(r)] for r in range(2, last_row + 1)]
    q_formulas = [[bahasa_formula(r)] for r in range(2, last_row + 1)]
    ws.update(
        range_name=f"P2:P{last_row}",
        values=p_formulas,
        value_input_option="USER_ENTERED",
    )
    ws.update(
        range_name=f"Q2:Q{last_row}",
        values=q_formulas,
        value_input_option="USER_ENTERED",
    )
    print(f"[3/5] Wrote {len(SHOTS)} rows + P/Q formulas")

    # Step 6: Apply beat colors on column N for non-empty beat rows
    requests = []
    for i, shot in enumerate(SHOTS):
        beat = shot[13]  # column N is index 13 in the tuple
        if not beat:
            continue
        color = BEAT_COLORS.get(beat)
        if not color:
            continue
        r, g, b = hex_to_rgb01(color)
        sheet_row = i + 1  # 0-based for API; row 0 is header, so data row 0 = sheet row 1 (which is row 2 in 1-based)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": sheet_row,
                    "endRowIndex": sheet_row + 1,
                    "startColumnIndex": 13,
                    "endColumnIndex": 14,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })
    if requests:
        sh.batch_update({"requests": requests})
    print(f"[4/5] Applied beat colors to {len(requests)} rows")

    # Step 7: Freeze header row + slight column width tweaks
    sh.batch_update({
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": ws.id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Hide column Q (Bahasa Prompt) by default
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": 16,
                        "endIndex": 17,
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            },
        ]
    })
    print(f"[5/5] Frozen header + hidden Bahasa column Q")

    print()
    print("=" * 60)
    print(f"DONE — sheet ready")
    print(f"  Sheet ID:  {sheet_id}")
    print(f"  Sheet URL: {sheet_url}")
    print(f"  Folder ID: {folder_id}")
    print(f"  Shots:     {len(SHOTS)}  →  Sets: {(len(SHOTS) + 4) // 5}")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  python3 storyboard_build.py --sheet {sheet_id}")
    print(f"  python3 storyboard_generate.py --sheet {sheet_id}")


if __name__ == "__main__":
    main()
