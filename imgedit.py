#!/usr/bin/env python3
"""
imgedit.py — fire ONE image + an edit instruction to Higgsfield Nano Banana 2
(or any Higgsfield image model) and write back the edited result.

This is the image-EDIT counterpart to blocking_generate.py / storyboard_generate.py:
you hand it a source image and a plain-English edit, it threads the source as the
reference and returns the edited image.

Source image (--image) can be:
  - a local file path                (/path/to/pic.png)
  - a Google Drive share URL         (https://drive.google.com/file/d/<id>/view)
  - a bare Drive file id             (1kr_HKFCiQ-wCAHidGVUAXNSJRET5z8hW)
  - any http(s) image URL            (https://.../pic.jpg)

Usage:
  python3 imgedit.py --image <path|url|id> --prompt "change the sign to 'Darkroom'..." \
      [--model nano_banana_2] [--aspect 16:9] [--resolution 1k] \
      [--out <path>] [--upload]

Notes:
  - Default model is nano_banana_2 (Nano Banana 2 on Higgsfield).
  - --aspect defaults to "auto": the source image's own aspect ratio is detected and
    snapped to the nearest Higgsfield-supported ratio so the frame isn't re-cropped.
  - Output is saved locally (default: ~/Documents/Good Light Generated Videos/_Edits/).
  - --upload also pushes the result to Drive (anyone-with-link reader) and prints the URL.
"""
import argparse
import io
import os
import re
import sys
import time
import tempfile

import higgs_gen

# ---------- input resolution ----------

def _is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s or ""))

def drive_id(url: str):
    m = re.search(r"/d/([A-Za-z0-9_-]+)", url or "") or re.search(r"[?&]id=([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else None

def _looks_like_drive_id(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,}", s or ""))

def resolve_image(arg: str) -> str:
    """Return a local file path for the source image, downloading if needed."""
    # local file
    if os.path.exists(arg):
        return arg
    # http(s) — could be a Drive /view link or a plain image URL
    if _is_url(arg):
        fid = drive_id(arg)
        if fid:
            return _download_drive(fid)
        return _download_http(arg)
    # bare Drive id
    if _looks_like_drive_id(arg):
        return _download_drive(arg)
    raise SystemExit(f"  ✗ could not resolve --image: {arg!r} (not a path, URL, or Drive id)")

def _download_http(url: str) -> str:
    import requests
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    suffix = ".png"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(r.content); tmp.close()
    return tmp.name

def _download_drive(file_id: str) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from auth import get_credentials
    drive = build("drive", "v3", credentials=get_credentials())
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, drive.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = dl.next_chunk()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(buf.getvalue()); tmp.close()
    return tmp.name

# ---------- aspect detection ----------

_SUPPORTED = {
    "1:1": 1.0, "16:9": 16/9, "9:16": 9/16, "4:3": 4/3, "3:4": 3/4,
    "3:2": 3/2, "2:3": 2/3, "21:9": 21/9,
}

def detect_aspect(path: str) -> str:
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        target = w / h
        best = min(_SUPPORTED.items(), key=lambda kv: abs(kv[1] - target))
        return best[0]
    except Exception:
        return "16:9"

# ---------- Drive upload (optional) ----------

EDITS_FOLDER_ENV = "IMGEDIT_DRIVE_FOLDER"  # optional override

def upload_share(name: str, content: bytes) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from auth import get_credentials
    drive = build("drive", "v3", credentials=get_credentials())
    body = {"name": name}
    folder = os.environ.get(EDITS_FOLDER_ENV, "").strip()
    if folder:
        body["parents"] = [folder]
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="image/png", resumable=False)
    f = drive.files().create(body=body, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"},
                               fields="id").execute()
    return f["webViewLink"]

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Edit one image via Higgsfield Nano Banana 2.")
    ap.add_argument("--image", required=True, help="source image: local path, Drive URL/id, or http URL")
    ap.add_argument("--prompt", help="the edit instruction (plain English)")
    ap.add_argument("--model", default="nano_banana_2", help="Higgsfield image model (default nano_banana_2)")
    ap.add_argument("--aspect", default="auto", help="output aspect ratio, or 'auto' to match the source")
    ap.add_argument("--resolution", default="1k", help="1k | 2k (default 1k)")
    ap.add_argument("--out", help="local output path (default: ~/Documents/Good Light Generated Videos/_Edits/)")
    ap.add_argument("--upload", action="store_true", help="also upload result to Drive and print the URL")
    args, extra = ap.parse_known_args()

    # allow prompt as trailing positional text too
    prompt = args.prompt or " ".join(extra).strip()
    if not prompt:
        raise SystemExit("  ✗ no edit prompt given (use --prompt \"...\")")

    src = resolve_image(args.image)
    aspect = detect_aspect(src) if args.aspect == "auto" else args.aspect
    print(f"  source: {args.image}")
    print(f"  local:  {src}")
    print(f"  model:  {args.model}   aspect: {aspect}   resolution: {args.resolution}")
    print(f"  edit:   {prompt[:140]}{'…' if len(prompt) > 140 else ''}")

    t0 = time.time()
    png = higgs_gen.generate(prompt=prompt, model=args.model, aspect_ratio=aspect,
                             resolution=args.resolution, image_ref_path=src)

    out = args.out
    if not out:
        d = os.path.expanduser("~/Documents/Good Light Generated Videos/_Edits")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, f"imgedit_{int(time.time())}.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as f:
        f.write(png)
    print(f"  ✓ {out}  ({len(png)//1024}KB, {time.time()-t0:.1f}s)")

    if args.upload:
        url = upload_share(os.path.basename(out), png)
        print(f"  ↗ Drive: {url}")

if __name__ == "__main__":
    main()
