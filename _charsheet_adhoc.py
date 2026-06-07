#!/usr/bin/env python3
"""Ad-hoc CHARACTER REFERENCE SHEET — fires Higgsfield gpt_image_2 with the
locked production-bible prompt template (same one used by character_generate.py
when ingesting from a v2.2 Sheet's CHARACTERS bible).

Two modes:
  1. Explicit flags: --name + any of the other 16 bible-field flags
  2. Free-form: --description "<one or more sentences describing the character>"
     The free-form is appended verbatim into a 'distinguishing features' style
     block — best for quick fires where you don't want to fill out 17 fields.

Output: PNG saved to ~/Desktop/Char Sheets/<slug>_v<N>.png and opened in Preview.
"""
import argparse, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import higgs_gen
from character_generate import PROMPT_TEMPLATE

# Load env so higgs CLI has any required tokens
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


DEFAULT_BACKGROUND = "off-white studio background (light ivory tone)"
DEFAULT_OUT_DIR = Path.home() / "Desktop" / "Char Sheets"


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:60].strip("_")


def next_versioned_path(out_dir: Path, slug: str) -> Path:
    """Find the next free vN slot (v1, v2, …) for this character slug."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        p = out_dir / f"{slug}_v{n}.png"
        if not p.exists():
            return p
        n += 1


def build_prompt(fields: dict, background: str) -> str:
    return PROMPT_TEMPLATE.format(
        background=background,
        name=fields.get("name") or "Unnamed",
        alias=fields.get("alias") or "—",
        role=fields.get("role") or "—",
        age=fields.get("age") or "—",
        gender=fields.get("gender") or "—",
        ethnicity=fields.get("ethnicity") or "—",
        height=fields.get("height") or "—",
        build=fields.get("build") or "—",
        hair=fields.get("hair") or "—",
        eyes=fields.get("eyes") or "—",
        distinguishing=fields.get("distinguishing") or "—",
        wardrobe=fields.get("wardrobe") or "—",
        prop=fields.get("prop") or "—",
        personality=fields.get("personality") or "—",
        theme=fields.get("theme") or "—",
        accent=fields.get("accent") or "—",
        mood=fields.get("mood") or "—",
    )


def main():
    ap = argparse.ArgumentParser(description="Ad-hoc character reference sheet via Higgsfield gpt_image_2.")
    # Identity
    ap.add_argument("--name", required=True, help="Character name (required)")
    ap.add_argument("--alias", default=None)
    ap.add_argument("--role", default=None, help="Role / Archetype")
    ap.add_argument("--age", default=None)
    ap.add_argument("--gender", default=None, help="Gender / pronouns")
    ap.add_argument("--ethnicity", default=None, help="Ethnicity / heritage")
    # Build
    ap.add_argument("--height", default=None)
    ap.add_argument("--build", default=None, help="Weight / build")
    ap.add_argument("--hair", default=None)
    ap.add_argument("--eyes", default=None)
    ap.add_argument("--distinguishing", default=None, help="Distinguishing features")
    # Wardrobe
    ap.add_argument("--wardrobe", default=None)
    ap.add_argument("--prop", default=None, help="Signature accessory / prop")
    # Personality / craft
    ap.add_argument("--personality", default=None)
    ap.add_argument("--theme", default=None, help="Core theme")
    ap.add_argument("--accent", default=None, help="Speech accent")
    ap.add_argument("--mood", default=None, help="Mood / aura")
    # Free-form fallback (appended to distinguishing if --distinguishing not set)
    ap.add_argument("--description", default=None,
                    help="Free-form description (used if explicit fields aren't given)")
    # Generation params
    ap.add_argument("--background", default=DEFAULT_BACKGROUND,
                    help=f"Background style (default: {DEFAULT_BACKGROUND!r})")
    ap.add_argument("--aspect", default="16:9", help="Aspect ratio (default 16:9)")
    ap.add_argument("--quality", default="high", help="Higgsfield quality (default high)")
    ap.add_argument("--resolution", default="2k", help="Higgsfield resolution (default 2k)")
    ap.add_argument("--iters", type=int, default=1, help="Iterations to fire (default 1)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                    help=f"Output directory (default {DEFAULT_OUT_DIR})")
    ap.add_argument("--no-open", action="store_true",
                    help="Don't auto-open output in Preview")

    args = ap.parse_args()

    fields = vars(args).copy()
    # If --description is set but --distinguishing is not, route the freeform there
    if args.description and not args.distinguishing:
        fields["distinguishing"] = args.description

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.name)

    prompt = build_prompt(fields, background=args.background)
    print(f"\n=== CHAR SHEET · {args.name} ===")
    print(f"  background: {args.background}")
    print(f"  aspect:     {args.aspect}  ·  quality: {args.quality}  ·  res: {args.resolution}")
    print(f"  iters:      {args.iters}")
    print(f"  out_dir:    {out_dir}")
    print(f"\n--- prompt ({len(prompt)} chars) ---\n{prompt[:600]}{'…' if len(prompt) > 600 else ''}\n")

    saved = []
    for i in range(1, args.iters + 1):
        out_path = next_versioned_path(out_dir, slug)
        t0 = time.time()
        print(f"  ◦ iter {i}/{args.iters} — firing Higgsfield gpt_image_2...", flush=True)
        try:
            png_bytes = higgs_gen.generate(
                prompt=prompt,
                model="gpt_image_2",
                aspect_ratio=args.aspect,
                quality=args.quality,
                resolution=args.resolution,
            )
        except Exception as e:
            print(f"    ✗ {e}")
            continue
        out_path.write_bytes(png_bytes)
        dt = time.time() - t0
        print(f"    ✓ saved → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB · {dt:.1f}s)")
        saved.append(out_path)

    if saved and not args.no_open:
        for p in saved:
            subprocess.run(["open", str(p)])
        subprocess.run(["open", str(out_dir)])

    print(f"\n=== DONE · {len(saved)}/{args.iters} landed ===")


if __name__ == "__main__":
    main()
