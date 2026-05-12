#!/usr/bin/env python3
"""Atomize a locked script into a DearAI v2.2 episode SOT.

Uses Claude Sonnet 4.5 as the atomizer when ANTHROPIC_API_KEY is set —
applies the microdrama-shotlist v2.2 rules (60-80 atomic shots per 90s
pilot, one-action-per-row, dialogue cuts, beat tagging, bible extraction).
Falls back to the heuristic split-by-paragraph atomizer if Anthropic is
unavailable (no key, quota exhausted, network error) so the pipeline
never dead-ends.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import gspread

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore
from _create_blank_sot import shotlist_q_formula, storyboard_body_formula, storyboard_prompt_formula

# ----- Anthropic config -----
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
ANTHROPIC_MAX_TOKENS = 32000  # plenty for 60-80 shots + bible rows in JSON

ATOMIZATION_SYSTEM_PROMPT = """You are a microdrama shotlist atomizer for DearAI Studio.
Your job: take a locked microdrama script and atomize it into a v2.2 shotlist + populate 5 text-only bibles.

# Format target

Output ONE JSON object (no markdown fences, no prose), shape:
{
  "shots": [...],
  "bibles": {
    "characters": [...],
    "locations": [...],
    "props": [...],
    "costumes": [...],
    "effects": [...]
  }
}

# Atomization rules (v2.2 — STRICT)

A 90-second microdrama pilot should produce 60-80 shot rows × 3-4s each = 180-320s of generated footage that the editor cuts down to 60-90s final.

Each shot row must satisfy:
1. ONE action per row. "She picks up the phone" and "He watches her" are TWO rows.
2. ONE subject per row. Don't combine character A's action with character B's reaction in the same row.
3. ONE angle per row. A shot that moves from WS to CU is two rows.
4. Dialogue cuts back-and-forth. Each spoken line gets its own shot row. Insert listener reaction rows between speakers.
5. Duration is exactly 3 or 4 (integer seconds). Never 1, 2, 5+.
6. Use 3 as default; bump to 4 only for slower / held / emotional moments.

# Per-shot JSON schema (each item in shots[])

{
  "shot_num": 1,                       // sequential int
  "duration": 3,                       // 3 or 4
  "shot_type": "MS",                   // CU, MCU, MS, WS, OTS, Insert, POV, ECU
  "camera_movement": "Static",         // Static, Pan R/L, Tilt U/D, Dolly In/Out, Handheld, Tracking, Rack Focus, Whip Pan, Push In, Pull Out
  "merge_candidate": "",               // mostly empty. ~10% rows get a hint like "Merge w/ {earlier shot #}; OTS push-in as she reaches for the phone."
  "description": "Imperative present tense, ONE action, English. e.g. 'Tara's trembling hands grip the chef's knife, knuckles white.'",
  "dialogue": "CHARACTER NAME: line in source language (no English translation here)",  // empty if no speech in this shot
  "tone": "",                          // optional flavor: "soft", "venomous", "panicked"
  "accent": "Jakarta Bahasa",          // per-row accent label
  "microexpression": "Eyes drop; jaw tightens", // only if face visible in the shot
  "sfx": "Knife on cutting board; kitchen ambient",  // short, semicolon-separated
  "props": "Chef's knife; cutting board",
  "brand": "",                         // brand integration if any
  "transition": "Cut",                 // Cut (default), Smash Cut, Fade to Black, Cross Dissolve, etc.
  "beat": "",                          // HOOK on shot 1; JOLT 1-4 at the four story jolts; CLIFF on the final shot; otherwise empty
  "english_translation": ""            // only populated if dialogue isn't already English
}

# Beat coloring

Apply beat tags ONLY on structural peaks:
- shot 1 → "HOOK"
- four JOLT moments across the episode → "JOLT 1", "JOLT 2", "JOLT 3", "JOLT 4"
- final shot → "CLIFF"
- other shots → "" (empty)

# Merge candidates (column "merge_candidate")

~5-15% of rows. Use when ALL of:
- Same continuous space
- Single camera motion
- Not HOOK/JOLT/CLIFF
- Not a dialogue exchange
- Merged runtime fits 3-5 seconds

Format: "Merge w/ {earlier shot #}; {camera move description ending at the current row's subject}."

# Categorization — characters vs effects vs props

Before extracting, decide which bible each item belongs in:

