#!/usr/bin/env python3
"""Split every X-Men generation MP4 into per-shot clips.

For each generation under ~/Documents/X-men/Generated Videos/<seq>/:
  - read the sheet to get the shot # / type / planned duration for that seq
  - scale planned durations proportionally to the actual MP4 runtime (15s)
  - ffmpeg-cut clips, one per shot, with fast keyframe-aware re-encode

Output:
  ~/Documents/X-men/Working/sequence_1/   (Seq01_Gym)
  ~/Documents/X-men/Working/sequence_2a/  (Seq02a_Climb_Shots09-13)
  ~/Documents/X-men/Working/sequence_2b/  (Seq02b_Climb_Shots13-19)

Naming: {seq_short}_{gen}_shot-{NN}_{type}.mp4
        e.g. seq1_v3-iter1_shot-03_Insert.mp4
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import gspread
from auth import get_credentials

SHEET_ID = "1oex57Ula_gWLTYHRosXgDxzZJlK_ZOO7T-Kx3syIOEw"
GEN_ROOT = Path("/Users/raymuschang/Documents/X-men/Generated Videos")
WORK_ROOT = Path("/Users/raymuschang/Documents/X-men/Working")

# seq folder name -> (work-folder name, shot # range, short tag)
SEQ_MAP = {
    "Seq01_Gym":                 ("sequence_1",  range(1, 9),   "seq1"),
    "Seq02a_Climb_Shots09-13":   ("sequence_2a", range(9, 14),  "seq2a"),
    "Seq02b_Climb_Shots13-19":   ("sequence_2b", range(13, 20), "seq2b"),
}


def gen_tag(mp4_name: str) -> str:
    """Map filename suffix to a short generation tag."""
    s = mp4_name
    if "_v3_iter1" in s:
        return "v3-iter1"
    if "_v3_iter2" in s:
        return "v3-iter2"
    if "_v2" in s:
        return "v2"
    return "v1"


def get_duration_s(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(mp4)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


def main():
    # ---- read shotlist ----
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("Shotlist")
    rows = ws.get("A2:L100")
    shots = []
    for r in rows:
        r += [""] * (12 - len(r))
        if not r[0].strip():
            continue
        try:
            n = int(r[0])
        except ValueError:
            continue
        try:
            dur = float(r[2])
        except ValueError:
            dur = 3.0
        shots.append({
            "num": n,
            "seq": r[1].strip(),
            "dur": dur,
            "type": r[3].strip() or "Shot",
            "desc": r[5].strip(),
        })

    # group shots by # for fast lookup
    shot_by_num = {s["num"]: s for s in shots}

    manifest = []

    for seq_dir in sorted(GEN_ROOT.iterdir()):
        if not seq_dir.is_dir() or seq_dir.name not in SEQ_MAP:
            continue
        work_name, shot_range, seq_short = SEQ_MAP[seq_dir.name]
        out_dir = WORK_ROOT / work_name
        out_dir.mkdir(parents=True, exist_ok=True)

        seq_shots = [shot_by_num[n] for n in shot_range if n in shot_by_num]
        planned_total = sum(s["dur"] for s in seq_shots)
        if planned_total <= 0:
            print(f"!! {seq_dir.name}: no planned durations; skipping")
            continue

        for mp4 in sorted(seq_dir.glob("*.mp4")):
            actual = get_duration_s(mp4)
            scale = actual / planned_total
            tag = gen_tag(mp4.name)
            print(f"\n→ {seq_dir.name} / {mp4.name} ({actual:.2f}s, scale={scale:.3f})")

            t0 = 0.0
            for s in seq_shots:
                seg = s["dur"] * scale
                t1 = min(t0 + seg, actual)
                clip_name = (
                    f"{seq_short}_{tag}_shot-{s['num']:02d}_{sanitize(s['type'])}.mp4"
                )
                clip_path = out_dir / clip_name
                # fast re-encode for clean keyframe-accurate cuts (libx264 preset veryfast)
                # input seek + duration; -avoid_negative_ts to clean up; copy audio if present
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-ss", f"{t0:.3f}", "-i", str(mp4),
                    "-t", f"{(t1 - t0):.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-avoid_negative_ts", "make_zero",
                    str(clip_path),
                ]
                try:
                    subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"   ✗ shot {s['num']}: {e}")
                    continue
                print(f"   ✓ shot {s['num']:02d} [{t0:5.2f}-{t1:5.2f}] -> {clip_name}")
                manifest.append({
                    "seq": seq_dir.name,
                    "work_folder": work_name,
                    "gen": tag,
                    "shot": s["num"],
                    "type": s["type"],
                    "desc": s["desc"],
                    "t0": round(t0, 3),
                    "t1": round(t1, 3),
                    "source": str(mp4),
                    "clip": str(clip_path),
                })
                t0 = t1

    mf = WORK_ROOT / "clips_manifest.json"
    mf.write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote manifest: {mf}")
    print(f"Total clips: {len(manifest)}")


if __name__ == "__main__":
    main()
