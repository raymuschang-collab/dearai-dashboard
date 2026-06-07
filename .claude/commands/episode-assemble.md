---
description: End-to-end episode assembly. Reads Storyboard Prompts, downloads each set's video iter, generates a Remotion project that strings them in shot order. Optional Storyblocks/local-clip substitution for missing sets.
argument-hint: <sheet-id-or-url> [--iter 1|2|3|4] [--render] [--storyblocks-map json] [--max-set N]
---

User wants to assemble all per-set videos into a final episode via Remotion.

Target: `$ARGUMENTS`

If `$ARGUMENTS` is empty, ASK which sheet to target.

## Action — run directly

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 ~/.claude/skills/episode-assemble/assemble.py --sheet "$ARGUMENTS"
```

If user passes additional flags (e.g. `--iter 2`, `--render`, `--storyblocks-map path.json`, `--max-set 12`), pass them through verbatim.

## Pharaoh-specific defaults

For Pharaoh sheet, recommend `--max-set 12` (matches current production scope) and `--iter 1` (slot L = primary).

```bash
python3 ~/.claude/skills/episode-assemble/assemble.py \
  --sheet "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE" \
  --max-set 12 \
  --iter 1
```

This produces `./strike_pharaoh_king_assembly/` (or whatever slug derives from the sheet title).

## After it generates the project

The skill prints next-step bash. The user runs:

```bash
cd <output-dir>
npm install   # one-time
npm run render
# → out/episode.mp4
```

Or pass `--render` to the skill itself to auto-run those commands.

## Final report

One block: show, episode, sets assembled, output dir, optional MP4 path.

## Authentication

Same `auth.py` flow as the other skills.

## Skill reference

Full spec at `~/.claude/skills/episode-assemble/SKILL.md`. Source at `~/.claude/skills/episode-assemble/assemble.py`. Templates at `~/.claude/skills/episode-assemble/templates/`.
