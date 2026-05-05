"""Smarter location detection — uses an alias map per Sajangnim location
because shot bodies describe action ("kitchen ambient, cutting board") and
rarely contain the canonical location name verbatim ("Hanbyeol Bistro Kitchen").

Re-populates col L on Storyboard Prompts for all 6 episodes. Also fixes any
"Unspecified" cells that the v1 pass left behind."""
import gspread, time
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]

# Alias map — canonical location → list of substrings (case-insensitive).
# Most-specific first since first-match-wins.
LOCATION_ALIASES = [
    ("Walk-In Cooler", [
        "walk-in cooler", "walk in cooler", "cooler", "freezer",
        "refrigerated", "stainless steel walls", "cold room",
    ]),
    ("Alley Behind Hanbyeol", [
        "alley behind hanbyeol", "back alley", "alley behind", "back-alley",
        "back of the bistro", "rear of hanbyeol", "service alley",
        "concrete back-alley",
    ]),
    ("Hanbyeol Dressing Room", [
        "dressing room", "locker room", "lockers", "changing room",
        "staff room", "uniforms hanging",
    ]),
    ("Hanbyeol Storage Room", [
        "storage room", "stockroom", "store room", "pantry",
        "dry storage", "shelves of",
    ]),
    ("Hanbyeol Pass Station", [
        "pass station", "the pass", "service window", "expo line",
        "expediter", "plating area", "ticket rail",
    ]),
    ("Joon-Ho's Office", [
        "joon-ho's office", "joon ho's office", "office", "manager's office",
        "behind a desk", "office desk", "owner's office",
    ]),
    ("Tara's Mampang Apartment", [
        "tara's mampang apartment", "mampang apartment", "mampang",
        "tara's apartment", "tara's room", "her apartment", "kost",
        "her bedroom", "studio apartment",
    ]),
    ("Hanbyeol Bistro Kitchen", [
        "hanbyeol bistro kitchen", "hanbyeol kitchen", "bistro kitchen",
        "kitchen line", "korean kitchen", "modern korean kitchen",
        "prep station", "cutting board", "induction burner", "kitchen ambient",
        "kitchen clatter", "stove hiss", "kitchen hum", "chef whites",
        "knife slice", "chef's knife", "kitchen tile", "knife thump",
        "cutting clove", "garlic", "chef line",
    ]),
]

def detect(body: str) -> str:
    bl = body.lower()
    for canonical, aliases in LOCATION_ALIASES:
        for a in aliases:
            if a in bl:
                return canonical
    return "Unspecified"


print("Cooling down for 75s before start...", flush=True)
time.sleep(75)

gc = gspread.authorize(get_credentials())

for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ({sid[:8]}...) ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        ws = sh.worksheet("Storyboard Prompts")
        time.sleep(3)
        body_rows = ws.get("J11:J50", value_render_option="FORMATTED_VALUE")
        time.sleep(3)
        detected = []
        last_with_data = 0
        for i, row in enumerate(body_rows):
            body = (row[0] if row else "")
            if body.strip():
                last_with_data = i + 1
            detected.append([detect(body)])
        if last_with_data > 0:
            ws.update(values=detected[:last_with_data],
                      range_name=f"L11:L{10+last_with_data}",
                      value_input_option="RAW")
            match = sum(1 for d in detected[:last_with_data] if d[0] != "Unspecified")
            unspec = last_with_data - match
            print(f"  L11:L{10+last_with_data}: {match} matched / {unspec} Unspecified", flush=True)
            for i, d in enumerate(detected[:last_with_data], start=11):
                print(f"    L{i}: {d[0]}", flush=True)
        time.sleep(15)
    except Exception as e:
        print(f"  ! error: {e}", flush=True)
        time.sleep(30)

print("\n✓ All 6 episodes done", flush=True)
