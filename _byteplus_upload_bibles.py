#!/usr/bin/env python3
"""Batch upload LOCATIONS / COSTUME / PROPS / EFFECTS bibles to BytePlus.

Walks each bible's iter URL column, builds a Source URL, calls v2 CreateAsset,
polls until Active, then appends a row to the Asset Library tab.

Locks the existing BYTEPLUS_GROUP_ID from .env."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import gspread

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

# Load .env vars manually (dotenv broke earlier)
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

# Import the v2 client AFTER env is loaded
import byteplus_asset_v2 as bp  # noqa: E402

SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
GROUP_ID = os.environ.get("BYTEPLUS_GROUP_ID", "group-20260505195134-wqx2b")


def drive_view_to_download(url: str) -> str:
    """https://drive.google.com/file/d/<ID>/view  →  download URL BytePlus can fetch."""
    if not url:
        return ""
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if not m:
        return url
    return f"https://drive.google.com/uc?export=download&id={m.group(1)}"


def gather_bible_rows(sh) -> list[dict]:
    """Walk all 4 bibles, return [{name, bible_tab, source_url, tags}, ...]
    for every row that has an iter 1 URL."""
    out = []

    # LOCATIONS — col A=Name, B=Shot Size, J=Iter 1 URL (rows 5+)
    locs_ws = sh.worksheet("LOCATIONS")
    locs = locs_ws.get("A5:L30", value_render_option="FORMATTED_VALUE")
    for r in locs:
        r = (r + [""] * 12)[:12]
        name = r[0].strip()
        url = r[9].strip()
        if name and url:
            tag = f"location; {r[1] or 'wide'}"
            out.append({"name": name, "bible_tab": "LOCATIONS",
                        "source_url": url, "tags": tag})

    # COSTUME / PROPS / EFFECTS — col A=Name, G=Iter 1 URL (rows 6+)
    for tab_name, tag_prefix in [("COSTUME", "costume"), ("PROPS", "prop"), ("EFFECTS", "effect")]:
        ws = sh.worksheet(tab_name)
        rows = ws.get("A6:J60", value_render_option="FORMATTED_VALUE")
        for r in rows:
            r = (r + [""] * 10)[:10]
            name = r[0].strip()
            url = r[6].strip()
            if name and url:
                out.append({"name": name, "bible_tab": tab_name,
                            "source_url": url, "tags": tag_prefix})

    return out


def already_uploaded(al_ws) -> set[tuple[str, str]]:
    """Set of (name, bible_tab) tuples already in Asset Library with Status=Uploaded."""
    al = al_ws.get("A5:F500", value_render_option="FORMATTED_VALUE")
    out = set()
    for r in al:
        r = (r + [""] * 6)[:6]
        if r[5].strip().lower() == "uploaded" and r[2].strip():
            out.add((r[0].strip(), r[1].strip()))
    return out


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    al_ws = sh.worksheet("Asset Library")

    rows = gather_bible_rows(sh)
    print(f"Gathered {len(rows)} bible entries with Source URLs")

    seen = already_uploaded(al_ws)
    rows = [r for r in rows if (r["name"], r["bible_tab"]) not in seen]
    print(f"After dedupe vs Asset Library: {len(rows)} to upload\n")

    # ---- PHASE 1: fire all CreateAsset calls (fast, sequential) ----
    submitted: list[dict] = []
    for i, r in enumerate(rows):
        download_url = drive_view_to_download(r["source_url"])
        try:
            aid = bp.create_asset(GROUP_ID, download_url, "Image", name=r["name"])
            print(f"  [{i+1:>2}/{len(rows)}] {r['bible_tab']:<9} · {r['name'][:40]:<40} → {aid}")
            r["asset_id"] = aid
            r["download_url"] = download_url
            submitted.append(r)
        except SystemExit as e:
            print(f"  [{i+1:>2}/{len(rows)}] ✗ FAILED for {r['name']}: {e}")
            r["error"] = str(e)
            submitted.append(r)
        except Exception as e:
            print(f"  [{i+1:>2}/{len(rows)}] ✗ FAILED for {r['name']}: {type(e).__name__}: {e}")
            r["error"] = f"{type(e).__name__}: {e}"
            submitted.append(r)

    # ---- PHASE 2: poll each to Active (parallel) ----
    print(f"\nPolling {sum(1 for r in submitted if r.get('asset_id'))} assets to Active...")

    def poll_one(r):
        aid = r.get("asset_id")
        if not aid:
            return r
        try:
            t0 = time.time()
            result = bp.poll_asset(aid, timeout=300)
            r["status"] = result.get("Status")
            r["poll_seconds"] = round(time.time() - t0, 1)
        except SystemExit as e:
            r["status"] = "Failed"
            r["error"] = str(e)
        except Exception as e:
            r["status"] = "Failed"
            r["error"] = f"{type(e).__name__}: {e}"
        return r

    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(poll_one, r) for r in submitted]):
            r = fut.result()
            ok = r.get("status") == "Active"
            print(f"  {'✓' if ok else '✗'} {r.get('name', '?')[:40]:<40} → {r.get('status', '—')} "
                  f"({r.get('poll_seconds', '—')}s)")

    # ---- PHASE 3: append rows to Asset Library ----
    al_existing = al_ws.get("A5:A500", value_render_option="FORMATTED_VALUE")
    next_row = 5 + sum(1 for r in al_existing if r and r[0])
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_rows = []
    for r in submitted:
        if r.get("status") != "Active":
            continue
        new_rows.append([
            r["name"],              # A
            r["bible_tab"],         # B
            r["asset_id"],          # C — Asset Code
            r["source_url"],        # D — Source URL
            "image",                # E
            "Uploaded",             # F
            ts,                     # G
            "",                     # H First Used Shot (filled later by audit)
            "Claude Ad v4.1",       # I
            r["tags"],              # J
            "",                     # K
            "",                     # L
        ])
    if new_rows:
        end_row = next_row + len(new_rows) - 1
        al_ws.update(range_name=f"A{next_row}:L{end_row}",
                     values=new_rows, value_input_option="USER_ENTERED")
        print(f"\n✓ Appended {len(new_rows)} rows to Asset Library (rows {next_row}-{end_row})")

    # Summary
    by_tab = {}
    for r in submitted:
        tab = r["bible_tab"]
        by_tab.setdefault(tab, {"done": 0, "fail": 0})
        if r.get("status") == "Active":
            by_tab[tab]["done"] += 1
        else:
            by_tab[tab]["fail"] += 1
    print(f"\n=== SUMMARY ===")
    for tab, counts in by_tab.items():
        print(f"  {tab:<10}: {counts['done']} done · {counts['fail']} failed")
    # save manifest
    with open("/tmp/byteplus_bibles_upload.json", "w") as f:
        json.dump(submitted, f, indent=2)
    print(f"\nManifest: /tmp/byteplus_bibles_upload.json")


if __name__ == "__main__":
    main()
