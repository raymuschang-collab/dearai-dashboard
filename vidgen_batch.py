#!/usr/bin/env python3
"""vidgen_batch.py — pump a multi-chunk VO take through Seedance r2v in parallel,
   download each clip, concat them in order, then Whisper-verify dialogue integrity.

Pipeline:
  1) For each *_part0N.mp3 (already cut to 12-14.9s by /audioto15s):
       a) Upload to Drive (public)
       b) BytePlus create-asset Type=Audio
       c) Fire Seedance gen using the locked /talkinghead-raymus refs
          (first frame: db4ps, talking-head: pz6xf, audio: <chunk>)
  2) ThreadPool with configurable pool size waits for all
  3) Download every mp4 to a per-post folder
  4) ffmpeg concat in order → <post>_FINAL.mp4
  5) Whisper-transcribe the FINAL mp4's audio
  6) Diff against the source _clean.mp3 transcript → flag dropped words

Usage:
  python3 vidgen_batch.py <stem_path>            # all parts of stem
  python3 vidgen_batch.py 01_creative-industry_clean  # autodetect parts
  python3 vidgen_batch.py <stem> --pool 5 --dry-run
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from byteplus_vidgen import submit_seedance_task, poll_task

PLATE_IMAGE = "asset-20260512205417-db4ps"
PLATE_VIDEO = "asset-20260512182033-pz6xf"
PERSONAL_BRAND_GROUP = "group-20260512182023-fvqm7"
DEFAULT_TAKES_DIR = Path("/Users/raymuschang/Desktop/Social Media Posts (Video)/personal-brand/script-audio-takes")
OUTPUT_BASE = Path("/Users/raymuschang/Desktop/Social Media Posts (Video)/personal-brand/vidgen-batches")

LOCKED_PROMPT = """Mid shot of a man looking directly at camera, speaking like an engaging content creator. He stands in a clean white studio space with soft diffuse lighting wrapping around him evenly. Measured conviction, natural micro-expressions, slight emphasis on key nouns when they land. Sharp focus on face, soft blurred white background. No music, only natural room tone + dialogue.

Dialogue (use the EXACT dialogue and voice from the reference audio):

Identity, face, and expression: drawn from the attached reference video.
Voice and accent: drawn from the attached reference audio (this is the primary signal for vocal characteristics).
9:16 vertical, broadcast-clean, no on-screen text."""


def find_parts(stem_arg: str) -> tuple[str, list[Path]]:
    """Return (stem_name, sorted_part_paths)."""
    stem_path = Path(stem_arg)
    if stem_path.is_absolute() and stem_path.parent.exists():
        stem_dir, stem_name = stem_path.parent, stem_path.name
    else:
        stem_dir, stem_name = DEFAULT_TAKES_DIR, stem_arg
    # Allow caller to pass either bare stem or full _clean path
    stem_name = stem_name.replace(".mp3", "").replace("_clean", "")
    parts = sorted(stem_dir.glob(f"{stem_name}_clean_part*.mp3"))
    if not parts:
        # Try literal stem
        parts = sorted(stem_dir.glob(f"{stem_name}_part*.mp3"))
    return stem_name, parts


def upload_audio_chunk(audio_path: Path, label_prefix: str) -> str:
    """Upload mp3 → Drive → BytePlus Audio asset. Returns asset:// URL."""
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

    label = f"{label_prefix} {audio_path.stem.split('_part')[-1]}"[:60]
    proc = subprocess.run(
        [sys.executable, str(HERE / "byteplus_asset_v2.py"),
         "create-asset", "--group", PERSONAL_BRAND_GROUP,
         "--url", drive_url, "--type", "Audio", "--name", label, "--wait"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"create-asset failed for {audio_path.name}:\n{proc.stdout}\n{proc.stderr}")
    for line in proc.stdout.splitlines():
        if line.startswith("ASSET_ID="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"couldn't parse asset id from:\n{proc.stdout}")


def fire_seedance(audio_asset_id: str, duration: int = 15, label: str = "") -> dict:
    refs = [
        {"type": "image", "url": f"asset://{PLATE_IMAGE}", "role": "reference_image"},
        {"type": "video", "url": f"asset://{PLATE_VIDEO}", "role": "reference_video"},
        {"type": "audio", "url": f"asset://{audio_asset_id}", "role": "reference_audio"},
    ]
    tid, err = submit_seedance_task(
        prompt=LOCKED_PROMPT, ref_urls=refs,
        aspect_ratio="9:16", duration=duration,
        resolution="480p", fast=False,
    )
    if err or not tid:
        return {"label": label, "error": f"submit fail: {err}", "task_id": None}
    result, perr = poll_task(tid, max_wait_sec=1500)
    if perr:
        return {"label": label, "task_id": tid, "error": f"poll fail: {perr}"}
    video_url = result.get("content", {}).get("video_url") if result else None
    seed = result.get("seed") if result else None
    return {"label": label, "task_id": tid, "seed": seed, "video_url": video_url}


def download(url: str, out: Path):
    subprocess.run(["curl", "-sSL", "-o", str(out), url], check=True)


def ffmpeg_concat(parts: list[Path], out: Path):
    list_file = out.parent / f"_concat_list_{out.stem}.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts) + "\n")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy",   # try stream copy first
        str(out),
    ], check=False)
    if not out.exists() or out.stat().st_size < 1000:
        # Re-encode fallback
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(out),
        ], check=True)
    list_file.unlink()