- **characters** — anything that ACTS in the story. Includes humans, creatures, aliens, AIs, animals with agency. If it MOVES on its own intent or REACTS to other characters, it's a character. Don't shove creatures or non-human entities into `effects` just because they're CGI — the alien in scene N is a CHARACTER even if it never speaks.
- **effects** — non-agentic visual phenomena. Steam, fire, light fields, particle systems, environmental ambient (rain, dust, smoke, sparks, water displacement, energy fields). Effects don't have intent.
- **props** — physical objects characters interact with: tools, weapons, vehicles, furniture.
- **costumes** — wearable items attached to a specific character (suit, dress, helmet, mask). Helmet on a character's head = costume; helmet sitting on a shelf = prop.
- **locations** — interior or exterior spaces where action happens.

When unsure between a character and an effect (e.g. "a presence moves in the dark"): if it can be the SUBJECT of a verb other than "moves" or "glows", treat it as a character.

# Bible extraction + INFERENCE

Read the script and extract every named entity. For each, produce a row that the production team can hand straight to an image-generation pipeline — that means every field is populated, not just the ones the script literally describes.

**INFER missing fields from context.** The script often gives a name and a function but no physical description ("Lockers along the walls", "The Brizo's cockpit", "Helmet"). Treat those as starting points and INFER plausible details:

- **Era / setting** — derive from the script's overall world (futuristic underwater research vessel ≠ 1880s Wild West saloon ≠ contemporary Jakarta bistro). Every prop, costume, and location detail should be physically consistent with that world.
- **Character context** — when a character holds, wears, or owns a prop, infer its style from their personality and station (a junior chef's knife = worn, inherited, simple wooden handle; a CEO's pen = lacquered Montblanc-equivalent).
- **Story tone** — a thriller's "mirror" should look battered and shadowed; a romcom's "mirror" should be clean and warmly lit. Match the script's emotional register.
- **Plausibility over invention** — don't make up exotic features the script wouldn't support. A "chair in a bedroom" can be inferred as "wood-frame upholstered chair with worn fabric" (plausible); not "intricately carved Edwardian armchair with hidden compartments" (invented).

Empty fields are only acceptable for fields you genuinely cannot infer (a character's exact height, a prop's brand). For lighting / time-of-day / description / wardrobe / mood / personality / build — always provide a reasoned guess. Mark inferred fields with a leading "~" only if you want to flag uncertainty: e.g. "~mid-30s" for age when the script doesn't say.

The downstream image generator reads the `description` field directly as a prompt. If `description` is empty, the image is skipped. So **every bible row's `description` must be at least one full sentence of physical/visual detail**.

## characters[]

Each item:
{
  "name": "TARA ANJANI",
  "alias": "Tara",
  "role": "Junior chef · protagonist",
  "age": "29",
  "gender": "F",
  "ethnicity": "Indonesian",
  "height": "165cm",
  "weight": "slim, athletic",
  "hair": "long black, tied back",
  "eyes": "dark brown",
  "distinguishing_features": "small scar on left wrist from a kitchen burn",
  "wardrobe": "White chef coat, black trousers, ESD-grip kitchen shoes",
  "signature_prop": "Inherited paring knife from her late mother",
  "personality": "Stoic on the surface, nervous beneath; tries to please",
  "core_theme": "Holding dignity in a system designed to break her",
  "speech_accent": "Jakarta Bahasa with Korean code-switch under pressure",
  "mood_aura": "Quiet grief carried like a second skin",
  "first_shot": "1",
  "notes": "Lead protagonist. Audience POV."
}

## locations[]

Each item:
{
  "name": "Hanbyeol Bistro Kitchen",
  "shot_size": "wide",                 // wide, mid, tight — usually "wide"
  "type": "INT",                       // INT or EXT
  "description": "Modern Korean restaurant kitchen in Senopati district, Jakarta. Stainless steel + tile. Korean signage mixed with Indonesian.",
  "lighting_mood": "Hot service lighting; clinical fluorescents over stations",
  "time_of_day": "Day/Night varies",
  "first_shot": "1",
  "notes": "Primary setting. Shot 1-30."
}

## props[]

Each item:
{
  "name": "Chef's knife",
  "used_by": "Tara",
  "description": "Inherited paring knife — short blade, worn wooden handle. Used in shots 1-21.",
  "first_shot": "1",
  "notes": ""
}

## costumes[]

