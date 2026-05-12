#!/usr/bin/env python3
"""Parse uploaded script files into plain UTF-8 text — with episode splitting.

The parser handles two cases:
  1. Single-episode script — returns one blob of text
  2. Multi-episode script — auto-detects boundary markers (e.g.
     "==== EPISODE 2 ====" or just "EPISODE 2 — Title") and returns a list
     of (episode_title, episode_text) tuples, one per episode.

Boundary patterns recognized (case-insensitive, line-anchored):
  - "EPISODE N" / "EP N" / "EPISODE N: Title" / "EP N — Title"
  - Decoration-wrapped variants: "====== EPISODE 2 ======"
  - "Chapter N", "PART N", "ACT N" (less common in microdrama scripts but
    still treated as episode markers)

If the first matched boundary is NOT at position 0, everything BEFORE the
first marker is treated as Episode 1 — so a script that starts with scene
description, then later marks "EPISODE 2", "EPISODE 3" gets split into
3 episodes (the first being everything-before-EPISODE-2).

If no markers are found, returns single-episode mode.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# Match an episode boundary header. The line may have optional decoration
# characters (=, -, *, _) on either side. The episode number can be digits
# or roman numerals. Optional title follows on the same line.
#
# Examples that match (after stripping decoration):
#   EPISODE 1
#   Episode 2 — Title
#   EP 3: Title
#   Episode IV
#   ====== EPISODE 2 ======
#   ---- Episode 1 ----
_EPISODE_BOUNDARY_RE = re.compile(
    r"^\s*[=\-*_\s]*"                          # optional leading decoration
    r"(?:EPISODE|EP|Chapter|PART|ACT)"          # keyword
    r"\s*"
    r"(?P<num>\d+|[IVX]+)"                       # episode number (decimal or roman)
    r"\s*[:\-—]?\s*"                             # optional separator before title
    r"(?P<title>[^=\-*_\n][^\n]*?)?"            # optional title
    r"\s*[=\-*_\s]*$",                          # optional trailing decoration
    re.IGNORECASE | re.MULTILINE,
)


def _roman_to_int(s: str) -> int:
    """Convert roman numerals to int. Returns 0 on failure."""
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    try:
        total = 0
        prev = 0
        for c in reversed(s.upper()):
            v = vals.get(c, 0)
            total = total - v if v < prev else total + v
            prev = v
        return total
    except Exception:
        return 0


def _derive_title_from_text(text: str, episode_num: int) -> str:
    """If no title was extracted from the boundary line, fall back to the
    first scene heading after the boundary. A screenplay scene heading
    looks like 'INT. LOCATION - TIME' or 'EXT. LOCATION - TIME'."""
    scene_re = re.compile(r"^\s*(INT|EXT|INT/EXT)\.?\s+([^\-—\n]+?)(?:\s*[\-—]\s*([^\n]+))?$",
                          re.IGNORECASE | re.MULTILINE)
    m = scene_re.search(text)
    if m:
        loc = m.group(2).strip().title()
        # Trim "The " prefix to keep titles tight ("The Brizo" → "Brizo")
        if loc.lower().startswith("the "):
            loc = loc[4:].strip()
        return loc[:40]  # cap title length
    return f"Episode {episode_num}"


def split_episodes(text: str) -> list[tuple[int, str, str]]:
    """Split text into (episode_num, title, episode_text) tuples.

    Returns a list with at least one entry. If no episode markers exist,
    returns [(1, derived_title, full_text)].
    """
    matches = list(_EPISODE_BOUNDARY_RE.finditer(text))
    if not matches:
        title = _derive_title_from_text(text, 1)
        return [(1, title, text)]

    # Build (episode_num, title, start_pos) for each boundary line.
    # Then add an implicit Episode 1 boundary at pos 0 if the first
    # marker isn't right at the start.
    parsed: list[tuple[int, str, int]] = []
    for m in matches:
        raw_num = m.group("num") or ""
        raw_title = (m.group("title") or "").strip(" :-—=*_")
        # Parse number (decimal or roman)
        try:
            ep_num = int(raw_num)
        except ValueError:
            ep_num = _roman_to_int(raw_num)
        if ep_num == 0:
            continue  # malformed marker, skip
        parsed.append((ep_num, raw_title, m.end()))

    if not parsed:
        title = _derive_title_from_text(text, 1)
        return [(1, title, text)]

    # First match isn't at position 0 → Episode 1 is everything before it
    first_match_start = matches[0].start()
    episodes: list[tuple[int, str, str]] = []
    if first_match_start > 50:  # require non-trivial content before
        ep1_text = text[:first_match_start].strip()
        ep1_title = _derive_title_from_text(ep1_text, 1)
        episodes.append((1, ep1_title, ep1_text))
        # Renumber the parsed list so its first marker becomes Episode 2
        # (only if the marker said EPISODE 2 or higher)
        if parsed[0][0] == 1:
            # Marker said EPISODE 1 — overwrite our implicit one
            episodes.pop()
            # The implicit-ep-1 region is now lost in favor of the explicit marker
            # That's fine — the explicit marker is the source of truth

    # For each parsed marker, slice from its end to the next marker's start
    sorted_starts = [m.start() for m in matches]
    for i, (ep_num, raw_title, content_start) in enumerate(parsed):
        # Find where this episode ends — at the next boundary's start, or EOF
        # The (i+1)th match in `matches` corresponds to this parsed entry's next
        # marker, but parsed[] may have skipped malformed markers; find by position.
        next_start = len(text)
        for s in sorted_starts:
            if s > content_start:
                next_start = s
                break
        ep_text = text[content_start:next_start].strip()
        title = raw_title if raw_title else _derive_title_from_text(ep_text, ep_num)
        episodes.append((ep_num, title, ep_text))

    # De-duplicate by episode number, keeping first occurrence
    seen: set[int] = set()
    deduped: list[tuple[int, str, str]] = []
    for ep_num, title, ep_text in episodes:
        if ep_num in seen:
            continue
        seen.add(ep_num)
        deduped.append((ep_num, title, ep_text))
    deduped.sort(key=lambda x: x[0])
    return deduped


def parse_script(source_path: str, dest_txt_path: str,
                 split_dir: Optional[str] = None) -> dict:
    """Read source_path, write plain text to dest_txt_path.

    If split_dir is given, also auto-detect episode boundaries and write
    one file per episode to that directory as `ep_NN.txt`.

    Returns:
        {
          "text": <full text>,
          "episodes": [(ep_num, title, ep_text), ...],  # always at least one entry
          "episode_paths": [Path("ep_01.txt"), ...] if split_dir else [],
        }
    """
    src = Path(source_path)
    ext = src.suffix.lower()

    if ext in {".txt", ".md"}:
        text = src.read_text(encoding="utf-8")
    elif ext == ".pdf":
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(str(src)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)
    elif ext == ".docx":
        import docx

        doc = docx.Document(str(src))
        text = "\n\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(
            f"unsupported script file extension {ext!r}; use .txt, .md, .docx, or .pdf"
        )

    Path(dest_txt_path).write_text(text, encoding="utf-8")
    episodes = split_episodes(text)
    episode_paths: list[Path] = []
    if split_dir:
        split_root = Path(split_dir)
        split_root.mkdir(parents=True, exist_ok=True)
        for ep_num, _title, ep_text in episodes:
            p = split_root / f"ep_{ep_num:02d}.txt"
            p.write_text(ep_text, encoding="utf-8")
            episode_paths.append(p)

    return {
        "text": text,
        "episodes": episodes,
        "episode_paths": episode_paths,
    }