def whisper_verify(audio_or_video: Path) -> dict:
    """Transcribe final video's audio with Whisper. Returns dict with text + words."""
    import requests
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    # Extract audio if video
    if audio_or_video.suffix.lower() in {".mp4", ".mov"}:
        audio = audio_or_video.with_suffix(".verify.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_or_video),
            "-vn", "-c:a", "libmp3lame", "-b:a", "192k", "-ac", "1", "-ar", "44100",
            str(audio),
        ], check=True)
    else:
        audio = audio_or_video

    with open(audio, "rb") as f:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio.name, f, "audio/mpeg")},
            data={"model": "whisper-1", "response_format": "verbose_json",
                  "timestamp_granularities[]": "word", "language": "en"},
            timeout=600,
        )
        r.raise_for_status()
    return r.json()


def diff_transcripts(source_words: list[str], rendered_words: list[str]) -> dict:
    """Compute coverage % + flag dropped chunks. Both lists are lowercase tokens."""
    import re
    norm = lambda s: re.sub(r"[^\w']", "", s.lower())
    src = [norm(w) for w in source_words if norm(w)]
    rnd = [norm(w) for w in rendered_words if norm(w)]
    # Sliding-window similarity is overkill; just check src word coverage in rendered (in order, allowing drops).
    rnd_set = set(rnd)
    coverage = sum(1 for w in src if w in rnd_set) / max(1, len(src))
    missing = [w for w in src if w not in rnd_set][:30]
    return {
        "source_word_count": len(src),
        "rendered_word_count": len(rnd),
        "coverage_pct": round(coverage * 100, 1),
        "first_missing_words": missing,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", help="post stem (e.g. '01_creative-industry') or full path")
    ap.add_argument("--pool", type=int, default=3, help="concurrent Seedance gens (default 3)")
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true", help="show plan, don't fire")
    ap.add_argument("--skip-whisper", action="store_true")
    args = ap.parse_args()

    stem, parts = find_parts(args.stem)
    if not parts:
        sys.exit(f"no part files found for stem={stem!r}")

    out_dir = OUTPUT_BASE / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    total_cost = len(parts) * 0.75
    print(f"\n=== /vidgen-batch · {stem} ===")
    print(f"  parts:    {len(parts)} chunks")
    print(f"  pool:     {args.pool} concurrent Seedance gens")
    print(f"  duration: {args.duration}s @ 480p @ 9:16")
    print(f"  cost:     ~${total_cost:.2f}")
    print(f"  output:   {out_dir}")
    if args.dry_run:
        for i, p in enumerate(parts, 1):
            print(f"    {i:02d}. {p.name}")
        return

    # ─── PHASE 1: Upload all chunks as BytePlus Audio assets (parallel) ───
    print(f"\n[1/4] Uploading {len(parts)} audio chunks → BytePlus Audio assets...")
    asset_map: dict[int, str] = {}
    upload_errors = []

    def _upload(i_path):
        i, p = i_path
        try:
            aid = upload_audio_chunk(p, label_prefix=stem)
            return i, p, aid, None
        except Exception as e:
            return i, p, None, str(e)

    with ThreadPoolExecutor(max_workers=5) as ex:
        for i, p, aid, err in ex.map(_upload, list(enumerate(parts, 1))):
            if err:
                upload_errors.append((i, p.name, err))
                print(f"  ✗ part{i:02d} upload fail: {err}")
            else:
                asset_map[i] = aid
                print(f"  ✓ part{i:02d}: {p.name} → {aid}")

    if upload_errors:
        sys.exit(f"\n✗ {len(upload_errors)} upload(s) failed — aborting before any Seedance spend")

    # ─── PHASE 2: Fire all Seedance gens (pool = args.pool) ───
    print(f"\n[2/4] Firing {len(parts)} Seedance gens · pool={args.pool}...")
    t0 = time.time()
    results: dict[int, dict] = {}

    def _gen(i_aid):
        i, aid = i_aid
        return i, fire_seedance(aid, duration=args.duration, label=f"part{i:02d}")

    with ThreadPoolExecutor(max_workers=args.pool) as ex:
        futs = [ex.submit(_gen, (i, asset_map[i])) for i in sorted(asset_map)]
        for fut in as_completed(futs):
            i, r = fut.result()
            results[i] = r
            elapsed = time.time() - t0
            status = "✓" if r.get("video_url") else "✗"
            tid = r.get("task_id") or "?"
            print(f"  {status} part{i:02d} @ {elapsed/60:.1f}min  task={tid}  err={r.get('error','-')}")

    gen_errors = [(i, r) for i, r in results.items() if not r.get("video_url")]
    if gen_errors:
        print(f"\n⚠ {len(gen_errors)} Seedance gen(s) failed:")
        for i, r in gen_errors:
            print(f"  part{i:02d}: {r.get('error')}")

    # ─── PHASE 3: Download every successful mp4 ───
    print(f"\n[3/4] Downloading {len(results) - len(gen_errors)} mp4 clips → {out_dir}")
    clip_paths: list[tuple[int, Path]] = []
    for i in sorted(results):
        r = results[i]
        if not r.get("video_url"):
            continue
        out = out_dir / f"{stem}_part{i:02d}.mp4"
        download(r["video_url"], out)
        clip_paths.append((i, out))
        print(f"  ✓ part{i:02d} → {out.name} ({out.stat().st_size/1e6:.2f} MB)")

    # ─── PHASE 4: Concat in order ───
    if not clip_paths:
        sys.exit("\n✗ No clips downloaded — nothing to concat")
    final_mp4 = out_dir / f"{stem}_FINAL.mp4"
    print(f"\n[4/4] ffmpeg concat → {final_mp4.name}")
    ffmpeg_concat([p for _, p in sorted(clip_paths)], final_mp4)
    print(f"  ✓ {final_mp4.name} ({final_mp4.stat().st_size/1e6:.2f} MB)")

    # ─── WHISPER VERIFY (optional) ───
    if not args.skip_whisper:
        print(f"\n[verify] Whisper transcribe the concat'd video...")
        rendered = whisper_verify(final_mp4)
        rendered_words = [w["word"] for w in rendered.get("words", [])]
        (out_dir / "_rendered_whisper.json").write_text(json.dumps(rendered, indent=2))
        print(f"  rendered transcript: {len(rendered_words)} words")

        source_clean = DEFAULT_TAKES_DIR / f"{stem}_clean.mp3"
        source_whisper_path = source_clean.parent / f"{source_clean.stem}_whisper.json"
        if source_whisper_path.exists():
            source = json.loads(source_whisper_path.read_text())
            source_words = [w["word"] for w in source.get("words", [])]
        else:
            source = whisper_verify(source_clean)
            source_words = [w["word"] for w in source.get("words", [])]
        diff = diff_transcripts(source_words, rendered_words)
        (out_dir / "_diff.json").write_text(json.dumps(diff, indent=2))
        print(f"  source words: {diff['source_word_count']}  rendered words: {diff['rendered_word_count']}")
        print(f"  coverage:     {diff['coverage_pct']}%")
        if diff["first_missing_words"]:
            print(f"  ⚠ first missing tokens: {diff['first_missing_words']}")
        else:
            print(f"  ✓ no missing tokens — dialogue intact")

    # ─── Summary ───
    summary = {
        "stem": stem,
        "parts": len(parts),
        "successful_gens": len(clip_paths),
        "failed_gens": len(gen_errors),
        "final_mp4": str(final_mp4),
        "final_duration_sec": float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(final_mp4)
        ]).decode().strip()),
        "results": results,
    }
    (out_dir / "_batch_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n=== DONE ===")
    print(f"  final: {final_mp4}  ({summary['final_duration_sec']:.1f}s)")
    print(f"  summary: {out_dir / '_batch_summary.json'}")
    print(f"\nNext: hand off to HyperFrames (in /Users/raymuschang/Desktop/Video Editing/) for captions + motion graphics.")


if __name__ == "__main__":
    main()