Each item:
{
  "name": "Sous chef whites (Min-jun)",
  "worn_by": "Min-jun",
  "description": "Crisp white chef coat with double-breasted brass buttons, sous-chef stripe at the cuff.",
  "first_shot": "4",
  "notes": ""
}

## effects[]

Each item:
{
  "name": "Kitchen steam",
  "used_by": "ambient",
  "description": "Diffuse steam over the pass during service.",
  "first_shot": "29",
  "notes": ""
}

# Quality bar

- Atomization MUST hit 60-80 shots for a normal-length microdrama pilot script. Don't undershoot. If the script is sparse, expand action beats into atomic shots (a single sentence "She walks into the kitchen" = 2-3 shots: WS of kitchen, MS of her entering, CU on her reading the room).
- Dialogue must be in SOURCE LANGUAGE in the dialogue field — don't translate to English. Put English in the english_translation field instead if source language ≠ English.
- Microexpressions populated only when a face is visible.
- SFX short, semicolons separating multiple sounds.
- Bibles populated with EVERY named entity found in the script, with reasoned producer-quality detail in each field — INFERRING physical/visual details where the script is silent. Empty `description` is unacceptable; it kills the downstream image generation pipeline.

Output the JSON object directly. No fenced blocks, no commentary. Just the JSON."""

LOCALE_ACCENT_HUMAN = {
    "jakarta": "Jakarta Bahasa Indonesia, with natural Korean / Mandarin / English code-switching depending on the speaker's heritage",
    "manila": "Manila Filipino — primarily Tagalog with natural Taglish code-switching",
    "seoul": "Seoul Korean with natural English code-switching for younger characters",
    "generic": "Natural local accent (English by default unless script implies otherwise)",
}


SHOTLIST_HEADERS_18 = [
    "Shot #", "Duration (s)", "Shot Type", "Camera Movement", "Merge Candidate",
    "Shot Description", "Dialogue/VO", "Tone of Voice", "Accent", "Microexpression",
    "SFX", "Props/Wardrobe", "Brand Integration", "Transition", "Beat",
    "English Translation", "Prompt", "Bahasa Prompt",
]

STORYBOARD_HEADERS = [
    "Set #", "Shot Range", "Storyboard Prompt", "Bahasa Prompt", "Drive Folder",
    "Status", "Iter 1 URL", "Iter 2 URL", "Error",
    "Body", "Bahasa Body", "Location", "Video Iter 1 URL", "Video Iter 2 URL",
]

CHARACTER_HEADERS = [
    "Name", "Alias", "Role / Archetype", "Age", "Gender / Pronouns",
    "Ethnicity / Heritage", "Height", "Weight / Build", "Hair", "Eyes",
    "Distinguishing features", "Wardrobe", "Signature accessory / prop",
    "Personality", "Core theme", "Speech accent", "Mood / aura",
    "First Shot #", "Notes", "Iter 1 URL (white bg)", "Iter 2 URL (white bg)",
    "Status", "Error",
]
LOCATION_HEADERS = [
    "Name", "Shot Size", "Type (INT/EXT)", "Description", "Lighting / Mood",
    "Time of Day", "First Shot #", "Notes", "Prompt", "Iter 1 URL",
    "Iter 2 URL", "Status", "Error", "Feedback", "Aliases",
]
SIMPLE_BIBLE_HEADERS = [
    "Name", "Worn By / Used By", "Description", "First Shot #", "Notes",
    "Prompt", "Iter 1 URL", "Iter 2 URL", "Status", "Error", "Feedback",
]

LOCALE_ACCENT = {
    "jakarta": "Jakarta Bahasa Indonesia with natural code-switching",
    "manila": "Manila Filipino English with natural Tagalog code-switching",
    "seoul": "Seoul Korean with natural English code-switching",
    "generic": "natural local accent",
}


def parse_sheet_id(value: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value or "")
    return match.group(1) if match else (value or "").strip()


def split_units(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) >= 8:
        return blocks
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def dialogue_from(text: str) -> str:
    quotes = re.findall(r'"([^"]{2,220})"', text)
    if quotes:
        return " / ".join(quotes[:2])
    return ""


def clean_description(text: str) -> str:
    text = re.sub(r"^[A-Z0-9 ._-]{1,32}:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text)


def shot_type_for(index: int, total: int) -> str:
    if index == 1:
        return "Establishing wide"
    if index == total:
        return "Cliffhanger close-up"
    return ["Medium shot", "Close-up", "Wide shot", "Tracking shot"][index % 4]


def movement_for(index: int) -> str:
    return ["Static hold", "Slow push-in", "Handheld follow", "Whip pan", "Dolly move"][index % 5]


def atomize(script_text: str, locale: str) -> list[list[str]]:
    """LEGACY heuristic atomizer — fallback only.
    Splits by paragraphs / sentences, generates generic shot type + movement.
    See atomize_with_claude() for the production path."""
    units = split_units(script_text)
    if not units:
        raise SystemExit("Script is empty")
    accent = LOCALE_ACCENT[locale]
    rows = []
    for i, unit in enumerate(units, start=1):
        desc = clean_description(unit)
        rows.append([
            str(i), "3", shot_type_for(i, len(units)), movement_for(i), "",
            desc[:900], dialogue_from(unit), "", accent, "",
            "", "", "", "", "", "",
        ])
    return rows


def _shot_dict_to_row(s: dict, accent_default: str) -> list[str]:
    """Convert Claude's shot JSON dict → the 16-col row the existing
    write_sheet() expects. Order matches SHOTLIST_HEADERS_18 cols A-P
    (cols Q+R are formulas dropped in afterward)."""
    return [
        str(s.get("shot_num", "")),
        str(s.get("duration", "3")),
        s.get("shot_type", ""),
        s.get("camera_movement", ""),
        s.get("merge_candidate", ""),
        (s.get("description", "") or "")[:900],
        s.get("dialogue", ""),
        s.get("tone", ""),
        s.get("accent", "") or accent_default,
        s.get("microexpression", ""),
        s.get("sfx", ""),
        s.get("props", ""),
        s.get("brand", ""),
        s.get("transition", "") or "Cut",
        s.get("beat", ""),
        s.get("english_translation", ""),
    ]


def _bible_row_character(c: dict) -> list[str]:
    return [
        c.get("name", ""), c.get("alias", ""), c.get("role", ""),
        c.get("age", ""), c.get("gender", ""), c.get("ethnicity", ""),
        c.get("height", ""), c.get("weight", ""), c.get("hair", ""),
        c.get("eyes", ""), c.get("distinguishing_features", ""),
        c.get("wardrobe", ""), c.get("signature_prop", ""),
        c.get("personality", ""), c.get("core_theme", ""),
        c.get("speech_accent", ""), c.get("mood_aura", ""),
        c.get("first_shot", ""), c.get("notes", ""),
        "", "",  # Iter 1/2 URL (will be filled by character_generate.py)
        "Pending", "",
    ]


def _bible_row_location(loc: dict) -> list[str]:
    return [
        loc.get("name", ""), loc.get("shot_size", "wide"), loc.get("type", "INT"),
        loc.get("description", ""), loc.get("lighting_mood", ""),
        loc.get("time_of_day", ""), loc.get("first_shot", ""),
        loc.get("notes", ""), "",   # col I = Prompt (formula populated later)
        "", "",  # Iter 1/2 URL
        "Pending", "", "", "",  # Status, Error, Feedback, Aliases
    ]


def _bible_row_simple(item: dict, used_by_key: str = "used_by") -> list[str]:
    return [
        item.get("name", ""), item.get(used_by_key, ""),
        item.get("description", ""), item.get("first_shot", ""),
        item.get("notes", ""), "",  # Prompt formula
        "", "",  # Iter 1/2 URL
        "Pending", "", "",  # Status, Error, Feedback
    ]


def atomize_with_claude(script_text: str, locale: str, show_name: str):
    """Anthropic-powered atomization. Returns (shots, bibles) where shots is
    a list of 16-col row lists and bibles is the 5-tuple of bible row lists.
    Raises on API error so the caller can decide whether to fall back."""
    import anthropic
    client = anthropic.Anthropic()
    accent_default = LOCALE_ACCENT[locale]
    locale_human = LOCALE_ACCENT_HUMAN.get(locale, "Natural local accent")

    user_prompt = f"""Show name: {show_name}
