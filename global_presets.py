#!/usr/bin/env python3
"""global_presets.py — 6 cinematic "global style" presets for the CMS.

A show's GLOBAL is the style preamble prepended to every shot's video prompt —
it lives in the project's `Video Prompts` sheet: B1 = Camera/look, B2 = Audio.
(B3 = Setting stays show-specific: the actual locations/era/geography.)

Today `_create_blank_sot.py` scaffolds a bland placeholder ("Shot with Arri
Alexa. 35mm film look."). These presets let the producer pick a real film look
the moment they create a project in the CMS — the choice is written into B1/B2
so EVERY generated shot inherits it.

Each preset's `camera` text is model-ready (Seedance/film-gen language): camera +
format + lens + grade + lighting + grain. Reference films are named to anchor the
look. Keep them tight — they are PREPENDED to every shot, so verbosity costs.

Used by: build_projects_page.py (the new-project selector) + dash_app/app.py
(/api/new-project → writes B1/B2 of the new sheet).
"""
from __future__ import annotations

GLOBAL_PRESETS = [
    {
        "id": "prestige",
        "name": "Prestige Drama",
        "tagline": "Desaturated, handheld, available-light naturalism",
        "ref": "The Bear · Succession",
        "camera": (
            "Shot on ARRI Alexa, 35mm prime lenses, intimate handheld with subtle "
            "breathing motion. Desaturated muted palette, lifted blacks, restrained "
            "warmth — prestige-TV grade. Available-light realism, soft contrast, fine "
            "film grain. Documentary-naturalistic, no gloss."
        ),
        "audio": (
            "No score. Diegetic sound only — room tone, breath, naturalistic ambience. "
            "Dialogue close, intimate and unprocessed."
        ),
    },
    {
        "id": "warm-cinematic",
        "name": "Warm Cinematic",
        "tagline": "Golden anamorphic studio look, creamy bokeh, halation",
        "ref": "Roger Deakins · Spielberg",
        "camera": (
            "Shot on ARRI Alexa LF, anamorphic lenses, smooth dolly and crane motion. "
            "Warm golden high-contrast film look, rich skin tones, gentle halation and "
            "creamy bokeh. Clean fine grain, classic studio-cinema polish."
        ),
        "audio": (
            "Lush orchestral underscore allowed; full, warm sound design. Dialogue "
            "clear, present and cinematic."
        ),
    },
    {
        "id": "neo-noir",
        "name": "Neo-Noir",
        "tagline": "Low-key, hard pools of light, teal-amber, neon",
        "ref": "Fincher · Blade Runner 2049",
        "camera": (
            "Shot on ARRI Alexa, vintage anamorphic glass, slow deliberate moves and "
            "locked frames. Low-key high-contrast noir — deep crushed shadows, hard "
            "pools of light, teal-and-amber grade with neon accents. Moody, sculpted, "
            "atmospheric haze."
        ),
        "audio": (
            "Sparse, tense ambient drone. Heavy room tone — footsteps, distant city. "
            "Dialogue low, close and weighted."
        ),
    },
    {
        "id": "daylight-realism",
        "name": "Natural Daylight Realism",
        "tagline": "Soft natural light, pastel, tender indie observation",
        "ref": "Aftersun · The Florida Project",
        "camera": (
            "Shot on ARRI Alexa Mini, handheld, intimate and observational, available "
            "light only. Soft natural daylight, gentle pastel palette, true-to-life "
            "skin, minimal grade. Organic, unforced, tender realism."
        ),
        "audio": (
            "No music. Pure diegetic ambience — wind, distant voices, breath. "
            "Naturalistic, unprocessed dialogue."
        ),
    },
    {
        "id": "epic-large-format",
        "name": "Epic Large-Format",
        "tagline": "Alexa 65, sweeping, painterly, monumental scale",
        "ref": "Villeneuve · Dune",
        "camera": (
            "Shot on large-format ARRI Alexa 65, wide spherical primes, sweeping crane "
            "and slow push-ins. Vast painterly imagery, rich controlled palette, deep "
            "atmospheric haze, monumental scale. Immaculate clarity with subtle filmic "
            "texture."
        ),
        "audio": (
            "Deep immersive sound design with a powerful, minimal score. Wide dynamic "
            "range. Dialogue grand yet grounded."
        ),
    },
    {
        "id": "vintage-70s",
        "name": "Vintage 70s Film",
        "tagline": "Period film stock, warm grain, halation, gate weave",
        "ref": "Killers of the Flower Moon · OUaT in Hollywood",
        "camera": (
            "Shot on 35mm with 16mm inserts, period zoom lenses, slightly soft, gentle "
            "handheld. Warm nostalgic film-stock grade — amber highlights, earthy "
            "browns, visible organic grain, subtle gate weave and halation. "
            "Period-authentic, analog."
        ),
        "audio": (
            "Era-appropriate needle-drops or warm analog score; soft tape-textured "
            "ambience. Dialogue warm and present."
        ),
    },
]

# id -> preset, for O(1) lookup from the API handler.
PRESETS_BY_ID = {p["id"]: p for p in GLOBAL_PRESETS}
DEFAULT_PRESET_ID = "prestige"


def get_preset(preset_id: str | None) -> dict:
    """Resolve a preset id to its dict, falling back to the default."""
    return PRESETS_BY_ID.get((preset_id or "").strip().lower(),
                             PRESETS_BY_ID[DEFAULT_PRESET_ID])
