#!/usr/bin/env python3
"""
walking_vlog.py — one-shot Seedance gen for Raymus's walking-talking-head workflow.

LOCKED RECIPE (proved 2026-05-30, HDB-walking gen seed 99904):
  • Video ref (face/voice/scene anchor): outdoor selfie mid-14.9s, NORMAL speed
        default = asset-20260530190201-mgnvk
  • Audio ref (Singapore English voice/accent timbre):
        default = asset-20260526124346-76ss5
  • Prompt scaffold: selfie vlog · walking · SG English · "follow voice ref" · the line
  • Output: 480p · 9:16 · 7s default (5-15 work)

USAGE
    python3 walking_vlog.py \
        --location "walking through a hawker centre at dusk" \
        --say "this is a test of the walking vlog workflow."

    # Optional flags
    --duration 7              # 5 / 7 / 10 / 15 OK
    --name "hawker_test"      # output filename stem (default: walking_vlog)
    --video-ref asset-...     # override the visual ref
    --audio-ref asset-...     # override the voice ref (e.g. different speaker)
    --no-drive                # skip the Drive copy

OUTPUT
    Local: Social Media Posts (Video)/personal-brand/vidgen-batches/_cartest/<name>_<dur>s.mp4
    Drive: My Drive/PocketShow and Raymus Brand/_to-phone-cartest/<name>_<dur>s.mp4
"""
import argparse, sys, urllib.request, shutil
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from byteplus_vidgen import submit_seedance_task, poll_task

# ── locked defaults (proved 2026-05-30) ──
DEFAULT_VIDEO_REF = "asset://asset-20260530190201-mgnvk"   # outdoor mid-14.9s · normal speed
DEFAULT_AUDIO_REF = "asset://asset-20260526124346-76ss5"   # Raymus voice · SG English

OUT_LOCAL = Path("/Users/raymuschang/Desktop/Social Media Posts (Video)/personal-brand/vidgen-batches/_cartest")
OUT_DRIVE = Path("/Users/raymuschang/Library/CloudStorage/GoogleDrive-raymuschang@gmail.com/My Drive/PocketShow and Raymus Brand/_to-phone-cartest")


def build_prompt(location: str, line: str) -> str:
    return (
        f'Selfie-style vlog shot: a man in a blue t-shirt {location}, '
        'talking directly to the camera as he moves — casual content-creator energy, '
        'natural daylight, environmental context visible behind him. '
        'Walking pace with a light handheld bob from steps. Delivery at a natural relaxed pace. '
        'He speaks in a natural Singapore English accent — closely follow the voice reference for '
        'cadence, timbre, and accent. '
        f'He says: "{line}" '
        'Natural conversational delivery with light micro-expressions. '
        'No music, only natural outdoor ambient + footsteps + dialogue.'
    )


def main():
    ap = argparse.ArgumentParser(description="Walking talking-head vlog gen (Seedance 2.0)")
    ap.add_argument("--location", required=True, help='e.g. "walking through an HDB estate"')
    ap.add_argument("--say",      required=True, help="dialogue line")
    ap.add_argument("--duration", type=int, default=7, choices=[5,7,10,15])
    ap.add_argument("--name",     default="walking_vlog", help="output filename stem")
    ap.add_argument("--video-ref", default=DEFAULT_VIDEO_REF, dest="video_ref")
    ap.add_argument("--audio-ref", default=DEFAULT_AUDIO_REF, dest="audio_ref")
    ap.add_argument("--no-drive", action="store_true", help="skip Drive copy")
    args = ap.parse_args()

    OUT_LOCAL.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(args.location, args.say)
    refs = [
        {"type": "video", "url": args.video_ref, "role": "reference_video"},
        {"type": "audio", "url": args.audio_ref, "role": "reference_audio"},
    ]

    print(f"\n→ Walking-vlog gen · {args.duration}s · 480p · 9:16")
    print(f"  location: {args.location}")
    print(f"  line:     \"{args.say}\"")
    print(f"  video:    {args.video_ref}")
    print(f"  voice:    {args.audio_ref}\n")

    tid, err = submit_seedance_task(
        prompt=prompt, ref_urls=refs,
        aspect_ratio="9:16", duration=args.duration,
        resolution="480p", fast=False,
    )
    if not tid:
        sys.exit(f"submit failed: {err}")
    print(f"  task_id={tid} · polling...")

    result, perr = poll_task(tid, max_wait_sec=1800)
    if perr or not result:
        sys.exit(f"poll failed: {perr}")

    vurl = result.get("content", {}).get("video_url")
    seed = result.get("seed")
    if not vurl:
        sys.exit("no video_url in result")

    dest = OUT_LOCAL / f"{args.name}_{args.duration}s.mp4"
    print(f"  downloading → {dest.name}")
    urllib.request.urlretrieve(vurl, dest)

    print(f"\n  ✓ seed={seed}")
    print(f"  ✓ local: {dest}")

    if not args.no_drive:
        OUT_DRIVE.mkdir(parents=True, exist_ok=True)
        drive_dest = OUT_DRIVE / dest.name
        shutil.copy(dest, drive_dest)
        print(f"  ✓ drive: {drive_dest.name} (sync ~30s)")


if __name__ == "__main__":
    main()
