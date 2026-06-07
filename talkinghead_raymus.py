#!/usr/bin/env python3
"""talkinghead_raymus.py — Raymus's locked talking-head Seedance gen, two modes:

  • SINGLE mode (default) — fire ONE gen with a supplied audio asset / file.
  • BATCH mode (--voiceover N) — run the full /vidgen-batch pipeline for a VO id:
      upload N chunks → fire N gens in parallel pool → download → ffmpeg concat
      → Whisper-verify dialogue integrity → handoff-ready FINAL.mp4.

LOCKED params (the personal-brand video template — apply to BOTH modes):
  • first frame:   asset-20260512205417-db4ps  (image plate — black sweater, white room)
  • talking head:  asset-20260512182033-pz6xf  (video ref — V1, dialogue mouth shapes)
  • prompt:        mid shot · white studio · diffuse light · content-creator energy
  • resolution:    480p
  • aspect:        9:16
  • duration:      15s (Seedance accepts arbitrary; 15s is canonical batch unit)
  • model:         dreamina-seedance-2-0-260128 (standard, not fast)

Usage:
  # SINGLE mode
  python3 talkinghead_raymus.py --audio asset-XXX [--duration 15] [--no-wait]
  python3 talkinghead_raymus.py --audio /path/to/voice.mp3 [--name "post 01 part 1"]
  python3 talkinghead_raymus.py --audio asset-XXX --prompt "..."  (override prompt)
  python3 talkinghead_raymus.py --no-audio              # silent gen (just visual)

  # BATCH mode (delegates to vidgen_batch.py under the hood)
  python3 talkinghead_raymus.py --voiceover 5          # → VO5 → 05_not-cheap
  python3 talkinghead_raymus.py --voiceover VO1        # → VO1 → 01_creative-industry
  python3 talkinghead_raymus.py --voiceover BTS3       # → VO-BTS3 → BTS-3_manager-choi
  python3 talkinghead_raymus.py --voiceover 11 --pool 5 --dry-run
"""
import argparse, json, sys, subprocess, os
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from byteplus_vidgen import submit_seedance_task, poll_task

# First-frame plate DROPPED 2026-05-14 — db4ps deleted from BytePlus, no longer used in r2v calls.
# Identity now comes purely from PLATE_VIDEO (V3 ref) + audio (per-call). Cleaner, fewer constraints.
PLATE_VIDEO = "asset-20260514122841-q5v2r"   # Talking-head ref V3 (official, 14.9s, 1080x1920 — V1 pz6xf + V2 zzdqj + first-frame plate db4ps all deleted 2026-05-14)
PERSONAL_BRAND_GROUP = "group-20260512182023-fvqm7"

LOCKED_PROMPT = """Mid shot of a man looking directly at camera, speaking like an engaging content creator. He stands in a clean white studio space with soft diffuse lighting wrapping around him evenly. Measured conviction, natural micro-expressions, slight emphasis on key nouns when they land. Sharp focus on face, soft blurred white background. No music, only natural room tone + dialogue.

Dialogue (use the EXACT dialogue and voice from the reference audio):

Identity, face, and expression: drawn from the attached reference video.
Voice and accent: drawn from the attached reference audio (this is the primary signal for vocal characteristics).
9:16 vertical, broadcast-clean, no on-screen text."""


