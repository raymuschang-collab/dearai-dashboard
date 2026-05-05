"""Locations-only audit on Sajangnim Shotlist + Storyboard Prompts.

Stage 1: For each Shot row on the Shotlist tab, detect a Location from
description/dialogue/SFX using the Sajangnim alias map. Write `loc:<canonical>`
into col T (Refs Detected — Loc/Prop/Costume/FX/Type), preserving any existing
prop/costume/fx tags.

Stage 2: Roll up Shotlist locations into Storyboard Prompts col L. Each set
covers 5 shots; the set's location = the first non-empty per-shot location
(if a single set spans 2+ locations, the first one wins).

Idempotent. Safe to re-run."""
import gspread, time, re, sys
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]

# Sajangnim location aliases — most specific first.
ALIASES = [
    ("walk-in cooler", "Walk-In Cooler"),
    ("walk in cooler", "Walk-In Cooler"),
    ("cold room", "Walk-In Cooler"),
    ("alley behind hanbyeol", "Alley Behind Hanbyeol"),
    ("back-alley", "Alley Behind Hanbyeol"),
    ("back alley", "Alley Behind Hanbyeol"),
    ("service alley", "Alley Behind Hanbyeol"),
    ("dressing room", "Hanbyeol Dressing Room"),
    ("locker room", "Hanbyeol Dressing Room"),
    ("changing room", "Hanbyeol Dressing Room"),
    ("storage room", "Hanbyeol Storage Room"),
    ("stockroom", "Hanbyeol Storage Room"),
    ("dry storage", "Hanbyeol Storage Room"),
    ("pass station", "Hanbyeol Pass Station"),
    ("the pass", "Hanbyeol Pass Station"),
    ("expo line", "Hanbyeol Pass Station"),
    ("expediter", "Hanbyeol Pass Station"),
    ("ticket rail", "Hanbyeol Pass Station"),
    ("plating area", "Hanbyeol Pass Station"),
    ("joon-ho's office", "Joon-Ho's Office"),
    ("joon ho's office", "Joon-Ho's Office"),
    ("manager's office", "Joon-Ho's Office"),
    ("owner's office", "Joon-Ho's Office"),
    ("mampang apartment", "Tara's Mampang Apartment"),
    ("mampang", "Tara's Mampang Apartment"),
    ("tara's apartment", "Tara's Mampang Apartment"),
    ("tara's room", "Tara's Mampang Apartment"),
    ("her apartment", "Tara's Mampang Apartment"),
    ("kost", "Tara's Mampang Apartment"),
    ("hanbyeol bistro kitchen", "Hanbyeol Bistro Kitchen"),
    ("hanbyeol kitchen", "Hanbyeol Bistro Kitchen"),
    ("bistro kitchen", "Hanbyeol Bistro Kitchen"),
    ("korean kitchen", "Hanbyeol Bistro Kitchen"),
    ("kitchen line", "Hanbyeol Bistro Kitchen"),
    ("prep station", "Hanbyeol Bistro Kitchen"),
    ("cutting board", "Hanbyeol Bistro Kitchen"),
    ("induction burner", "Hanbyeol Bistro Kitchen"),
    ("kitchen ambient", "Hanbyeol Bistro Kitchen"),
    ("kitchen clatter", "Hanbyeol Bistro Kitchen"),
    ("stove hiss", "Hanbyeol Bistro Kitchen"),
    ("kitchen hum", "Hanbyeol Bistro Kitchen"),
    ("chef's knife", "Hanbyeol Bistro Kitchen"),
    ("chef whites", "Hanbyeol Bistro Kitchen"),
    ("kitchen tile", "Hanbyeol Bistro Kitchen"),
    ("knife thump", "Hanbyeol Bistro Kitchen"),
    ("knife slice", "Hanbyeol Bistro Kitchen"),
    ("knife slip", "Hanbyeol Bistro Kitchen"),
    ("kitchen", "Hanbyeol Bistro Kitchen"),
]

def detect(text: str, valid: set[str]) -> str:
    tl = text.lower()
    for alias, canon in ALIASES:
        if canon not in valid:
            continue
        if alias in tl:
            return canon
    return ""

