#!/usr/bin/env python3
"""vidgen_repair.py — per-chunk hybrid repair of a vidgen batch.

For each chunk in <stem>:
  1. Whisper-transcribe the rendered Seedance mp4 (per chunk, not the concat)
  2. Compare to the source chunk's clean audio transcript via fuzzy match
  3. If similarity ≥ threshold (default 0.75): KEEP the Seedance gen
  4. If similarity < threshold: SUBSTITUTE with [held still image + source audio]
                                (a placeholder for HyperFrames motion-graphics fill)
  5. Concat everything → <stem>_HYBRID.mp4
  6. Whisper-verify final coverage

The held still defaults to a frame extracted from the FIRST good chunk of the batch
(neutral mid-shot of Raymus) so the bridge looks like a hold, not a cut to black.
"""
import argparse, json, os, subprocess, sys, re
from pathlib import Path
from difflib import SequenceMatcher
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")

TAKES_DIR = Path("/Users/raymuschang/Documents/Social Media Posts (Video)/personal-brand/script-audio-takes")
VIDGEN_DIR = Path("/Users/raymuschang/Documents/Social Media Posts (Video)/personal-brand/vidgen-batches")


def whisper_words(audio_or_video_path: Path, cache_suffix: str = "_whisper.json") -> dict:
    cache = audio_or_video_path.parent / f"{audio_or_video_path.stem}{cache_suffix}"
    if cache.exists():
        return json.loads(cache.read_text())
    if not API_KEY:
        sys.exit("OPENAI_API_KEY missing")
    # Extract audio if video
    if audio_or_video_path.suffix.lower() in {".mp4", ".mov"}:
        audio = audio_or_video_path.with_name(f"{audio_or_video_path.stem}.verify.mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_or_video_path),
                        "-vn", "-c:a", "libmp3lame", "-b:a", "192k", "-ac", "1", "-ar", "44100",
                        str(audio)], check=True)
    else:
        audio = audio_or_video_path
    with open(audio, "rb") as f:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": (audio.name, f, "audio/mpeg")},
            data={"model": "whisper-1", "response_format": "verbose_json",
                  "timestamp_granularities[]": "word", "language": "en"},
            timeout=600,
        )
        r.raise_for_status()
        result = r.json()
    cache.write_text(json.dumps(result, indent=2))
    return result


def normalize(text: str) -> list[str]:
    return [re.sub(r"[^\w']", "", w.lower()) for w in text.split() if re.sub(r"[^\w']", "", w.lower())]


def similarity(src_text: str, rnd_text: str) -> float:
    """SequenceMatcher ratio on token streams — punishes hallucinations + drops."""
    src = normalize(src_text)
    rnd = normalize(rnd_text)
    if not src:
        return 0.0
    return SequenceMatcher(None, src, rnd).ratio()


def grab_anchor_frame(seedance_clips: list[Path], out_png: Path) -> Path:
    """Pull a frame from the first available clip to use as the 'held' still for bad chunks."""
    if not seedance_clips:
        sys.exit("no Seedance clips to extract an anchor frame from")
    src = seedance_clips[0]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5",
                    "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out_png)],
                   check=True)
    return out_png


