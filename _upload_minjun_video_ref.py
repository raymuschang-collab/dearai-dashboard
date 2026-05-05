"""Upload RayVideo.mp4 as a Video asset for PARK MIN-JUN. Adds a SECOND
Asset Library row tied to the same canonical name — vidgen will then attach
both the still image (asset-...-tzk8r) AND the video reference whenever
MIN-JUN is mentioned in the body.

Drive id: 15CYyo5exGAFrtNPzFU1MhXP_IwFQ1z-K
Group:    group-20260505195134-wqx2b (sajangnim-bibles)
"""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
from dotenv import load_dotenv
from googleapiclient.discovery import build

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
load_dotenv(HERE / ".env")

from auth import get_credentials
import byteplus_asset_v2 as bp

BIBLE = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"
# BytePlus video assets must be 1.8–15.2s. The team's full RayVideo.mp4
# (15CYyo5exGAFrtNPzFU1MhXP_IwFQ1z-K) is too long → use the 14s trim.
FILE_ID = "1THKmzFmO-z6X7ts4ObM8Zg-C3T_EgGRM"
NAME = "PARK MIN-JUN"
GROUP_ID = os.getenv("BYTEPLUS_GROUP_ID", "group-20260505195134-wqx2b").strip()


def main():
    print("Cool 30s for sheets quota...", flush=True); time.sleep(30)
    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    # Stage 1 — anyone-with-link reader on the video
    print(f"\nStage 1: setting anyone-with-link reader on {FILE_ID}…", flush=True)
    try:
        drive.permissions().create(
            fileId=FILE_ID, body={"role": "reader", "type": "anyone"},
            fields="id", supportsAllDrives=True,
        ).execute()
        print("  ✓ public", flush=True)
    except Exception as e:
        if "already" in str(e).lower() or "duplicate" in str(e).lower():
            print("  • already public", flush=True)
        else:
            print(f"  ! {e}", flush=True)

    # Stage 2 — upload to BytePlus as Video asset
    # Drive's direct-download endpoint serves the binary for files <100MB.
    src_url = f"https://drive.google.com/uc?export=download&id={FILE_ID}"
    print(f"\nStage 2: CreateAsset Video '{NAME} (video ref)' from {src_url}…", flush=True)
    aid = bp.create_asset(GROUP_ID, src_url, "Video", name=f"{NAME} (video ref)")
    print(f"  → {aid} — polling until Active…", flush=True)
    bp.poll_asset(aid, timeout=300)
    print(f"  ✓ {aid} Active", flush=True)

    # Stage 3 — append Asset Library row, same canonical name
    print(f"\nStage 3: appending Asset Library row…", flush=True)
    sh = gc.open_by_key(BIBLE)
    al = sh.worksheet("Asset Library")
    rows = al.get("A5:A60", value_render_option="FORMATTED_VALUE")
    last_used = 4
    for i, r in enumerate(rows, start=5):
        if r and r[0]:
            last_used = i
    next_row = last_used + 1
    ts = datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")
    new_view = f"https://drive.google.com/file/d/{FILE_ID}/view?usp=drivesdk"
    al.update(values=[[NAME, "CHARACTERS", aid, new_view, "video",
                       "Uploaded", ts]],
              range_name=f"A{next_row}:G{next_row}",
              value_input_option="RAW")
    print(f"  ✓ row {next_row}: {NAME} (video) → {aid}", flush=True)

    print(f"\n✓ done. Reload dashboard + ↻ Refresh; next vidgen with MIN-JUN "
          f"in the body will attach {aid} as a reference_video alongside the "
          f"existing still ref.", flush=True)


if __name__ == "__main__":
    main()
