#!/usr/bin/env python3
"""Kling AI API client — JWT-signed requests.

Endpoints + accepted model_name values (verified live 2026-05-18, Singapore region):
  POST /v1/videos/text2video           kling-v3, kling-v2-master
  POST /v1/videos/image2video          kling-v3, kling-v2-master
                                       (single frame; optional image_tail for first+end)
  POST /v1/videos/multi-image2video    kling-v1-6 only (Elements — up to 4 image refs)
  POST /v1/videos/motion-control       kling-v3, kling-v2-6
                                       (char image + motion-ref video; supports elements=[])
  POST /v1/videos/omni-video           kling-video-o1 only
                                       (t2v / i2v / multi-ref / V2V transformation)
  POST /v1/videos/video-effects        (effects)
  GET  /v1/videos/<endpoint>/<task_id> (poll any of the above)
  POST /v1/images/generations          (Kolors text2image)

NOTE: "kling-video-o3" is NOT exposed on any public REST endpoint as of 2026-05-18
— probably powers Kling's web UI "Edit Video" tool. For video-element identity
preservation, use motion-control with an element_id created via
/v1/general/advanced-custom-elements/ (reference_type=video_refer).

Full reference + body schemas + failure modes: KLING_REFERENCE.md (this dir).

Auth: JWT signed with HS256 using KLING_SECRET_KEY.
  Header: typ=JWT, alg=HS256
  Payload: iss=KLING_ACCESS_KEY, exp=now+1800, nbf=now-5

Wallet: per-call billed against Kling account balance.
"""
import os
import sys
import time
import json
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

AK = os.getenv("KLING_ACCESS_KEY")
SK = os.getenv("KLING_SECRET_KEY")
BASE = "https://api-singapore.klingai.com"

if not AK or not SK:
    sys.exit("KLING_ACCESS_KEY / KLING_SECRET_KEY missing in .env")


def make_token() -> str:
    """Build a JWT good for ~30 min."""
    headers = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"iss": AK, "exp": now + 1800, "nbf": now - 5}
    return jwt.encode(payload, SK, algorithm="HS256", headers=headers)


def _request(method: str, path: str, json_body: dict | None = None) -> dict:
    """Signed request. Returns parsed JSON."""
    url = f"{BASE}{path}"
    headers = {
        "Authorization": f"Bearer {make_token()}",
        "Content-Type": "application/json",
    }
    r = requests.request(method, url, headers=headers, json=json_body, timeout=60)
    try:
        return r.json()
    except Exception:
        return {"_status": r.status_code, "_raw": r.text[:1000]}


# === Public helpers ===

def text2video(prompt: str, model: str = "kling-v3",
               duration: int = 5, aspect_ratio: str = "16:9",
               negative_prompt: str = "", cfg_scale: float = 0.5) -> dict:
    """Verified live 2026-05-18 — accepted model_name values:
        "kling-v3"          (default — current SoTA, no video-element support)
        "kling-v2-master"
    Rejected: "kling-v3-master", "kling-video-o3", "kling-video-o1".
    """
    body = {
        "model_name": model,
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
        "cfg_scale": cfg_scale,
    }
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    return _request("POST", "/v1/videos/text2video", body)


def image2video(image_url: str, prompt: str = "",
                image_tail: str | None = None,
                model: str = "kling-v3",
                duration: int = 5, mode: str = "std",
                negative_prompt: str = "", cfg_scale: float = 0.5,
                aspect_ratio: str | None = None) -> dict:
    """Single-frame i2v. Pass image_tail for first→end interpolation.

    image_url / image_tail = publicly fetchable URL or base64 string.

    Verified live 2026-05-18 — accepted model_name values:
        "kling-v3"          (default — best identity / no video-element support)
        "kling-v2-master"
    Rejected: "kling-v3-master", "kling-video-o3".
    """
    body = {
        "model_name": model,
        "image": image_url,
        "prompt": prompt,
        "duration": str(duration),
        "mode": mode,
        "cfg_scale": cfg_scale,
    }
    if image_tail:
        body["image_tail"] = image_tail
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    if aspect_ratio:
        body["aspect_ratio"] = aspect_ratio
    return _request("POST", "/v1/videos/image2video", body)


