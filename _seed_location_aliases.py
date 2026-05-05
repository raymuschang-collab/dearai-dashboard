"""Add an `Aliases` column at LOCATIONS!O (header at O4, data O5+) and seed
canonical alias strings for Sajangnim and Pharaoh.

The LOCATIONS bible has multiple rows per location (one per shot size).
Aliases are written on the FIRST row of each location (the `wide` row).
Empty aliases on subsequent rows = inherit from the location's first row.

Format: semicolon-separated lowercase substrings. Most-specific first.

After this runs, refs_audit.py should be refactored to read aliases from the
bible instead of the hardcoded LOCATION_ALIASES list."""
import gspread, time
from auth import get_credentials

# (sheet_id, [(canonical_name, "alias1; alias2; alias3"), ...])
SHOWS = [
    ("1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc", "Sajangnim", [
        ("Hanbyeol Bistro Kitchen",
         "hanbyeol bistro kitchen; hanbyeol kitchen; bistro kitchen; "
         "korean kitchen; kitchen line; prep station; cutting board; "
         "induction burner; kitchen ambient; kitchen clatter; stove hiss; "
         "kitchen hum; chef's knife; chef whites; kitchen tile; "
         "knife thump; knife slice; knife slip; kitchen"),
        ("Hanbyeol Pass Station",
         "pass station; the pass; expo line; expediter; ticket rail; "
         "plating area"),
        ("Hanbyeol Dressing Room",
         "dressing room; locker room; changing room; staff room; "
         "uniforms hanging"),
        ("Hanbyeol Storage Room",
         "storage room; stockroom; store room; pantry; dry storage"),
        ("Walk-In Cooler",
         "walk-in cooler; walk in cooler; cold room; freezer"),
        ("Alley Behind Hanbyeol",
         "alley behind hanbyeol; back-alley; back alley; service alley; "
         "back of the bistro; rear of hanbyeol; concrete back-alley"),
        ("Joon-Ho's Office",
         "joon-ho's office; joon ho's office; 's office; "
         "behind the desk; office quiet; manager's office; owner's office"),
        ("Tara's Mampang Apartment",
         "tara's mampang apartment; mampang apartment; mampang; "
         "tara's apartment; tara's room; her apartment; her bedroom; "
         "kost; studio apartment"),
    ]),
    ("1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE", "Pharaoh", [
        ("Rooftop above the Bazaar", "rooftop above the bazaar; rooftop"),
        ("Peasant Bazaar", "peasant bazaar; bazaar; marketplace"),
        ("Pyramid Field (Battlefield)", "pyramid field; battlefield"),
        ("Base of the Pyramid", "base of the pyramid"),
        ("Desert Plateau / Great Pyramid",
         "desert plateau; great pyramid; pyramid"),
        ("Impact Crater", "impact crater; crater"),
    ]),
]

def col_letter(idx0: int) -> str:
    return chr(ord('A') + idx0) if idx0 < 26 else 'A' + chr(ord('A') + idx0 - 26)

print("Cool 60s for quota...", flush=True)
time.sleep(60)
gc = gspread.authorize(get_credentials())

ALIAS_COL_IDX = 14   # col O
ALIAS_COL = col_letter(ALIAS_COL_IDX)

for sid, show_name, aliases_by_name in SHOWS:
    print(f"\n=== {show_name} ({sid[:8]}…) ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        ws = sh.worksheet("LOCATIONS")
        time.sleep(3)

        # ensure col count >= 15
        if ws.col_count < ALIAS_COL_IDX + 1:
            ws.resize(rows=max(ws.row_count, 50),
                      cols=ALIAS_COL_IDX + 1)
            time.sleep(2)

        # header at row 4
        cur_hdr = ws.get(f"{ALIAS_COL}4", value_render_option="FORMATTED_VALUE")
        cur = (cur_hdr[0][0] if cur_hdr and cur_hdr[0] else "").strip()
        if cur != "Aliases":
            ws.update(values=[["Aliases"]], range_name=f"{ALIAS_COL}4",
                      value_input_option="RAW")
            print(f"  + {ALIAS_COL}4: 'Aliases'", flush=True)
            time.sleep(2)

        # find first row per canonical name
        all_rows = ws.get(f"A5:A{ALIAS_COL}{ws.row_count}",
                          value_render_option="FORMATTED_VALUE")
        time.sleep(2)
        first_row_by_name = {}
        for i, row in enumerate(all_rows, start=5):
            name = (row[0] if row else "").strip()
            if name and name not in first_row_by_name:
                first_row_by_name[name] = i

        # write aliases
        updates = []
        for name, aliases in aliases_by_name:
            r = first_row_by_name.get(name)
            if r is None:
                print(f"  ! '{name}' not found in bible — skipped", flush=True)
                continue
            updates.append({
                "range": f"'LOCATIONS'!{ALIAS_COL}{r}",
                "values": [[aliases]],
            })
        if updates:
            sh.values_batch_update(body={
                "valueInputOption": "RAW",
                "data": updates,
            })
            for u in updates:
                rng = u['range'].split('!')[1]
                print(f"  + {rng}: {u['values'][0][0][:80]}…", flush=True)
        time.sleep(15)
    except Exception as e:
        print(f"  ! {e}", flush=True)
        time.sleep(20)

print("\n✓ Done", flush=True)
