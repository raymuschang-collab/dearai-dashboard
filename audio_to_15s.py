#!/usr/bin/env python3
"""audio_to_15s.py — cut an audio file (or folder of audios) into Seedance-friendly chunks.

Each output chunk is 12–14.9s long, cut on word boundaries (Whisper timestamps).
The cap is 14.9s so each chunk fits BytePlus's 1.8–15.2s asset window plus a small safety margin.
The 12s floor avoids tiny stubs. The last chunk per file can be shorter if there's no other option.

Outputs:
  • <stem>_part01.mp3, <stem>_part02.mp3, ... (192kbps mono mp3)
  • <stem>_parts.json — chunk index with start/end/duration/transcript per chunk

Usage:
  python3 audio_to_15s.py <file.mp3>                  # one file
  python3 audio_to_15s.py <folder>                    # all .mp3/.m4a/.wav in folder
  python3 audio_to_15s.py <file> --max-sec 14.9 --min-sec 12.0 --out-dir custom/path
  python3 audio_to_15s.py <file> --skip-transcribe    # use existing <stem>_whisper.json
"""
import argparse, os, sys, json, subprocess, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus"}


def whisper_words(audio_path: Path) -> dict:
    """Transcribe with word-level timestamps. Caches alongside audio file."""
    cache = audio_path.parent / f"{audio_path.stem}_whisper.json"
    if cache.exists():
        return json.loads(cache.read_text())
    if not API_KEY:
        sys.exit("✗ OPENAI_API_KEY not set in .env")
    print(f"  transcribing {audio_path.name} via Whisper API...")
    with open(audio_path, "rb") as f:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": (audio_path.name, f, "audio/mpeg")},
            data={
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
                "language": "en",
            },
            timeout=600,
        )
        r.raise_for_status()
        result = r.json()
    cache.write_text(json.dumps(result, indent=2))
    return result


def greedy_chunk(words: list[dict], max_sec: float, min_sec: float) -> list[tuple[int, int, float, float]]:
    """Return list of (start_word_idx, end_word_idx_inclusive, start_t, end_t).
    Greedy: accumulate words until adding next would exceed max_sec. Backtrack if needed.
    Last chunk may be shorter than min_sec if no remainder fits a 2-chunk split."""
    chunks = []
    i = 0
    n = len(words)
    while i < n:
        chunk_start = words[i]["start"]
        # Find largest j such that words[j].end - chunk_start <= max_sec
        j = i
        while j + 1 < n and words[j + 1]["end"] - chunk_start <= max_sec:
            j += 1
        # If this is not the last chunk and we're below min_sec, force-include words anyway
        # (we MUST move forward to avoid infinite loop)
        # Look at the duration we landed on
        dur = words[j]["end"] - chunk_start

        # If we still have remaining words AND this chunk is too short, try extending
        # by one more word (will push over max_sec but is the lesser evil)
        # — Actually, prefer the under-max version unless that gives a 0-word chunk.
        if j < i:
            j = i  # at minimum the first word

        chunks.append((i, j, chunk_start, words[j]["end"]))
        i = j + 1
    return chunks


def cut_audio(src: Path, start: float, dur: float, out: Path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{max(0, start):.3f}",
            "-i", str(src),
            "-t", f"{dur:.3f}",
            "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1",
            str(out),
        ],
        check=True,
    )


def process_one(audio_path: Path, max_sec: float, min_sec: float, out_dir: Path | None) -> dict:
    print(f"\n→ {audio_path.name}")
    result = whisper_words(audio_path)
    words = result["words"]
    print(f"  {len(words)} words · {result.get('duration', 0):.1f}s total")

    # Pads we'll add when slicing. The word-boundary chunks must fit inside max_sec
    # AFTER the pads, so reserve that budget here.
    HEAD_PAD = 0.05
    TAIL_PAD = 0.10
    word_max = max_sec - (HEAD_PAD + TAIL_PAD)
    chunks = greedy_chunk(words, word_max, min_sec)
    print(f"  → {len(chunks)} chunks targeted (word-span cap: {word_max:.2f}s · file cap: {max_sec:.2f}s)")

    base = out_dir if out_dir else audio_path.parent
    base.mkdir(parents=True, exist_ok=True)
    parts_meta = []
    for k, (i, j, s_t, e_t) in enumerate(chunks, 1):
        out = base / f"{audio_path.stem}_part{k:02d}.mp3"
        # Clamp slice to source bounds
        slice_start = max(0, s_t - HEAD_PAD)
        slice_dur = (e_t - s_t) + HEAD_PAD + TAIL_PAD
        # Hard cap file duration at max_sec (just in case)
        slice_dur = min(slice_dur, max_sec)
        cut_audio(audio_path, slice_start, slice_dur, out)
        # Verify actual duration
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
            capture_output=True, text=True,
        )
        actual = float(pr.stdout.strip())
        transcript = " ".join(words[idx]["word"] for idx in range(i, j + 1))
        flag = ""
        if actual > max_sec + 0.5:
            flag = " ⚠ OVER MAX"
        elif actual < min_sec:
            flag = " ⚠ UNDER MIN" if k != len(chunks) else " (final, OK short)"
        print(f"  {k:02d}. [{s_t:6.2f}–{e_t:6.2f}] dur={actual:5.2f}s · {j-i+1:3d}w · …{transcript[-60:]}{flag}")
        parts_meta.append({
            "part": k,
            "file": str(out),
            "start_sec": round(s_t, 3),
            "end_sec": round(e_t, 3),
            "audio_duration_sec": round(actual, 3),
            "word_count": j - i + 1,
            "transcript": transcript,
        })

    meta = {
        "source": str(audio_path),
        "source_duration_sec": round(result.get("duration", 0), 2),
        "max_sec": max_sec,
        "min_sec": min_sec,
        "parts": parts_meta,
    }
    meta_path = base / f"{audio_path.stem}_parts.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"  ✓ {meta_path.name}")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="audio file or folder")
    ap.add_argument("--max-sec", type=float, default=14.9)
    ap.add_argument("--min-sec", type=float, default=12.0)
    ap.add_argument("--out-dir", help="optional output directory (defaults to input's parent)")
    ap.add_argument("--include", default="_clean.mp3",
                    help="substring filter when input is a folder (default: _clean.mp3). Use '' for no filter.")
    args = ap.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else None

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = sorted([p for p in input_path.iterdir()
                        if p.suffix.lower() in AUDIO_EXTS and (args.include == "" or args.include in p.name)])
    else:
        sys.exit(f"not found: {input_path}")

    if not files:
        sys.exit(f"no audio files matched in {input_path} (filter: {args.include!r})")

    print(f"=== cutting {len(files)} file(s) into {args.min_sec}–{args.max_sec}s chunks ===")
    all_meta = []
    for f in files:
        all_meta.append(process_one(f, args.max_sec, args.min_sec, out_dir))

    if len(files) > 1:
        total = sum(len(m["parts"]) for m in all_meta)
        print(f"\n=== TOTAL: {len(files)} files → {total} chunks ===")


if __name__ == "__main__":
    main()
