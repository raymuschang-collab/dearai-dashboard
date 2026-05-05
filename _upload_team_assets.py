"""Upload (= write Drive URLs to bible Iter 1 cells) the team's working
files from sajangnim/01.Assets/* into the Sajangnim bible. Sets each Drive
file to anyone-with-link reader so the dashboard's lh3 thumbs render.

Idempotent — re-running just re-writes the same URLs."""
import time
import gspread
from auth import get_credentials
from googleapiclient.discovery import build

BIBLE = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

# (bible_tab, row, col, file_id, label-for-log)
ASSIGNMENTS = [
    # ---- CHARACTERS — col T = Iter 1 URL ----
    ("CHARACTERS",  2, "T", "1-8I7NQa7cEG0vP8N7hh3LvZE5-WPR2P2", "TARA ANJANI ← Tara Tied Hair"),
    ("CHARACTERS",  3, "T", "1mCYXN9JFJsaHuz0e9nrsmM4v-OC09Lfo", "LEE JOON-HO ← VER 2"),
    ("CHARACTERS",  4, "T", "1jnf5zpEKXxJxkDEEkzbEkseVHuevOIQO", "PARK MIN-JUN ← V02"),
    ("CHARACTERS",  5, "T", "1SjlJWcHSHZ00VJTCHlmc5gbYp03gHrPR", "BU ENDANG ← Model Sheet v.2"),
    ("CHARACTERS",  6, "T", "1H7jqiIWMxS-vldsNgGSvmch_vT_gqwj_", "GALIH ← character sheet"),

    # ---- LOCATIONS — col J = Iter 1 URL (on wide rows) ----
    ("LOCATIONS",   5, "J", "10wivkLHQMHUrouoTx9Kml9CV9lWnWpYX", "Hanbyeol Bistro Kitchen ← INT. Kitchen 4"),
    ("LOCATIONS",   6, "J", "1qULgOP8GD1QrJc31Eq_OmZXSaj1DuWmy", "Hanbyeol Dressing Room ← INT. Locker Room"),
    ("LOCATIONS",   7, "J", "1diYBNQpWi1bG_XfM4C_w9qmG71TXfzl0", "Walk-In Cooler ← INT. Chiller"),
    ("LOCATIONS",   8, "J", "18jiO12bVsNviNAxEOGg_mhwF9PefsC08", "Joon-Ho's Office ← INT.Office"),
    ("LOCATIONS",   9, "J", "10wivkLHQMHUrouoTx9Kml9CV9lWnWpYX", "(placeholder Storage — using Kitchen)"),
    # NOTE: Storage 4.png is 1OTqk9ED9NljmEdEp1etCtD9X5Zk16G4h
    ("LOCATIONS",  10, "J", "1uWUm645YEmhWxZy1_10yFCOIBCyBkHvY", "Alley Behind Hanbyeol ← EXT. Back Alley 4"),
    ("LOCATIONS",  11, "J", "1IsexbI4Xhgr1GQA9k7QSfZYukXgdJ30x", "Tara's Mampang Apartment ← Studio Day"),
    ("LOCATIONS",  12, "J", "198Eim35295y-4ww25mzEZPndhXmUQJW5", "Hanbyeol Pass Station ← INT. Hanbyeol Bistro"),

    # ---- COSTUME — col G = Iter 1 URL ----
    ("COSTUME",     6, "G", "1hSG9vBvfVRu1HcDs-ukWCQA8HQNcfV32", "White junior chef coat (Tara EP01) ← Chef Uniform"),
    ("COSTUME",     8, "G", "1ePf8FWTtKT4XYE3h92APTNN_FI4sR0Gm", "Tara casual (apartment) ← Tara Casual"),
    ("COSTUME",     9, "G", "1hSG9vBvfVRu1HcDs-ukWCQA8HQNcfV32", "Sous chef whites (Min-jun) ← Chef Uniform"),
    ("COSTUME",    10, "G", "1hSG9vBvfVRu1HcDs-ukWCQA8HQNcfV32", "Executive chef whites (Joon-ho) ← Chef Uniform"),
    ("COSTUME",    13, "G", "112odLdCPYvgfG24OmFfbb1_wJt6D4yWt", "Joon-ho's casual ← Chef Lee Casual"),
]

# Fix the Storage entry (was wrong file_id above)
for i, a in enumerate(ASSIGNMENTS):
    if a[0] == "LOCATIONS" and a[1] == 9:
        ASSIGNMENTS[i] = ("LOCATIONS", 9, "J", "1OTqk9ED9NljmEdEp1etCtD9X5Zk16G4h",
                           "Hanbyeol Storage Room ← INT. Storage 4")

print("Cool 60s for sheets quota...", flush=True)
time.sleep(60)

creds = get_credentials()
gc = gspread.authorize(creds)
ds = build("drive", "v3", credentials=creds)
sh = gc.open_by_key(BIBLE)

# Stage 1: ensure each Drive file is anyone-with-link reader
print("\nStage 1: setting anyone-with-link reader on each file...", flush=True)
unique_ids = sorted({a[3] for a in ASSIGNMENTS})
for fid in unique_ids:
    try:
        ds.permissions().create(
            fileId=fid,
            body={"role": "reader", "type": "anyone"},
            fields="id",
            supportsAllDrives=True,
        ).execute()
        print(f"  ✓ {fid}", flush=True)
    except Exception as e:
        msg = str(e)
        if "already" in msg.lower() or "duplicate" in msg.lower():
            print(f"  • {fid} (already public)", flush=True)
        else:
            print(f"  ! {fid}: {msg[:120]}", flush=True)

# Stage 2: build batch update — group by tab, write all in one batch_update per tab
print("\nStage 2: writing Drive URLs to bible cells...", flush=True)
def view_url(fid):
    return f"https://drive.google.com/file/d/{fid}/view?usp=drivesdk"

# Group writes per tab to minimize round-trips
by_tab: dict[str, list] = {}
for tab, row, col, fid, label in ASSIGNMENTS:
    by_tab.setdefault(tab, []).append((tab, row, col, fid, label))

for tab, rows in by_tab.items():
    print(f"\n  --- {tab} ---", flush=True)
    updates = []
    for _, r, c, fid, label in rows:
        url = view_url(fid)
        updates.append({"range": f"'{tab}'!{c}{r}", "values": [[url]]})
        print(f"    {tab}!{c}{r}: {label}", flush=True)
    sh.values_batch_update(body={
        "valueInputOption": "RAW",
        "data": updates,
    })
    time.sleep(8)  # gentle pace

print("\n✓ All assets written. Reload dashboard + click ↻ Refresh.", flush=True)
