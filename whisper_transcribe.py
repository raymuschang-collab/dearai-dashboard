#!/usr/bin/env python3
"""Whisper transcription helper for the dearai pipeline.

Bridges both `Shotlist Workflows/` (microdrama production) and `Video Editing/`
(jobs workspace) — symlinked into the latter.

Inputs accepted:
  • Local file path (.mp4 / .mp3 / .m4a / .wav / .ogg / .webm / .flac)
  • Drive file ID (extracted from share URL or pasted as bare ID)
  • Public HTTPS URL (downloaded to /tmp/ first)

Output formats (select via --format):
  • text          → plain transcript
  • srt           → standard subtitle file (NLE / video player ready)
  • vtt           → web subtitle format (HyperFrames / HTML5 video)
  • verbose_json  → timestamped segments + words (for caption tracks, QA)
  • json          → simple JSON wrapper

Auto-handles:
  • Files >25 MB: creates a compressed audio-only copy in /tmp/ via ffmpeg
    (opus 24k mono, suitable for speech) and transcribes that. Original
    untouched.
  • Cost estimate printed before firing — Whisper is $0.006/min audio.

Usage:
  python3 whisper_transcribe.py <input> [flags]

Examples:
  # Local video file → SRT for NLE
  python3 whisper_transcribe.py shot-22.mp4 --format srt --language id

  # Drive file → timestamped JSON for HF captions
  python3 whisper_transcribe.py 1AbC123XyZ --format verbose_json --language id

  # Bahasa-tagged plain transcript
  python3 whisper_transcribe.py promo.mp3 --language id --format text
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHISPER_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-1"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # OpenAI's hard limit per request
COST_PER_MIN = 0.006  # USD


# ─────────────────────────────────────────────────────────────────────────────
# Input resolution: local path | drive id | URL
# ─────────────────────────────────────────────────────────────────────────────

DRIVE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{20,}$")


def is_drive_id(s: str) -> bool:
    return bool(DRIVE_ID_RE.match(s)) and not os.path.exists(s) and "://" not in s


def extract_drive_id(s: str) -> str | None:
    """Pull the file ID out of common Drive URL forms."""
    m = re.search(r"/d/([a-zA-Z0-9_-]{20,})", s)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]{20,})", s)
    if m:
        return m.group(1)
    if is_drive_id(s):
        return s
    return None


def download_drive_file(file_id: str) -> str:
    """Download a Drive file by ID; returns local /tmp/ path."""
    sys.path.insert(0, HERE)
    from auth import get_credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    meta = drive.files().get(fileId=file_id, fields="name,size,mimeType").execute()
    name = meta["name"]
    print(f"  → drive: {name} ({int(meta.get('size', 0)) / 1e6:.1f} MB, {meta.get('mimeType')})")

    out = os.path.join(tempfile.gettempdir(), name)
    req = drive.files().get_media(fileId=file_id)
    with open(out, "wb") as f:
        dl = MediaIoBaseDownload(f, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return out


def download_url(url: str) -> str:
    """Download a public URL to /tmp/."""
    name = url.rstrip("/").split("/")[-1].split("?")[0] or "downloaded"
    out = os.path.join(tempfile.gettempdir(), name)
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return out


def resolve_input(s: str) -> str:
    """Return a local file path regardless of input form."""
    if os.path.exists(s):
        return s
    if "://" in s:
        if "drive.google.com" in s:
            fid = extract_drive_id(s)
            if not fid:
                raise ValueError(f"Could not extract Drive ID from {s}")
            return download_drive_file(fid)
        return download_url(s)
    fid = extract_drive_id(s)
    if fid:
        return download_drive_file(fid)
    raise FileNotFoundError(f"Cannot resolve input: {s}")


# ─────────────────────────────────────────────────────────────────────────────
# ffmpeg helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_audio_duration(path: str) -> float:
    """Return audio duration in seconds via ffprobe."""
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        stderr=subprocess.STDOUT,
    )
    return float(out.decode().strip())


def compress_for_whisper(path: str) -> str:
    """Re-encode to mono opus 24k — small, speech-clean, well under 25 MB."""
    out = os.path.join(tempfile.gettempdir(), Path(path).stem + ".whisper.ogg")
    subprocess.check_call(
        ["ffmpeg", "-y", "-i", path,
         "-vn",                  # drop video
         "-ac", "1",             # mono
         "-ar", "16000",         # 16 kHz (whisper's native rate)
         "-c:a", "libopus",
         "-b:a", "24k",          # speech-optimized bitrate
         out],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Whisper API call
# ─────────────────────────────────────────────────────────────────────────────

def transcribe(path: str, language: str | None, fmt: str, prompt: str | None) -> bytes:
    """Call Whisper API and return raw response body."""
    if not OPENAI_API_KEY:
        sys.exit("✗ OPENAI_API_KEY not set in .env")

    files = {"file": (os.path.basename(path), open(path, "rb"))}
    data = {
        "model": WHISPER_MODEL,
        "response_format": fmt,
    }
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    if fmt == "verbose_json":
        # Get word-level timestamps too — useful for caption tracks
        data["timestamp_granularities[]"] = "word"

    r = requests.post(
        WHISPER_ENDPOINT,
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        files=files,
        data=data,
        timeout=600,
    )
    if r.status_code != 200:
        sys.exit(f"✗ Whisper API HTTP {r.status_code}: {r.text[:300]}")
    return r.content


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Transcribe audio/video via OpenAI Whisper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", help="local path | Drive file ID | Drive share URL | https URL")
    ap.add_argument("--language", "-l", default=None,
                    help="ISO 639-1 code (e.g., 'id' for Bahasa, 'en'). Default: auto-detect.")
    ap.add_argument("--format", "-f", default="srt",
                    choices=["text", "srt", "vtt", "json", "verbose_json"],
                    help="Output format. Default: srt.")
    ap.add_argument("--output", "-o", default=None,
                    help="Output path. Default: <input-stem>.<ext> in same dir.")
    ap.add_argument("--prompt", default=None,
                    help="Optional context to bias transcription (e.g., character names, jargon).")
    ap.add_argument("--no-confirm", action="store_true",
                    help="Skip cost-estimate confirmation prompt.")
    args = ap.parse_args()

    # Step 1: resolve input → local path
    print(f"Input: {args.input}")
    local = resolve_input(args.input)
    size_mb = os.path.getsize(local) / 1e6
    print(f"  local: {local} ({size_mb:.1f} MB)")

    # Step 2: get duration + cost estimate
    try:
        dur = get_audio_duration(local)
    except Exception as e:
        sys.exit(f"✗ ffprobe failed: {e}")
    cost = (dur / 60) * COST_PER_MIN
    print(f"  duration: {dur:.1f}s  est. cost: ${cost:.4f}")

    # Step 3: confirm gate (skip with --no-confirm)
    if not args.no_confirm:
        ans = input(f"  Submit to Whisper API for ~${cost:.4f}? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            sys.exit("  ✗ aborted at confirm gate")

    # Step 4: compress if needed
    upload_path = local
    if size_mb > 25:
        print(f"  > 25 MB — compressing to opus mono for upload...")
        upload_path = compress_for_whisper(local)
        new_size = os.path.getsize(upload_path) / 1e6
        print(f"  compressed: {new_size:.1f} MB")
        if new_size > 25:
            sys.exit(f"✗ compressed file still {new_size:.1f} MB — split into segments first")

    # Step 5: transcribe
    print(f"  submitting to Whisper (language={args.language or 'auto'}, format={args.format})...")
    body = transcribe(upload_path, args.language, args.format, args.prompt)

    # Step 6: write output
    ext_map = {"text": "txt", "srt": "srt", "vtt": "vtt",
               "json": "json", "verbose_json": "json"}
    ext = ext_map[args.format]

    if args.output:
        out_path = args.output
    else:
        # Save next to the original input if it's local; otherwise to /tmp/
        anchor = args.input if os.path.exists(args.input) else local
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(anchor)) or ".",
            Path(anchor).stem + f".{ext}",
        )

    if args.format == "verbose_json":
        # Pretty-print
        with open(out_path, "w") as f:
            json.dump(json.loads(body), f, indent=2, ensure_ascii=False)
    else:
        with open(out_path, "wb") as f:
            f.write(body)

    print(f"\n✓ wrote {out_path} ({os.path.getsize(out_path)} bytes)")
    print(f"  cost: ${cost:.4f}")


if __name__ == "__main__":
    main()