def multi_image2video(image_list: list[str], prompt: str,
                       model: str = "kling-v1-6",
                       duration: int = 5, aspect_ratio: str = "16:9",
                       mode: str = "std",
                       negative_prompt: str = "",
                       cfg_scale: float = 0.5) -> dict:
    """Kling Elements — up to 4 image refs as named elements.

    Note: as of 2026-05, only kling-v1-6 supports Elements; v2-x not yet.
    """
    if len(image_list) > 4:
        raise ValueError("Elements API accepts at most 4 images")
    body = {
        "model_name": model,
        "image_list": [{"image": img} for img in image_list],
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
        "mode": mode,
        "cfg_scale": cfg_scale,
    }
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    return _request("POST", "/v1/videos/multi-image2video", body)


def motion_control(image_url: str, video_url: str,
                   prompt: str = "",
                   model: str = "kling-v3",
                   character_orientation: str = "image",
                   keep_original_sound: bool = False,
                   mode: str = "std",
                   elements: list[str] | None = None,
                   negative_prompt: str = "") -> dict:
    """Motion Control — transfer motion from video_url onto character in image_url.

    image_url: character ref / scene-still (.jpg/.jpeg/.png, ≤10MB, ≥300px, AR 2:5–5:2).
    video_url: motion ref (.mp4/.mov, ≤100MB, 3–30s, head/shoulders/torso visible).

    character_orientation:
      "image" — match character image orientation. Allows camera moves. Max 10s. (Default.)
      "video" — match motion ref orientation. Richer motion. Max 30s.

    elements: list of element_id strings for face/voice identity preservation.
      Created via create_element_video_refer() / create_element_image_refer().
      Reference in prompt as @Element1, @Element2 etc.

    Validated live 2026-05-18 — strict schema (any deviation → "Failed to
    resolve the request body"):
        model_name              "kling-v3" only (v2-6 / -master / o3 rejected)
        mode                    "std" only (pro rejected on v3)
        character_orientation   "image" or "video" — both work
        keep_original_sound     STRING "yes" / "no" — NOT a Python bool
    Resolution: motion-control output is fixed at std=720p; "resolution"/"size"/
    "quality" params are silently accepted but have no effect.
    """
    body = {
        "model_name": model,
        "image_url": image_url,
        "video_url": video_url,
        "character_orientation": character_orientation,
        "keep_original_sound": "yes" if keep_original_sound else "no",
        "mode": mode,
    }
    if prompt:
        body["prompt"] = prompt
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    if elements:
        body["elements"] = elements
    return _request("POST", "/v1/videos/motion-control", body)


# === Advanced Custom Elements ===
# Endpoint base: /v1/general/advanced-custom-elements/
#
# Confirmed via probing (2026-05-18):
#   GET                → list existing elements (returns {data: [...]})
#   GET /<task_id>     → fetch one element's status/result
#   POST               → create new element (training task)
#
# Required JSON fields (confirmed):
#   element_description : str  — text describing the element's identity
#   element_name        : str  — short name (referenced as @<name> in prompts)
#   reference_type      : "image_refer" | "video_refer"
#
# image_refer mode: 1 frontal image + N additional angle images (refer_images[]).
#   Identity = face/look only.
# video_refer mode: 1 video, 3–8s, 1080P, 16:9 or 9:16, ≤200MB.
#   Identity = face + motion + voice (audio is cloned + added to voice library).
#   ⚠ Downstream gens consuming a video-trained element require kling-video-o3,
#     which is REJECTED on every public REST endpoint as of 2026-05-18.
#   So video_refer elements may TRAIN successfully but be unusable on the public
#   surface until Kling exposes o3. Use image_refer elements + motion-control today.
#
# The exact JSON key for frontal-image / video-list was NOT discovered through
# brute-force probing — many candidates returned "Missing element frontal image"
# or "The number of element videos must be 1". The helpers below pass the
# most-plausible names but accept **extra_fields so you can override once you
# have the real schema (e.g. from the Kling official docs page).

