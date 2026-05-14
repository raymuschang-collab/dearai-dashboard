---
description: Pull up the floating Dear.AI microdrama concept registry — active ideas + archived. Active set currently: DRY COUNTRY, MAID, FIVE BOROUGHS.
argument-hint: [slug] (optional — narrow to one idea, e.g. /microdramaideas pembantu)
---

User invoked /microdramaideas. Args: `$ARGUMENTS`

## Action

Read `dearai_microdrama_ideas.json` at the project root and pretty-print the floating concept registry.

Display format:

1. **Active ideas first** — each gets a full card:
   - Title (EN + ID)
   - Status
   - One-line tagline (EN)
   - Genre + lead + setting
   - Dopamine engine summary
   - Key cast (collapsed list, ~5 names)
   - Ensemble image link if present
   - Why team likes it
   - Scale ("microdrama only" / "scales to limited series")
2. **Archived ideas** at the bottom in a compact list — slug + reason archived.
3. If `$ARGUMENTS` is non-empty, treat it as a slug filter — show ONLY that idea with full detail (also pulling Bahasa tagline, full cast, notes).

## Bash

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
"/Users/raymuschang/Desktop/Shotlist Workflows/.venv-transcribe/bin/python3" << 'PY'
import json
import sys

with open("dearai_microdrama_ideas.json") as f:
    data = json.load(f)

args = """$ARGUMENTS""".strip()
ideas = data.get("ideas", [])
archived = data.get("archived", [])

if args:
    # Single-idea mode
    match = [i for i in ideas if i["slug"] == args.lower()]
    if not match:
        match = [i for i in archived if i["slug"] == args.lower()]
    if not match:
        print(f"No idea with slug={args!r}. Active slugs: {[i['slug'] for i in ideas]}")
        sys.exit(0)
    i = match[0]
    print(f"# {i['title_en']}" + (f" · {i.get('title_id','')}" if i.get('title_id') else ""))
    print(f"\n**Status:** {i.get('status','?')}")
    print(f"\n**EN:** {i.get('tagline_en','')}")
    print(f"\n**ID:** {i.get('tagline_id','')}")
    print(f"\n**Genre:** {i.get('genre','')}")
    print(f"\n**Lead:** {i.get('lead','')}")
    print(f"\n**Setting:** {i.get('setting','')}")
    print(f"\n**Dopamine engine:** {i.get('dopamine_engine','')}")
    print(f"\n**Cast:**")
    for c in i.get("key_cast", []):
        print(f"  - {c}")
    if i.get("ensemble_image"):
        print(f"\n**Ensemble image:** {i['ensemble_image']}")
    print(f"\n**Why team:** {i.get('why_team','')}")
    print(f"\n**Scale:** {i.get('scale','')}")
    if i.get("notes"):
        print(f"\n**Notes:** {i['notes']}")
else:
    print(f"# Dear.AI Microdrama Idea Registry\n")
    print(f"*Last updated: {data['_meta'].get('last_updated','?')} · {len(ideas)} active · {len(archived)} archived*\n")
    print("---\n")
    for i in ideas:
        title = f"**{i['title_en']}**"
        if i.get("title_id"):
            title += f" · *{i['title_id']}*"
        print(f"### {title}  `[{i.get('status','?')}]`\n")
        print(f"> {i.get('tagline_en','')}\n")
        print(f"- **Genre:** {i.get('genre','')}")
        print(f"- **Lead:** {i.get('lead','')}")
        print(f"- **Setting:** {i.get('setting','')}")
        print(f"- **Dopamine engine:** {i.get('dopamine_engine','')[:200]}{'...' if len(i.get('dopamine_engine',''))>200 else ''}")
        cast = i.get("key_cast", [])
        if cast:
            cast_preview = ", ".join(c.split(" (")[0] for c in cast[:6])
            if len(cast) > 6:
                cast_preview += f" +{len(cast)-6} more"
            print(f"- **Cast:** {cast_preview}")
        if i.get("ensemble_image"):
            print(f"- **Ensemble:** [{i['slug']}_ensemble]({i['ensemble_image']})")
        print(f"- **Why team:** {i.get('why_team','')}")
        print(f"- **Scale:** {i.get('scale','')}")
        print(f"- **Slug:** `{i['slug']}` — run `/microdramaideas {i['slug']}` for full detail")
        print()
    if archived:
        print("---\n")
        print(f"## Archived (compact)\n")
        for a in archived:
            print(f"- **{a['title_en']}** (`{a['slug']}`) — {a.get('reason_archived','')}")
PY
```

## Adding a new idea

Edit `dearai_microdrama_ideas.json` and append to `ideas[]`. Same schema as existing entries. The skill auto-picks it up next call.

## Moving an idea to archived

Move the entry from `ideas[]` to `archived[]`, drop the heavier fields (cast, dopamine_engine, etc.) and add a `reason_archived` field.
