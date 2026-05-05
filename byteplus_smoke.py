#!/usr/bin/env python3
"""
byteplus_smoke.py — One-off Seedance 2.0 vidgen for testing/smoke.
Skips the sheet machinery — takes prompt + asset_ids directly.

Usage:
  python3 byteplus_smoke.py --prompt "..." --asset-ids id1,id2 --duration 5 [--resolution 720p] [--fast]
  python3 byteplus_smoke.py --prompt "..." --asset-ids none --duration 5  # text-only, no refs

Output: MP4 to ~/Downloads/byteplus_smoke_<task_id>.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3")

if not ARK_API_KEY:
    sys.exit("BYTEPLUS_ARK_API_KEY not set in .env")

ap = argparse.ArgumentParser()
ap.add_argument("--prompt", required=True)
ap.add_argument("--ref", action="append", default=[],
                help="Reference URL — repeatable. Format: 'image:https://...' or 'video:https://...'. "
                     "Role defaults to 'subject'. Can append ',role=X' for explicit role.")
ap.add_argument("--duration", type=int, default=5)
ap.add_argument("--resolution", default="720p", choices=["480p","720p","1080p","2K"])
ap.add_argument("--aspect", default="9:16")
ap.add_argument("--fast", action="store_true")
ap.add_argument("--output", default=None, help="Output MP4 path (default: ~/Downloads/byteplus_smoke_<id>.mp4)")
ap.add_argument("--label", default="smoke", help="Label for output filename + expense log")
args = ap.parse_args()

# Parse refs: each is "type:url" optionally with ",role=X"
references = []
for r in args.ref:
    if ":" not in r: continue
    type_part, url_part = r.split(":", 1)
    role = "subject"
    if ",role=" in url_part:
        url_part, role = url_part.split(",role=", 1)
    references.append({"type": type_part.strip(), "url": url_part.strip(), "role": role.strip()})

model = "dreamina-seedance-2-0-fast-260128" if args.fast else "dreamina-seedance-2-0-260128"
endpoint = f"{ARK_BASE}/contents/generations/tasks"
headers = {"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"}

content = [{"type": "text", "text": args.prompt}]
for ref in references:
    if ref["type"] == "image":
        content.append({"type": "image_url", "image_url": {"url": ref["url"]}})
    elif ref["type"] == "video":
        content.append({"type": "video_url", "video_url": {"url": ref["url"]}})
body = {
    "model": model,
    "content": content,
    "ratio": args.aspect,
    "duration": args.duration,
    "resolution": args.resolution,
    "watermark": False,
}

print(f"=== BytePlus smoke test ===")
print(f"  model: {model}")
print(f"  prompt: {args.prompt[:100]}{'...' if len(args.prompt)>100 else ''}")
if references:
    for ref in references:
        print(f"  ref ({ref['type']}, role={ref['role']}): {ref['url'][:80]}{'...' if len(ref['url'])>80 else ''}")
else:
    print(f"  refs: (none — text-only)")
print(f"  resolution: {args.resolution}, duration: {args.duration}s, aspect: {args.aspect}")
print(f"  endpoint: {endpoint}")
print()

print(f"Submitting...")
try:
    r = requests.post(endpoint, headers=headers, json=body, timeout=60)
except Exception as e:
    sys.exit(f"  ✗ submit exception: {e}")

if r.status_code != 200:
    print(f"  ✗ submit failed: {r.status_code}")
    print(f"  response: {r.text[:1000]}")
    # Try CN region as fallback
    if "ap-southeast" in ARK_BASE:
        print(f"\n  Singapore region rejected — trying CN region as fallback...")
        cn_endpoint = endpoint.replace("ark.ap-southeast.bytepluses.com", "ark.cn-beijing.volces.com")
        try:
            r = requests.post(cn_endpoint, headers=headers, json=body, timeout=60)
            print(f"  CN region: {r.status_code}")
            if r.status_code == 200:
                print(f"  ✓ CN region works! Update BYTEPLUS_ARK_BASE in .env to:")
                print(f"      BYTEPLUS_ARK_BASE=https://ark.cn-beijing.volces.com/api/v3")
        except Exception as e:
            print(f"  CN region exception: {e}")
    if r.status_code != 200:
        sys.exit(1)

resp = r.json()
task_id = resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")
if not task_id:
    sys.exit(f"  ✗ no task_id in response: {json.dumps(resp)[:500]}")
print(f"  ✓ task_id: {task_id}")

# Poll
print(f"\nPolling (typical 30-180s)...")
poll_endpoint = f"{ARK_BASE}/contents/generations/tasks/{task_id}"
start = time.time()
last_status = None
result = None
while time.time() - start < 600:
    try:
        r = requests.get(poll_endpoint, headers={"Authorization": f"Bearer {ARK_API_KEY}"}, timeout=30)
        if r.status_code != 200:
            print(f"  poll failed: {r.status_code} {r.text[:200]}")
            time.sleep(10)
            continue
        resp = r.json()
        status = resp.get("status") or resp.get("data", {}).get("status")
        if status != last_status:
            print(f"  [{int(time.time()-start)}s] status: {status}")
            last_status = status
        if status in ("succeeded", "completed", "success"):
            result = resp
            break
        if status in ("failed", "expired", "cancelled"):
            sys.exit(f"  ✗ task failed: status={status} resp={json.dumps(resp)[:500]}")
    except Exception as e:
        print(f"  poll exception: {e}")
    time.sleep(15)

if not result:
    sys.exit("  ✗ max wait exceeded")

# Find video URL (BytePlus puts it at content.video_url)
video_url = (result.get("content", {}).get("video_url")
             or result.get("video_url") or result.get("url")
             or result.get("data", {}).get("video_url")
             or result.get("results", {}).get("video_url"))
if not video_url:
    print(f"  ⚠ no video_url found — full response:")
    print(f"  {json.dumps(result, indent=2)[:1500]}")
    sys.exit(1)
print(f"\n  ✓ video ready: {video_url}")

# Download
output_path = Path(args.output) if args.output else Path.home() / "Downloads" / f"byteplus_{args.label}_{task_id[:8]}.mp4"
output_path.parent.mkdir(parents=True, exist_ok=True)
print(f"\nDownloading → {output_path}")
mp4 = requests.get(video_url, timeout=300).content
output_path.write_bytes(mp4)
print(f"  ✓ {output_path.stat().st_size//1024} KB written")

# Log expense
EXPENSE_LOG = HERE / ".byteplus_expense.json"
cost_per_sec = {"480p": 0.05, "720p": 0.08, "1080p": 0.132, "2K": 0.20}.get(args.resolution, 0.132)
if args.fast: cost_per_sec *= 0.5
est_cost = round(cost_per_sec * args.duration, 4)
try:
    log = json.loads(EXPENSE_LOG.read_text()) if EXPENSE_LOG.exists() else {"entries": [], "cumulative_usd": 0.0}
except Exception:
    log = {"entries": [], "cumulative_usd": 0.0}
log["entries"].append({
    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "task_id": task_id, "model": model, "duration": args.duration,
    "resolution": args.resolution, "aspect": args.aspect,
    "label": args.label, "estimated_usd": est_cost,
})
log["cumulative_usd"] = round(sum(e["estimated_usd"] for e in log["entries"]), 2)
EXPENSE_LOG.write_text(json.dumps(log, indent=2))

print(f"\n=== DONE ===")
print(f"  task_id: {task_id}")
print(f"  output:  {output_path}")
print(f"  est cost: ${est_cost}  (cumulative: ${log['cumulative_usd']})")
print(f"\n  open with: open {output_path}")