def list_elements() -> dict:
    """List all custom elements on this account."""
    return _request("GET", "/v1/general/advanced-custom-elements/", None)


def get_element(task_id: str) -> dict:
    """Fetch one element's training-task status / result by task_id."""
    return _request("GET", f"/v1/general/advanced-custom-elements/{task_id}", None)


def create_element_image_refer(element_name: str,
                                element_description: str,
                                frontal_image_url: str,
                                refer_image_urls: list[str] | None = None,
                                voice_id: str | None = None,
                                tag_ids: list[str] | None = None,
                                callback_url: str = "",
                                external_task_id: str = "") -> dict:
    """Create an Element from image references (face/look only).

    Schema verified live 2026-05-18 — body shape:
        {
          "element_name": "...",
          "element_description": "...",
          "reference_type": "image_refer",
          "element_image_list": {
            "frontal_image": "<url>",
            "refer_images": [{"image_url": "<url>"}, ...]
          },
          "element_voice_id": "<voice_id>",   # optional
          "tag_list": [{"tag_id": "<tag>"}],   # optional
          ...
        }

    Returns {data: {task_id}} immediately. Poll get_element(task_id) for the
    final element_id (lands in seconds, FREE — verified final_unit_deduction=0).
    """
    body = {
        "element_name": element_name,
        "element_description": element_description,
        "reference_type": "image_refer",
        "element_image_list": {
            "frontal_image": frontal_image_url,
            "refer_images": [{"image_url": u} for u in (refer_image_urls or [])],
        },
        "callback_url": callback_url,
        "external_task_id": external_task_id,
    }
    if voice_id:
        body["element_voice_id"] = voice_id
    if tag_ids:
        body["tag_list"] = [{"tag_id": t} for t in tag_ids]
    return _request("POST", "/v1/general/advanced-custom-elements/", body)


def create_element_video_refer(element_name: str,
                                element_description: str,
                                video_url: str,
                                voice_id: str | None = None,
                                tag_ids: list[str] | None = None,
                                callback_url: str = "",
                                external_task_id: str = "") -> dict:
    """Create an Element from a video reference (face + motion + voice).

    Schema verified live 2026-05-18 — body shape:
        {
          "element_name": "...",
          "element_description": "...",
          "reference_type": "video_refer",
          "element_video_list": {
            "refer_videos": [{"video_url": "<url>"}]
          },
          "element_voice_id": "<voice_id>",   # optional
          "tag_list": [{"tag_id": "<tag>"}],   # optional
          ...
        }

    Source video constraints (verified live 2026-05-18):
      - duration: 3-8s
      - width: 720-2160px (videos <720 wide will be REJECTED on the training
        task with "The video width should not be less than 720px ...")
      - aspect: 16:9 or 9:16 preferred
      - ≤200MB, single clear subject in frame, audio optional (gets cloned)

    Other constraints (HTTP 1201 validation rejects):
      - element_name : 0-20 chars
      - element_description : 0-100 chars

    Returns {data: {task_id}} immediately. Poll get_element(task_id) for the
    final element_id (lands in ~13s, FREE — verified final_unit_deduction=0).
    """
    body = {
        "element_name": element_name,
        "element_description": element_description,
        "reference_type": "video_refer",
        "element_video_list": {
            "refer_videos": [{"video_url": video_url}],
        },
        "callback_url": callback_url,
        "external_task_id": external_task_id,
    }
    if voice_id:
        body["element_voice_id"] = voice_id
    if tag_ids:
        body["tag_list"] = [{"tag_id": t} for t in tag_ids]
    return _request("POST", "/v1/general/advanced-custom-elements/", body)


