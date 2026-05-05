"""Pass 2: clear two stale iter-2 cells (Walk-In Cooler, Alley Behind Hanbyeol),
then walk every team Drive subfolder and write iter-2 URLs wherever an
additional variant exists (CHARACTERS col U, LOCATIONS col K).

Iter 1 was already filled by _upload_team_assets.py — this just adds the
second variant where the team uploaded multiple photos."""
import time
import gspread
from auth import get_credentials
from googleapiclient.discovery import build

BIBLE = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

# (bible_tab, row, col, file_id_or_None, label)
# file_id_or_None = "" means CLEAR the cell.
CLEAR = [
    ("LOCATIONS",  7, "K", "",  "Walk-In Cooler iter 2 — CLEAR"),
    ("LOCATIONS", 10, "K", "",  "Alley Behind Hanbyeol iter 2 — CLEAR"),
]

# Iter 2 variants from the team's asset folders. Each pulled from the
# already-public set (perms set in pass 1) — but we re-set permissions
# defensively in case any are private.
ITER2 = [
    # ---- CHARACTERS (col U = Iter 2 URL) ----
    ("CHARACTERS",  2, "U", "14GCCvH0yootUFItpczBc63rI4DGxeWp6", "TARA ANJANI iter2 ← Tara Bun Hair"),
    ("CHARACTERS",  3, "U", "1c71Ao_qPJeizsVZbrmFe01At28YcFz5G", "LEE JOON-HO iter2 ← VER 1"),
    ("CHARACTERS",  4, "U", "1JW0ruYqZl1mDL9HUL43tFHTooSkfJ4CL", "PARK MIN-JUN iter2 ← V03"),
    ("CHARACTERS",  5, "U", "1aBsd4KU8jm9S24yBZ379_A-SsNmOl32H", "BU ENDANG iter2 ← character sheet"),
    ("CHARACTERS",  6, "U", "1jTwtBSvGgUf9UDf1tQvYz4n85UxF9dv2", "GALIH iter2 ← character sheet_1"),

    # ---- LOCATIONS (col K = Iter 2 URL) — only where >1 team file exists ----
    ("LOCATIONS",   5, "K", "15FaCcZWwLJKUL9iOXNuLOCbc-lk8xfOB", "Hanbyeol Bistro Kitchen iter2 ← INT. Kicthen (alt)"),
    ("LOCATIONS",   9, "K", "1Olh_Mg5316maPZixhgOVMy_6hmsmGwDj", "Hanbyeol Storage Room iter2 ← INT. Storage (alt)"),
    ("LOCATIONS",  10, "K", "1N1n4_40alxvTLQjO943ItFCFYwG6ChPV", "Alley Behind Hanbyeol iter2 ← Night Rain"),
    ("LOCATIONS",  11, "K", "1clJ5LjvC18jXa6YbVSOAUfkQazgEJOEu", "Tara's Mampang Apartment iter2 ← Night Version"),
    # Walk-In Cooler: only 1 team file (INT. Chiller) — iter 2 left CLEARED above.
]

# Note: clear LOCATIONS!K10 first, then ITER2 re-fills it with Night Rain.
# We run CLEAR before ITER2 so the alley value gets the new one.

print("Cool 30s for sheets quota...", flush=True)
time.sleep(30)
creds = get_credentials()
gc = gspread.authorize(creds)
ds = build("drive", "v3", credentials=creds)
sh = gc.open_by_key(BIBLE)

# Stage 1 — set anyone-with-link reader on the new variant files
print("\nStage 1: making iter-2 files public...", flush=True)
for _, _, _, fid, label in ITER2:
    if not fid:
        continue
    try:
        ds.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"},
                                 fields="id", supportsAllDrives=True).execute()
        print(f"  ✓ {fid}  ({label})", flush=True)
    except Exception as e:
        msg = str(e)
        if "already" in msg.lower() or "duplicate" in msg.lower():
            print(f"  • {fid} (already public)", flush=True)
        else:
            print(f"  ! {fid}: {msg[:120]}", flush=True)

def view(fid):
    return f"https://drive.google.com/file/d/{fid}/view?usp=drivesdk"

# Stage 2 — clear stale iter-2 cells
print("\nStage 2: clearing stale iter-2 cells...", flush=True)
clear_data = [{"range": f"'{tab}'!{c}{r}", "values": [[""]]}
              for tab, r, c, _, label in CLEAR]
sh.values_batch_update(body={"valueInputOption": "RAW", "data": clear_data})
for tab, r, c, _, label in CLEAR:
    print(f"  ✓ {tab}!{c}{r} cleared  ({label})", flush=True)
time.sleep(8)

# Stage 3 — write iter-2 variant URLs
print("\nStage 3: writing iter-2 variants...", flush=True)
by_tab: dict[str, list] = {}
for tab, r, c, fid, label in ITER2:
    if not fid:
        continue
    by_tab.setdefault(tab, []).append((tab, r, c, fid, label))
for tab, rows in by_tab.items():
    print(f"\n  --- {tab} ---", flush=True)
    updates = [{"range": f"'{tab}'!{c}{r}", "values": [[view(fid)]]}
               for _, r, c, fid, _ in rows]
    sh.values_batch_update(body={"valueInputOption": "RAW", "data": updates})
    for _, r, c, _, label in rows:
        print(f"    {tab}!{c}{r}: {label}", flush=True)
    time.sleep(8)

print("\n✓ done — reload dashboard + click ↻ Refresh.", flush=True)
