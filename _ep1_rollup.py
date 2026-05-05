"""Ep 1 Stage 2 retry — rollup Shotlist!T per-shot locations into SP!L."""
import gspread, time, re
from collections import Counter
from auth import get_credentials

SID = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

print("Cool 90s for quota...", flush=True)
time.sleep(90)

gc = gspread.authorize(get_credentials())
sh = gc.open_by_key(SID)
sl = sh.worksheet("Shotlist")
all_rows = sl.get_all_values()
header = all_rows[0]
loc_t_i = None
for i, h in enumerate(header):
    if h.strip().startswith("Refs Detected — Loc"):
        loc_t_i = i
        break
print(f"Shotlist!T col idx = {loc_t_i}", flush=True)

per_shot = []
for row in all_rows[1:]:
    if not row or len(row) <= loc_t_i:
        per_shot.append("")
        continue
    cell = row[loc_t_i]
    m = re.search(r"loc:([^;]+)", cell or "")
    per_shot.append(m.group(1).strip() if m else "")
print(f"per_shot count = {len(per_shot)}, non-empty = {sum(1 for p in per_shot if p)}", flush=True)

time.sleep(5)
sp = sh.worksheet("Storyboard Prompts")
sets_n = (len(per_shot) + 4) // 5
L_values = []
for set_n in range(1, sets_n + 1):
    first = (set_n - 1) * 5
    last = set_n * 5
    slice_locs = [l for l in per_shot[first:last] if l]
    if slice_locs:
        L_values.append([Counter(slice_locs).most_common(1)[0][0]])
    else:
        L_values.append(["Unspecified"])

sp.update(values=L_values, range_name=f"L11:L{10+len(L_values)}",
          value_input_option="RAW")
matched = sum(1 for v in L_values if v[0] != "Unspecified")
print(f"Wrote {len(L_values)} sets to Ep 1 SP!L ({matched} matched, {len(L_values)-matched} Unspecified)", flush=True)
for i, v in enumerate(L_values, start=11):
    print(f"  L{i}: {v[0]}", flush=True)