def omni_video(prompt: str,
               image_urls: list[str] | None = None,
               video_urls: list[str] | None = None,
               refer_type: str = "base",
               keep_original_sound: bool = False,
               model: str = "kling-video-o1",
               mode: str = "pro",
               duration: int = 5,
               aspect_ratio: str | None = None,
               negative_prompt: str = "",
               cfg_scale: float = 0.5) -> dict:
    """Omni-Video (kling-video-o1) — unified multimodal endpoint.

    Three modes (auto-selected by which inputs you pass):

    1. **Text-to-Video** — prompt + aspect_ratio.
    2. **Image-conditioned (Ref2V)** — prompt + image_urls.
       Reference @<<<image_1>>>, <<<image_2>>>… in the prompt.
    3. **Transformation (V2V)** — prompt + video_urls with refer_type="base".
       Reskins the source video while preserving motion / timing / blocking.
       Reference <<<video_1>>> in the prompt. Combine with image_urls to inject
       look refs into a V2V reskin (e.g. "Put the crown from <<<image_1>>> on
       the girl in <<<video_1>>>").

    Args:
        prompt: text instruction; use <<<image_N>>> / <<<video_N>>> to reference inputs.
        image_urls: list of publicly-fetchable image URLs (still refs).
        video_urls: list of publicly-fetchable video URLs (source / motion refs).
        refer_type: "base" = V2V transformation (preserve motion/timing).
                    Other values may exist; "base" is the one verified live.
        keep_original_sound: keep audio track from the source video.
        model: "kling-video-o1" — only model exposed on this endpoint.
        mode: "std" or "pro" — pro is higher quality / more credits.

    Spend: ~4 credits per 5s std output. ~$0.50-0.70 / 5s std, ~$1.00+ pro.
    """
    body = {
        "model_name": model,
        "prompt": prompt,
        "mode": mode,
        "duration": str(duration),
        "cfg_scale": cfg_scale,
    }
    if image_urls:
        body["image_list"] = [{"image_url": u} for u in image_urls]
    if video_urls:
        body["video_list"] = [{
            "video_url": u,
            "refer_type": refer_type,
            "keep_original_sound": "yes" if keep_original_sound else "no",
        } for u in video_urls]
    if aspect_ratio:
        body["aspect_ratio"] = aspect_ratio
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    # Validation: aspect_ratio required when no video_list (V2V inherits from source)
    if not aspect_ratio and not video_urls:
        raise ValueError("aspect_ratio required when no video_urls (V2V inherits from source)")
    return _request("POST", "/v1/videos/omni-video", body)


def get_task(endpoint: str, task_id: str) -> dict:
    """endpoint ∈ {text2video, image2video, multi-image2video, motion-control, omni-video, video-effects}"""
    return _request("GET", f"/v1/videos/{endpoint}/{task_id}")


def poll_task(endpoint: str, task_id: str, max_wait: int = 1800) -> dict:
    """Poll until succeed/failed. Returns the 'data' dict on success.

    data["task_result"]["videos"][0]["url"] is the output MP4 (24h TTL — download promptly).
    """
    start = time.time()
    last = None
    while time.time() - start < max_wait:
        resp = get_task(endpoint, task_id)
        data = resp.get("data", {})
        status = data.get("task_status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status == "succeed":
            return data
        if status == "failed":
            raise RuntimeError(f"task failed: {json.dumps(resp)[:500]}")
        time.sleep(10)
    raise RuntimeError("poll timeout")


def extract_video_url(task_data: dict) -> str | None:
    """Pull the MP4 URL from a poll_task() return value."""
    result = task_data.get("task_result", {})
    videos = result.get("videos") or []
    if videos and isinstance(videos[0], dict):
        return videos[0].get("url")
    return None


if __name__ == "__main__":
    # Sanity check: try to ping any endpoint with a known-empty body to verify auth
    print(f"Access key: {AK[:8]}...{AK[-4:]}")
    print(f"JWT preview: {make_token()[:30]}...")
    # Try listing the account by hitting text2video with empty body (will 400, but auth should be OK)
    r = _request("POST", "/v1/videos/text2video", {})
    print(json.dumps(r, indent=2)[:500])
