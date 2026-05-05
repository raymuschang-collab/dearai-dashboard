"""Prep Asset Library tab for BytePlus upload — quota-friendly version.

Single batchGet for all URL reads, single batchUpdate for all writes."""
import time
from datetime import datetime, timezone

import gspread
from auth import get_credentials

BIBLE = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

LOC_NAMES_BY_BIBLE_ROW = [
    (5,  "Hanbyeol Bistro Kitchen"),
    (6,  "Hanbyeol Dressing Room"),
    (7,  "Walk-In Cooler"),
    (8,  "Joon-Ho's Office"),
    (9,  "Hanbyeol Storage Room"),
    (10, "Alley Behind Hanbyeol"),
    (11, "Tara's Mampang Apartment"),
    (12, "Hanbyeol Pass Station"),
]

CHAR_NAMES_BY_BIBLE_ROW = [
    (2, "TARA ANJANI"),
    (3, "LEE JOON-HO"),
    (4, "PARK MIN-JUN"),
    (5, "BU ENDANG"),
    (6, "GALIH"),
]

print("Cool 30s for sheets quota...", flush=True)
time.sleep(30)

gc = gspread.authorize(get_credentials())
sh = gc.open_by_key(BIBLE)

# ---- ONE batchGet for all reads ----
ranges = (
    [f"LOCATIONS!J{r}" for r, _ in LOC_NAMES_BY_BIBLE_ROW]
    + [f"CHARACTERS!T{r}" for r, _ in CHAR_NAMES_BY_BIBLE_ROW]
    + ["'Asset Library'!A5:F60"]
)
print(f"batchGet {len(ranges)} ranges...", flush=True)
resp = sh.values_batch_get(ranges, params={"valueRenderOption": "FORMATTED_VALUE"})
values_lists = [r.get("values", []) for r in resp.get("valueRanges", [])]

# Resolve URLs
n_loc = len(LOC_NAMES_BY_BIBLE_ROW)
n_char = len(CHAR_NAMES_BY_BIBLE_ROW)
loc_urls = {}
for i, (row, name) in enumerate(LOC_NAMES_BY_BIBLE_ROW):
    cell = values_lists[i]
    url = cell[0][0] if cell and cell[0] else ""
    loc_urls[name] = url
char_urls = {}
for i, (row, name) in enumerate(CHAR_NAMES_BY_BIBLE_ROW):
    cell = values_lists[n_loc + i]
    url = cell[0][0] if cell and cell[0] else ""
    char_urls[name] = url
al_rows = values_lists[n_loc + n_char]
print("\nResolved URLs:")
for n, u in loc_urls.items():
    print(f"  LOC {n}: {u[:70]}")
for n, u in char_urls.items():
    print(f"  CHR {n}: {u[:70]}")

# ---- Build all writes ----
updates = []

# Stage A: Locations rows 5-12 — refresh URLs
print("\nStage A: refreshing LOCATIONS rows 5-12...", flush=True)
for i, row in enumerate(al_rows[:8]):
    sheet_row = 5 + i
    row = (row + [""] * 6)[:6]
    name = row[0]
    if name in loc_urls:
        new_url = loc_urls[name]
        updates.append({"range": f"'Asset Library'!C{sheet_row}", "values": [[""]]})
        updates.append({"range": f"'Asset Library'!D{sheet_row}", "values": [[new_url]]})
        updates.append({"range": f"'Asset Library'!F{sheet_row}", "values": [["Pending"]]})
        print(f"  row {sheet_row}: {name} → {new_url[:60]}", flush=True)

# Stage B: append CHARACTERS rows after last used
last_used = 4
for i, r in enumerate(al_rows, start=5):
    if r and r[0]:
        last_used = i
next_row = last_used + 1
print(f"\nStage B: appending {n_char} CHARACTERS rows starting at row {next_row}...", flush=True)
for i, (_, name) in enumerate(CHAR_NAMES_BY_BIBLE_ROW):
    url = char_urls.get(name, "")
    if not url:
        print(f"  ! {name} no URL, skipping", flush=True)
        continue
    sheet_row = next_row + i
    updates.append({"range": f"'Asset Library'!A{sheet_row}", "values": [[name]]})
    updates.append({"range": f"'Asset Library'!B{sheet_row}", "values": [["CHARACTERS"]]})
    updates.append({"range": f"'Asset Library'!C{sheet_row}", "values": [[""]]})
    updates.append({"range": f"'Asset Library'!D{sheet_row}", "values": [[url]]})
    updates.append({"range": f"'Asset Library'!E{sheet_row}", "values": [["character"]]})
    updates.append({"range": f"'Asset Library'!F{sheet_row}", "values": [["Pending"]]})
    print(f"  row {sheet_row}: {name} → {url[:60]}", flush=True)

# Stage C: refresh sync timestamp
ts = datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")
updates.append({"range": "'Asset Library'!B2", "values": [[ts]]})

# ---- Single batchUpdate ----
print(f"\nbatchUpdate {len(updates)} writes...", flush=True)
sh.values_batch_update(body={
    "valueInputOption": "RAW",
    "data": updates,
})
print(f"\n✓ Asset Library prepped — {n_loc + n_char} rows ready (Status=Pending)", flush=True)
print(f"  Last sync = {ts}", flush=True)
