"""One-off: add 'Location' header at col L on Storyboard Prompts for all 6
Sajangnim episodes, plus Video Iter 1/2 URL headers at M/N. Auto-populate
col L by scanning col J body against LOCATIONS bible.

Paced for the 60-reads/min Sheets quota."""
import gspread, time, sys
from auth import get_credentials

EPISODES = [
    ("Ep 1", "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"),
    ("Ep 2", "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4"),
    ("Ep 3", "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I"),
    ("Ep 4", "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4"),
    ("Ep 5", "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg"),
    ("Ep 6", "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI"),
]
BIBLE = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

# initial cooldown to clear quota
print("Cooling down for 75s before start...", flush=True)
time.sleep(75)

gc = gspread.authorize(get_credentials())
bible_sh = gc.open_by_key(BIBLE)
loc_ws = bible_sh.worksheet("LOCATIONS")
loc_rows = loc_ws.get("A5:A100", value_render_option="FORMATTED_VALUE")
locations = sorted(
    {row[0].strip() for row in loc_rows if row and row[0].strip()},
    key=len, reverse=True,
)
print(f"Loaded {len(locations)} locations: {locations}", flush=True)

def detect_location(body: str) -> str:
    bl = body.lower()
    for loc in locations:
        if loc.lower() in bl:
            return loc
    return "Unspecified"

for ep_name, sid in EPISODES:
    print(f"\n=== {ep_name} ({sid[:8]}...) ===", flush=True)
    try:
        sh = gc.open_by_key(sid)
        ws = sh.worksheet("Storyboard Prompts")
        time.sleep(3)
        if ws.col_count < 14:
            ws.resize(rows=max(ws.row_count, 50), cols=14)
            print(f"  Resized to 14 cols", flush=True)
            time.sleep(3)
        hdr_rows = ws.get("A10:N10", value_render_option="FORMATTED_VALUE")
        hdr = (hdr_rows[0] if hdr_rows else []) + [""] * 14
        hdr = hdr[:14]
        time.sleep(3)
        updates = []
        if hdr[11] != "Location":
            updates.append({"range": "L10", "values": [["Location"]]})
        if hdr[12] != "Video Iter 1 URL":
            updates.append({"range": "M10", "values": [["Video Iter 1 URL"]]})
        if hdr[13] != "Video Iter 2 URL":
            updates.append({"range": "N10", "values": [["Video Iter 2 URL"]]})
        if updates:
            ws.batch_update(updates, value_input_option="RAW")
            time.sleep(3)
            for u in updates:
                print(f"  + {u['range']}: {u['values'][0][0]}", flush=True)
        body_rows = ws.get("J11:J50", value_render_option="FORMATTED_VALUE")
        time.sleep(3)
        detected = []
        last_with_data = 0
        for i, row in enumerate(body_rows):
            body = (row[0] if row else "")
            if body.strip():
                last_with_data = i + 1
            detected.append([detect_location(body)])
        if last_with_data > 0:
            ws.update(f"L11:L{10+last_with_data}", detected[:last_with_data], value_input_option="RAW")
            match = sum(1 for d in detected[:last_with_data] if d[0] != "Unspecified")
            unspec = last_with_data - match
            print(f"  L11:L{10+last_with_data}: {match} matched / {unspec} Unspecified", flush=True)
            for i, d in enumerate(detected[:last_with_data], start=11):
                print(f"    L{i}: {d[0]}", flush=True)
        time.sleep(15)  # pace under quota
    except gspread.exceptions.APIError as e:
        print(f"  ! API error: {e}. Sleeping 60s + retry...", flush=True)
        time.sleep(60)
        # one retry
        try:
            sh = gc.open_by_key(sid)
            ws = sh.worksheet("Storyboard Prompts")
            time.sleep(3)
            if ws.col_count < 14:
                ws.resize(rows=max(ws.row_count, 50), cols=14)
                time.sleep(3)
            hdr_rows = ws.get("A10:N10", value_render_option="FORMATTED_VALUE")
            hdr = (hdr_rows[0] if hdr_rows else []) + [""] * 14
            hdr = hdr[:14]
            time.sleep(3)
            updates = []
            if hdr[11] != "Location":
                updates.append({"range": "L10", "values": [["Location"]]})
            if hdr[12] != "Video Iter 1 URL":
                updates.append({"range": "M10", "values": [["Video Iter 1 URL"]]})
            if hdr[13] != "Video Iter 2 URL":
                updates.append({"range": "N10", "values": [["Video Iter 2 URL"]]})
            if updates:
                ws.batch_update(updates, value_input_option="RAW")
                time.sleep(3)
            body_rows = ws.get("J11:J50", value_render_option="FORMATTED_VALUE")
            time.sleep(3)
            detected = []
            last_with_data = 0
            for i, row in enumerate(body_rows):
                body = (row[0] if row else "")
                if body.strip():
                    last_with_data = i + 1
                detected.append([detect_location(body)])
            if last_with_data > 0:
                ws.update(f"L11:L{10+last_with_data}", detected[:last_with_data], value_input_option="RAW")
                match = sum(1 for d in detected[:last_with_data] if d[0] != "Unspecified")
                unspec = last_with_data - match
                print(f"  RETRY OK · L11:L{10+last_with_data}: {match} matched / {unspec} Unspecified", flush=True)
            time.sleep(15)
        except Exception as e2:
            print(f"  X retry failed: {e2}", flush=True)

print("\n✓ All 6 episodes done", flush=True)