def make_audio_only_clip(audio_mp3: Path, still_png: Path, out_mp4: Path):
    """Build a video that's still_png + audio_mp3, duration matched to audio."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(still_png),
        "-i", str(audio_mp3),
        "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=496:864:force_original_aspect_ratio=increase,crop=496:864",
        "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out_mp4),
    ], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", help="post stem (e.g. '01_creative-industry')")
    ap.add_argument("--threshold", type=float, default=0.75,
                    help="fuzzy similarity below this = SUBSTITUTE with source-audio bridge")
    ap.add_argument("--dry-run", action="store_true", help="show plan, don't render")
    args = ap.parse_args()

    stem = args.stem
    batch_dir = VIDGEN_DIR / stem
    if not batch_dir.exists():
        sys.exit(f"batch dir not found: {batch_dir}")

    # Find all chunk pairs: seedance_clip + source_audio
    seedance_clips = sorted(batch_dir.glob(f"{stem}_part*.mp4"))
    seedance_clips = [p for p in seedance_clips if "FINAL" not in p.name and "HYBRID" not in p.name]
    source_audios = sorted(TAKES_DIR.glob(f"{stem}_clean_part*.mp3"))
    if len(seedance_clips) != len(source_audios):
        print(f"⚠ count mismatch: {len(seedance_clips)} clips vs {len(source_audios)} audio chunks")
    n = min(len(seedance_clips), len(source_audios))

    print(f"\n=== Repair · {stem} · {n} chunks · threshold={args.threshold} ===\n")

    # Per-chunk analysis
    decisions = []
    for i in range(n):
        clip = seedance_clips[i]
        src_aud = source_audios[i]
        rnd = whisper_words(clip, cache_suffix="_whisper.json")
        src = whisper_words(src_aud, cache_suffix="_whisper.json")
        rnd_text = rnd.get("text", "")
        src_text = src.get("text", "")
        sim = similarity(src_text, rnd_text)
        decision = "KEEP" if sim >= args.threshold else "REPLACE"
        decisions.append({"i": i + 1, "clip": clip, "src_audio": src_aud,
                          "similarity": round(sim, 3), "decision": decision,
                          "src_text": src_text, "rnd_text": rnd_text})
        print(f"  part {i+1:02d}  sim={sim:.2f}  [{decision}]")
        if decision == "REPLACE":
            print(f"      SRC: {src_text[:120]}")
            print(f"      RND: {rnd_text[:120]}")

    keep = sum(1 for d in decisions if d["decision"] == "KEEP")
    replace = sum(1 for d in decisions if d["decision"] == "REPLACE")
    print(f"\n  → {keep} KEEP · {replace} REPLACE (use source-audio bridge)")
    if args.dry_run:
        return

    # Anchor frame for substitutions
    keep_clips = [d["clip"] for d in decisions if d["decision"] == "KEEP"]
    if not keep_clips:
        print("⚠ no good clips to anchor from — using first chunk anyway")
        keep_clips = [decisions[0]["clip"]]
    anchor_png = batch_dir / "_anchor_frame.png"
    grab_anchor_frame(keep_clips, anchor_png)
    print(f"\n  anchor still: {anchor_png.name}")

    # Build substitute clips
    print(f"\n  building substitutes...")
    for d in decisions:
        if d["decision"] == "REPLACE":
            out = batch_dir / f"{stem}_part{d['i']:02d}_BRIDGE.mp4"
            make_audio_only_clip(d["src_audio"], anchor_png, out)
            d["use_clip"] = out
            print(f"    part {d['i']:02d}: BRIDGE built → {out.name}")
        else:
            d["use_clip"] = d["clip"]

    # ffmpeg concat
    list_path = batch_dir / "_hybrid_concat.txt"
    list_path.write_text("\n".join(f"file '{d['use_clip']}'" for d in decisions) + "\n")
    hybrid_mp4 = batch_dir / f"{stem}_HYBRID.mp4"
    # Re-encode to normalize codecs/timestamps across mixed sources
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        str(hybrid_mp4),
    ], check=True)
    print(f"\n  ✓ {hybrid_mp4.name} ({hybrid_mp4.stat().st_size/1e6:.1f} MB)")

    # Whisper-verify hybrid
    print(f"\n  Whisper-verifying hybrid output...")
    hybrid_whisper = whisper_words(hybrid_mp4, cache_suffix="_hybrid_whisper.json")
    hybrid_text = hybrid_whisper.get("text", "")
    # Full source = concat of all per-chunk source texts
    full_src = " ".join(d["src_text"] for d in decisions)
    sim_full = similarity(full_src, hybrid_text)
    print(f"  hybrid coverage vs source: {sim_full*100:.1f}%")

    # Save audit log
    audit = {
        "stem": stem,
        "threshold": args.threshold,
        "decisions": [
            {"part": d["i"], "decision": d["decision"], "similarity": d["similarity"],
             "use_clip": str(d["use_clip"]), "src_text": d["src_text"], "rnd_text": d["rnd_text"]}
            for d in decisions
        ],
        "hybrid_coverage_vs_source": round(sim_full * 100, 1),
        "hybrid_file": str(hybrid_mp4),
    }
    (batch_dir / "_repair_audit.json").write_text(json.dumps(audit, indent=2))
    print(f"  ✓ audit: _repair_audit.json")
    print(f"\n=== DONE · {hybrid_mp4} ===")


if __name__ == "__main__":
    main()
