"""Repair Storyboard Prompts!L cells that were overwritten by the legacy
SLOT_TO_COL={1:'L',2:'M'} bug in byteplus_vidgen.py. Detect L cells that
contain a URL (instead of a location name) and either:
  - re-roll from Shotlist!T, or
  - forward-fill from the previous matched set."""
import gspread, time, re
from collections import Counter
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]

def looks_like_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http") or "drive.google.com" in s

print("Cool 75s for quota...", flush=True)
time.sleep(75)
gc = gspread.authorize(get_credentials())

for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        sl = sh.worksheet("Shotlist")
        time.sleep(3)
        all_rows = sl.get_all_values()
        time.sleep(3)
        # find col T (Refs Detected — Loc)
        loc_t_i = None
        for i, h in enumerate(all_rows[0] if all_rows else []):
            if h.strip().startswith("Refs Detected — Loc"):
                loc_t_i = i
                break
        if loc_t_i is None:
            print(f"  ! no Refs Detected — Loc col, skipping", flush=True)
            continue
        # per-shot canonical
        per_shot = []
        for row in all_rows[1:]:
            if not row or len(row) <= loc_t_i:
                per_shot.append("")
                continue
            m = re.search(r"loc:([^;]+)", row[loc_t_i] or "")
            per_shot.append(m.group(1).strip() if m else "")

        sp = sh.worksheet("Storyboard Prompts")
        time.sleep(3)
        cur_l = sp.get("L11:L60", value_render_option="FORMATTED_VALUE")
        time.sleep(2)
        n_rows = len(cur_l)
        if n_rows == 0:
            print("  no SP rows, skipping", flush=True)
            continue
        new_l = []
        last_known = ""
        urls_repaired = 0
        for set_n in range(1, n_rows + 1):
            cur = (cur_l[set_n - 1][0] if cur_l[set_n - 1] else "").strip()
            # build proposed value from rollup
            slice_locs = [l for l in per_shot[(set_n-1)*5:set_n*5] if l]
            rolled = (Counter(slice_locs).most_common(1)[0][0]
                      if slice_locs else "")
            if looks_like_url(cur):
                # corrupted — replace with rolled, then forward-fill if rolled empty
                new_v = rolled or last_known or "Unspecified"
                urls_repaired += 1
            elif not cur or cur.lower() == "unspecified":
                new_v = rolled or last_known or "Unspecified"
            else:
                new_v = cur  # keep manual / valid value
            if new_v.lower() != "unspecified":
                last_known = new_v
            new_l.append([new_v])

        # second pass — forward-fill any remaining Unspecified using running last_known
        last = ""
        final_l = []
        for [v] in new_l:
            if v.lower() == "unspecified" and last:
                final_l.append([last])
            else:
                final_l.append([v])
                if v.lower() != "unspecified":
                    last = v

        sp.update(values=final_l,
                  range_name=f"L11:L{10+len(final_l)}",
                  value_input_option="RAW")
        good = sum(1 for [v] in final_l if v.lower() != "unspecified")
        print(f"  repaired {urls_repaired} URL-stomped cells; final coverage {good}/{len(final_l)}", flush=True)
        for i, [v] in enumerate(final_l, start=11):
            print(f"    L{i}: {v}", flush=True)
        time.sleep(12)
    except Exception as e:
        print(f"  ! {e}", flush=True)
        time.sleep(20)
print("\n✓ done", flush=True)