def merge_loc_into_t(existing: str, new_loc: str) -> str:
    """Replace any existing loc:... tag with the new one. Preserve prop/costume/fx."""
    parts = [p.strip() for p in (existing or "").split(";") if p.strip()]
    parts = [p for p in parts if not p.lower().startswith("loc:")]
    if new_loc:
        parts.insert(0, f"loc:{new_loc}")
    return "; ".join(parts)

print("Cooling down 120s for quota...", flush=True)
time.sleep(120)

gc = gspread.authorize(get_credentials())
# Load LOCATIONS bible canonicals once
bible_sh = gc.open_by_key(EPISODES[0][1])
loc_ws = bible_sh.worksheet("LOCATIONS")
valid = {row[0].strip() for row in loc_ws.get("A5:A100") if row and row[0]}
print(f"Valid canonicals: {valid}", flush=True)

for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        sl = sh.worksheet("Shotlist")
        time.sleep(3)
        all_rows = sl.get_all_values()
        time.sleep(3)
        if len(all_rows) < 2:
            print("  empty shotlist, skip", flush=True)
            continue
        header = all_rows[0]
        # find cols by header name
        def find_col(*candidates):
            for i, h in enumerate(header):
                hs = h.strip()
                for c in candidates:
                    if hs == c or hs.startswith(c):
                        return i
            return None
        desc_i = find_col("Shot Description")
        diag_i = find_col("Dialogue/VO")
        sfx_i  = find_col("SFX")
        loc_t_i = find_col("Refs Detected — Loc/Prop/Costume/FX/Type",
                           "Refs Detected — Loc")
        if desc_i is None or loc_t_i is None:
            print(f"  ! missing desc or loc cols — header={header}", flush=True)
            continue

        # ---- Stage 1: write per-shot locations into col T ----
        per_shot_locs: list[str] = []  # canonical or "" — index 0 = shot 1
        updates = []
        for ridx, row in enumerate(all_rows[1:], start=2):
            if not row:
                per_shot_locs.append("")
                continue
            desc = row[desc_i] if desc_i < len(row) else ""
            diag = row[diag_i] if diag_i is not None and diag_i < len(row) else ""
            sfx  = row[sfx_i]  if sfx_i  is not None and sfx_i  < len(row) else ""
            scan = "\n".join([desc, diag, sfx])
            if not scan.strip():
                per_shot_locs.append("")
                continue
            new_loc = detect(scan, valid)
            per_shot_locs.append(new_loc)
            existing = row[loc_t_i] if loc_t_i < len(row) else ""
            merged = merge_loc_into_t(existing, new_loc)
            if merged != existing:
                t_letter = chr(65 + loc_t_i) if loc_t_i < 26 else "A" + chr(65 + loc_t_i - 26)
                updates.append({"range": f"'Shotlist'!{t_letter}{ridx}",
                                 "values": [[merged]]})
        if updates:
            sh.values_batch_update(body={"valueInputOption": "RAW",
                                          "data": updates})
            print(f"  Stage 1: wrote {len(updates)} shot-level locations to Shotlist!T", flush=True)
        else:
            print(f"  Stage 1: nothing to write (already up-to-date)", flush=True)
        time.sleep(5)

        # ---- Stage 2: roll up to Storyboard Prompts col L ----
        sp = sh.worksheet("Storyboard Prompts")
        time.sleep(3)
        sp_rows_max = (len(per_shot_locs) + 4) // 5
        L_values = []
        for set_n in range(1, sp_rows_max + 1):
            first = (set_n - 1) * 5
            last  = set_n * 5
            slice_locs = [l for l in per_shot_locs[first:last] if l]
            if slice_locs:
                # majority vote, fall back to first non-empty
                from collections import Counter
                top = Counter(slice_locs).most_common(1)[0][0]
                L_values.append([top])
            else:
                L_values.append(["Unspecified"])
        if L_values:
            sp.update(values=L_values, range_name=f"L11:L{10+len(L_values)}",
                       value_input_option="RAW")
            matched = sum(1 for v in L_values if v[0] != "Unspecified")
            print(f"  Stage 2: wrote {len(L_values)} sets to Storyboard Prompts!L "
                  f"({matched} matched, {len(L_values)-matched} Unspecified)", flush=True)
            for i, v in enumerate(L_values, start=11):
                print(f"    L{i}: {v[0]}", flush=True)
        time.sleep(15)
    except Exception as e:
        print(f"  ! error: {e}", flush=True)
        time.sleep(30)

print("\n✓ done all episodes", flush=True)
