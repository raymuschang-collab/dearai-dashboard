#!/usr/bin/env python3
"""Kling OmniVideo (kling-video-o1) Ref2V — Julia in a Newtsuit, 2 shots.

Shot A: submarine corridor, tracking MCU dolly-out, 9:16.
Shot B: hydroponic bay, side MCU working plants, 16:9.

Identity = julia_id.jpg (frontal crop). image_1 = Julia, image_2 = location plate.
"""
import json, os, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from kling_api import omni_video
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

JULIA = HERE / "Brizio/Tests/_kling_omni/julia_id.jpg"
SUB   = Path("/Users/raymuschang/Documents/Shotlist Workflows/Brizio/Tests/hf_20260527_014710_242cef7a-861d-48bc-bdda-a752d899e9df.png")
HYDRO = Path("/Users/raymuschang/Documents/Shotlist Workflows/Brizio/Tests/hf_20260527_015314_f5f7855c-bedc-43be-aec6-eca1ce0b1279.png")

NEG = "CGI, 3D render, video game, unreal engine, plastic skin, cartoon, anime, over-smooth, glossy, movie poster, airbrushed, waxy"

PROMPT_A = """Documentary editorial cinematography. A tracking medium close-up that slowly dollies out, following a woman head-on as she works her way through the cramped interior of a submarine. Her face and identity exactly match <<<image_1>>> — same facial structure, features, skin tone, dark hair with blunt bangs. She wears a realistic hard-shell atmospheric diving suit (Newtsuit-style articulated ADS): bulky aluminium pressure shell, rotary joints at shoulders and elbows, domed helmet with a round viewport, scuffed and used. She angles her body to squeeze through the tight passage. Environment and lighting come from <<<image_2>>>: claustrophobic submarine interior, riveted steel bulkheads, exposed pipes, valves and gauges, low ceiling, narrow corridor. Match the lighting of <<<image_2>>> exactly — its color temperature, pooled overhead/console key light, instrument glow and deep shadow falloff. Camera: stabilised tracking MCU, steady continuous dolly-out as she advances, shallow depth of field, anamorphic lens, Arri Alexa. Documentary editorial photography aesthetic, natural skin texture with visible pores and small imperfections, Kodak Portra 400 color science, subtle film grain, muted palette, practical light only."""

PROMPT_B = """Documentary editorial cinematography. A side medium close-up, profile framing, of a woman tending plants in a hydroponic grow bay. Her face and identity exactly match <<<image_1>>> — same facial structure, features, skin tone, dark hair with blunt bangs. She wears a realistic hard-shell atmospheric diving suit (Newtsuit-style articulated ADS): bulky aluminium pressure shell, rotary joints at shoulders and elbows, domed helmet with a round viewport, scuffed and used. She reaches into the racks, working the leaves and stems. Environment and lighting come from <<<image_2>>>: tiered hydroponic racks, NFT channels, nutrient tubing, lush green growth under grow-lamps. Match the lighting of <<<image_2>>> exactly — its color temperature, magenta/white LED grow-light wash, glistening water and humid haze, shadow falloff. Camera: locked side MCU with a slow drift, shallow depth of field, anamorphic lens, Arri Alexa. Documentary editorial photography aesthetic, natural skin texture with visible pores and small imperfections, Kodak Portra 400 color science, subtle film grain, practical light only."""


def upload(drive, parent, p: Path, name: str) -> str:
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    f = drive.files().create(
        body={"name": name, "parents": [parent]},
        media_body=MediaFileUpload(str(p), mimetype=mime),
        fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    return f"https://lh3.googleusercontent.com/d/{f['id']}=w2048"


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Omni Inputs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    parent = found[0]["id"] if found else drive.files().create(
        body={"name": "Kling Omni Inputs", "mimeType": "application/vnd.google-apps.folder"}, fields="id"
    ).execute()["id"]

    print("Uploading refs to Drive…")
    julia_url = upload(drive, parent, JULIA, "julia_id.jpg")
    sub_url   = upload(drive, parent, SUB,   "submarine_plate.png")
    hydro_url = upload(drive, parent, HYDRO, "hydroponic_plate.png")
    print("  julia :", julia_url)
    print("  sub   :", sub_url)
    print("  hydro :", hydro_url)

    out = {}

    print("\n>>> Firing Shot A — submarine corridor (9:16)…")
    ra = omni_video(prompt=PROMPT_A, image_urls=[julia_url, sub_url],
                    model="kling-video-o1", mode="pro", duration=5,
                    aspect_ratio="9:16", negative_prompt=NEG, cfg_scale=0.5)
    print(json.dumps(ra, ensure_ascii=False))
    out["shotA"] = ra

    print("\n>>> Firing Shot B — hydroponic bay (16:9)…")
    rb = omni_video(prompt=PROMPT_B, image_urls=[julia_url, hydro_url],
                    model="kling-video-o1", mode="pro", duration=5,
                    aspect_ratio="16:9", negative_prompt=NEG, cfg_scale=0.5)
    print(json.dumps(rb, ensure_ascii=False))
    out["shotB"] = rb

    (HERE / ".kling_omni_julia_tasks.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("\nSaved task ids → .kling_omni_julia_tasks.json")


if __name__ == "__main__":
    main()