def normalize_audio_ref(audio_arg: str, name_hint: str | None = None) -> str:
    """Return a usable asset:// URL. Upload local files to BytePlus on the fly."""
    if not audio_arg:
        return ""
    if audio_arg.startswith("asset-") or audio_arg.startswith("asset://"):
        return audio_arg if audio_arg.startswith("asset://") else f"asset://{audio_arg}"
    # Otherwise: treat as local file path → upload via Drive → BytePlus Audio asset
    audio_path = Path(audio_arg).expanduser().resolve()
    if not audio_path.exists():
        sys.exit(f"audio not found: {audio_path}")

    # 1) Upload to Drive (public read)
    print(f"  uploading {audio_path.name} → Drive...", flush=True)
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from auth import get_credentials
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    f = drive.files().create(
        body={"name": audio_path.name},
        media_body=MediaFileUpload(str(audio_path), mimetype="audio/mpeg", resumable=True),
        fields="id, name",
    ).execute()
    fid = f["id"]
    drive.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    drive_url = f"https://drive.google.com/uc?export=download&id={fid}"
    print(f"  drive_id={fid}", flush=True)

    # 2) BytePlus create-asset
    print(f"  registering as BytePlus Audio asset...", flush=True)
    label = (name_hint or audio_path.stem)[:60]
    proc = subprocess.run(
        [
            sys.executable, str(HERE / "byteplus_asset_v2.py"),
            "create-asset",
            "--group", PERSONAL_BRAND_GROUP,
            "--url", drive_url,
            "--type", "Audio",
            "--name", label,
            "--wait",
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"asset create failed:\n{proc.stdout}\n{proc.stderr}")
    asset_id = None
    for line in proc.stdout.splitlines():
        if line.startswith("ASSET_ID="):
            asset_id = line.split("=", 1)[1].strip()
            break
    if not asset_id:
        sys.exit(f"couldn't parse asset id from:\n{proc.stdout}")
    print(f"  ✓ asset={asset_id}", flush=True)
    return f"asset://{asset_id}"


def fire_one(audio_ref: str, duration: int = 15, prompt: str | None = None,
             wait: bool = True, label: str = "talking-head") -> dict:
    refs = [
        {"type": "video", "url": f"asset://{PLATE_VIDEO}", "role": "reference_video"},
    ]
    if audio_ref:
        refs.append({"type": "audio", "url": audio_ref, "role": "reference_audio"})

    print(f"[{label}] submit · duration={duration}s · audio={audio_ref or 'none'}", flush=True)
    tid, err = submit_seedance_task(
        prompt=prompt or LOCKED_PROMPT,
        ref_urls=refs,
        aspect_ratio="9:16",
        duration=duration,
        resolution="480p",
        fast=False,
    )
    if err or not tid:
        return {"label": label, "task_id": None, "error": f"submit fail: {err}"}
    print(f"[{label}] task={tid}", flush=True)
    if not wait:
        return {"label": label, "task_id": tid, "polled": False}
    print(f"[{label}] polling...", flush=True)
    result, perr = poll_task(tid, max_wait_sec=1500)
    if perr:
        return {"label": label, "task_id": tid, "error": f"poll fail: {perr}"}
    video_url = result.get("content", {}).get("video_url") if result else None
    seed = result.get("seed") if result else None
    return {"label": label, "task_id": tid, "seed": seed, "video_url": video_url}


def resolve_voiceover(arg: str) -> str:
    """Map a VO id ('1', 'VO5', 'BTS3', 'VO-BTS4', '11') to the audio-take stem."""
    vo_map_path = HERE / "_vo_map.json"
    vo_map = json.loads(vo_map_path.read_text())
    aliases = vo_map["_numeric_aliases"]
    vo_to_stem = vo_map["vo_to_stem"]
    key = str(arg).strip().upper().replace("VOICEOVER", "").strip()
    if key.startswith("VO-"):
        canonical = key
    elif key.startswith("VO"):
        canonical = key
    else:
        canonical = aliases.get(key) or aliases.get(key.upper())
    if not canonical or canonical not in vo_to_stem:
        sys.exit(f"unknown VO id: {arg!r}\n"
                 f"valid: {list(vo_to_stem.keys())}\n"
                 f"or numeric aliases: {list(aliases.keys())}")
    return vo_to_stem[canonical]


def main():
    ap = argparse.ArgumentParser()
    # MODE selectors (mutually exclusive in practice)
    ap.add_argument("--voiceover", help="VO id (e.g. '5', 'VO5', 'BTS3') — runs full BATCH pipeline")
    ap.add_argument("--audio", help="SINGLE mode: asset id, asset:// URL, or local audio path")
    ap.add_argument("--no-audio", action="store_true", help="SINGLE mode: silent gen (no audio ref)")
    # Common
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--prompt", help="override the locked prompt")
    ap.add_argument("--name", help="label (single mode only)")
    ap.add_argument("--no-wait", action="store_true", help="single mode: fire-and-forget")
    # Batch-mode pass-throughs
    ap.add_argument("--pool", type=int, default=3, help="batch mode: concurrent Seedance gens")
    ap.add_argument("--dry-run", action="store_true", help="batch mode: show plan only")
    ap.add_argument("--skip-whisper", action="store_true", help="batch mode: skip verify")
    args = ap.parse_args()

    # ─── BATCH MODE — dispatch to vidgen_batch.py ───
    if args.voiceover:
        stem = resolve_voiceover(args.voiceover)
        print(f"\n→ BATCH mode · voiceover {args.voiceover!r} → stem {stem!r}\n")
        cmd = [sys.executable, str(HERE / "vidgen_batch.py"), stem,
               "--pool", str(args.pool), "--duration", str(args.duration)]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.skip_whisper:
            cmd.append("--skip-whisper")
        rc = subprocess.run(cmd).returncode
        sys.exit(rc)

    # ─── SINGLE MODE ───
    if not args.audio and not args.no_audio:
        sys.exit("Provide one of:\n"
                 "  --voiceover <N>     (batch pipeline — recommended)\n"
                 "  --audio <ref>       (single gen with audio)\n"
                 "  --no-audio          (single gen, silent)")

    audio_ref = "" if args.no_audio else normalize_audio_ref(args.audio, args.name)
    result = fire_one(
        audio_ref=audio_ref,
        duration=args.duration,
        prompt=args.prompt,
        wait=not args.no_wait,
        label=args.name or "talking-head",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