Locale dialect default: {locale_human}

Script:
<script>
{script_text}
</script>

Output the atomized v2.2 shotlist + bibles as a single JSON object per the system prompt schema. Target 60-80 shots. Apply HOOK / JOLT 1-4 / CLIFF beat tags. Extract every named character / location / prop / costume / effect into the bibles. Output JSON only."""

    print(f"[claude] atomizing with {ANTHROPIC_MODEL} (streaming, max_tokens={ANTHROPIC_MAX_TOKENS})...", flush=True)
    t0 = time.time()
    # Use streaming — the SDK refuses non-streaming requests when max_tokens
    # is high enough to potentially run >10 minutes (e.g. 32000 tokens on
    # Sonnet 4.5). Streaming also lets us print incremental progress.
    text_chunks: list[str] = []
    last_progress = time.time()
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=ATOMIZATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            text_chunks.append(chunk)
            # Heartbeat every ~10s so long generations don't look hung in the
            # Render logs.
            if time.time() - last_progress > 10:
                print(f"[claude] streaming… {sum(len(c) for c in text_chunks)} chars so far", flush=True)
                last_progress = time.time()
        final_msg = stream.get_final_message()
    dt = time.time() - t0
    raw = "".join(text_chunks)
    usage = final_msg.usage
    print(f"[claude] {dt:.1f}s · in={usage.input_tokens} out={usage.output_tokens} "
          f"· ≈${(usage.input_tokens * 3 + usage.output_tokens * 15) / 1_000_000:.3f}",
          flush=True)

    # Strip optional ```json fences if Claude added them
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # Save the bad output for inspection
        bad_path = Path("/tmp/shotlist_gen_bad_output.json")
        bad_path.write_text(raw)
        raise RuntimeError(f"Claude returned invalid JSON: {e}. Saved to {bad_path}.")

    shot_dicts = data.get("shots", [])
    if not shot_dicts:
        raise RuntimeError("Claude response missing 'shots' array")
    shots = [_shot_dict_to_row(s, accent_default) for s in shot_dicts]

    bibles_raw = data.get("bibles", {})
    chars = [_bible_row_character(c) for c in bibles_raw.get("characters", [])]
    locs = [_bible_row_location(l) for l in bibles_raw.get("locations", [])]
    props = [_bible_row_simple(p) for p in bibles_raw.get("props", [])]
    costumes = [_bible_row_simple(c, used_by_key="worn_by") for c in bibles_raw.get("costumes", [])]
    effects = [_bible_row_simple(e) for e in bibles_raw.get("effects", [])]

    print(f"[claude] atomized {len(shots)} shots · "
          f"bibles: {len(chars)} chars / {len(locs)} locs / "
          f"{len(props)} props / {len(costumes)} costumes / {len(effects)} fx",
          flush=True)
    return shots, (chars, locs, props, costumes, effects)


def words_by_frequency(text: str) -> list[tuple[str, int]]:
    stop = {"THE", "AND", "WITH", "FROM", "THIS", "THAT", "THEY", "THEIR", "INTO", "WHEN", "WHERE"}
    counts: dict[str, int] = {}
    for token in re.findall(r"\b[A-Z][A-Z0-9'-]{2,}(?:\s+[A-Z][A-Z0-9'-]{2,})?\b", text):
        token = token.strip().upper()
        if token in stop:
            continue
        counts[token] = counts.get(token, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def first_shot_for(name: str, shots: list[list[str]]) -> str:
    pattern = re.compile(rf"\b{re.escape(name)}\b", re.I)
    for row in shots:
        if pattern.search(row[5]) or pattern.search(row[6]):
            return row[0]
    return "1"


def build_bibles(script_text: str, shots: list[list[str]], show_name: str):
    names = [n for n, c in words_by_frequency(script_text) if c >= 2][:12]
    if not names:
        names = [show_name.upper()]
    chars = []
    for name in names[:8]:
        chars.append([
            name, "", "Microdrama character", "", "", "", "", "", "", "",
            "", "Show-appropriate wardrobe", "", "Driven, emotionally readable",
            "Core conflict", "", "Grounded dramatic presence", first_shot_for(name, shots),
            "Auto-extracted from locked script; producer should refine.", "", "", "Pending", "",
        ])
    locations = [[
        "Primary Location", "wide", "INT/EXT", f"Main recurring environment for {show_name}.",
        "Natural cinematic lighting", "", "1",
        "Auto placeholder; producer should rename/refine.", "", "", "", "Pending", "", "", "",
    ]]
    props = []
    for term in [n for n, _ in words_by_frequency(script_text) if n not in names][:12]:
        props.append([term.title(), "", f"Script-mentioned object or production detail: {term}.",
                      first_shot_for(term, shots), "Auto-extracted.", "", "", "", "Pending", "", ""])
    return chars, locations, props, [], []


def formula_columns(headers: list[str]) -> tuple[str, str]:
    prompt_ix = next((i for i, h in enumerate(headers) if h.strip().lower() == "prompt"), 16)
    prompt_col = chr(ord("A") + prompt_ix)
    bahasa_col = chr(ord("A") + prompt_ix + 1)
    return prompt_col, bahasa_col


def ensure_ws(sh, title: str, rows: int, cols: int):
    try:
        ws = sh.worksheet(title)
        ws.resize(rows=max(ws.row_count, rows), cols=max(ws.col_count, cols))
        return ws
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def write_sheet(sheet_id: str, show_name: str, shots: list[list[str]], bibles, dry_run: bool) -> None:
    set_count = math.ceil(len(shots) / 5)
    if dry_run:
        print(f"DRY RUN: would write {len(shots)} shot rows and {set_count} storyboard sets to {sheet_id}")
        for row in shots[:5]:
            print(f"  shot {row[0]}: {row[5][:100]}")
        chars, locs, props, costumes, effects = bibles
        print(f"  bible rows: CHARACTERS={len(chars)} LOCATIONS={len(locs)} PROPS={len(props)} COSTUME={len(costumes)} EFFECTS={len(effects)}")
        return

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(parse_sheet_id(sheet_id))

    shot_ws = ensure_ws(sh, "Shotlist", max(120, len(shots) + 5), 18)
    headers = shot_ws.row_values(1)
    if not headers:
        headers = SHOTLIST_HEADERS_18
        shot_ws.update(range_name="A1:R1", values=[headers], value_input_option="RAW")
    prompt_col, bahasa_col = formula_columns(headers + [""] * 20)
    shot_ws.update(range_name=f"A2:P{len(shots)+1}", values=shots, value_input_option="USER_ENTERED")
    q_values = [[shotlist_q_formula(r)] for r in range(2, len(shots) + 2)]
    r_values = [[f'=IF(A{r}="","",GOOGLETRANSLATE({prompt_col}{r},"en","id"))'] for r in range(2, len(shots) + 2)]
    sh.values_batch_update(body={"valueInputOption": "USER_ENTERED", "data": [
        {"range": f"Shotlist!{prompt_col}2:{prompt_col}{len(shots)+1}", "values": q_values},
        {"range": f"Shotlist!{bahasa_col}2:{bahasa_col}{len(shots)+1}", "values": r_values},
    ]})

    sp = ensure_ws(sh, "Storyboard Prompts", max(50, set_count + 12), 14)
    sp.update(range_name="A10:N10", values=[STORYBOARD_HEADERS], value_input_option="RAW")
    sp_rows = []
    for n in range(1, set_count + 1):
        start, end = (n - 1) * 5 + 1, min(n * 5, len(shots))
        sp_rows.append([str(n), f"{start}-{end}", storyboard_prompt_formula(),
                        f'=IF(A{10+n}="","",GOOGLETRANSLATE(C{10+n},"en","id"))',
                        "", "Pending", "", "", "", storyboard_body_formula(),
                        f'=IF(A{10+n}="","",GOOGLETRANSLATE(J{10+n},"en","id"))',
                        "", "", ""])
    sp.update(range_name=f"A11:N{10+set_count}", values=sp_rows, value_input_option="USER_ENTERED")

    chars, locs, props, costumes, effects = bibles
    ensure_ws(sh, "CHARACTERS", max(50, len(chars) + 2), 23).update(range_name=f"A1:W{len(chars)+1}", values=[CHARACTER_HEADERS] + chars, value_input_option="USER_ENTERED")

    # LOCATIONS — write the rows, THEN inject the Prompt formula in col I.
    # Without this, location_generate.py skips every row with "empty prompt".
    locs_ws = ensure_ws(sh, "LOCATIONS", max(50, len(locs) + 5), 15)
    locs_ws.update(range_name=f"A4:O{len(locs)+4}", values=[LOCATION_HEADERS] + locs, value_input_option="USER_ENTERED")
    if locs:
        loc_prompt_formulas = [
            [(
                f'=IF(A{r}="","","Cinematic photorealistic "&IF(B{r}="","wide ",B{r}&" ")&'
                f'IF(C{r}="","",C{r}&" ")&"shot of "&A{r}&". "&D{r}&'
                f'IF(E{r}=""," "," Lighting: "&E{r}&".")&'
                f'IF(F{r}=""," "," Time: "&F{r}&".")&" No people, no text. 16:9 cinematic.")'
            )] for r in range(5, 5 + len(locs))
        ]
        locs_ws.update(range_name=f"I5:I{4+len(locs)}", values=loc_prompt_formulas, value_input_option="USER_ENTERED")

    # PROPS / COSTUME / EFFECTS — same pattern. Prompt formula in col F.
    # bible_generate.py reads row[5] (col F) as prompt.
    for title, rows, kind in [
        ("PROPS", props, "Studio product photography of "),
        ("COSTUME", costumes, "Costume reference photograph of "),
        ("EFFECTS", effects, "VFX reference image: "),
    ]:
        ws = ensure_ws(sh, title, max(50, len(rows) + 6), 11)
        values = [SIMPLE_BIBLE_HEADERS] + rows if rows else [SIMPLE_BIBLE_HEADERS]
        ws.update(range_name=f"A5:K{len(values)+4}", values=values, value_input_option="USER_ENTERED")
        if rows:
            tail = ("Off-white studio background (light ivory), soft directional lighting, "
                    "no humans, no text, 1:1 square."
                    if title == "PROPS" else
                    "Mannequin or invisible-body display, off-white studio background, "
                    "soft directional lighting, no people, 1:1 square."
                    if title == "COSTUME" else
                    "Isolated effect element on off-white background, no scene context, "
                    "no people, no text, 1:1 square.")
            prop_formulas = [
                [(
                    f'=IF(A{r}="","","{kind}"&A{r}&". "&C{r}&'
                    f'IF(E{r}=""," "," "&E{r}&" ")&"{tail}")'
                )] for r in range(6, 6 + len(rows))
            ]
            ws.update(range_name=f"F6:F{5+len(rows)}", values=prop_formulas, value_input_option="USER_ENTERED")
    print(f"Done: wrote {len(shots)} shots, {set_count} sets, and text bible rows to {sh.title}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", required=True, help="Locked script path")
    ap.add_argument("--sheet", required=True, help="Target episode SOT sheet ID or URL")
    ap.add_argument("--name", required=True, help="Show name")
    ap.add_argument("--locale", default="generic", choices=sorted(LOCALE_ACCENT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--heuristic", action="store_true",
                    help="Force the dumb heuristic atomizer (skip Anthropic). "
                         "Auto-fallback already happens if ANTHROPIC_API_KEY is unset.")
    args = ap.parse_args()

    script_path = Path(args.script).expanduser()
    script_text = script_path.read_text(encoding="utf-8")

    # Atomization path selection:
    #   1. --heuristic flag → force dumb split
    #   2. ANTHROPIC_API_KEY unset → fall back to dumb split with a warning
    #   3. Otherwise → Claude Sonnet 4.5 via Anthropic API
    # The fallback also catches API errors (quota, network) so the pipeline
    # never dead-ends — better to ship a coarse shotlist than nothing.
    use_claude = not args.heuristic and bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    atomizer_used = "claude"
    if not use_claude:
        reason = "user --heuristic flag" if args.heuristic else "ANTHROPIC_API_KEY not set"
        print(f"[atomize] using heuristic atomizer ({reason})", flush=True)
        # Loud banner so it's obvious in the job log + Render logs
        print(f"[atomize] === ATOMIZER=HEURISTIC ({reason}) ===", flush=True)
        shots = atomize(script_text, args.locale)
        bibles = build_bibles(script_text, shots, args.name)
        atomizer_used = f"heuristic ({reason})"
    else:
        try:
            shots, bibles = atomize_with_claude(script_text, args.locale, args.name)
            print(f"[atomize] === ATOMIZER=CLAUDE ({ANTHROPIC_MODEL}) ===", flush=True)
        except Exception as e:
            print(f"[atomize] Claude path failed: {type(e).__name__}: {e}", flush=True)
            print(f"[atomize] === ATOMIZER=HEURISTIC (claude failed: {type(e).__name__}) ===", flush=True)
            shots = atomize(script_text, args.locale)
            bibles = build_bibles(script_text, shots, args.name)
            atomizer_used = f"heuristic (claude failed: {type(e).__name__})"

    print(f"[atomize] final: atomizer={atomizer_used} · shots={len(shots)}", flush=True)
    write_sheet(args.sheet, args.name, shots, bibles, args.dry_run)


if __name__ == "__main__":
    main()
