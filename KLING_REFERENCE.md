# Kling AI API — Reference

Live as of 2026-05-18. Verified against `api-singapore.klingai.com`.

Source-of-truth client: `kling_api.py` (this directory).

---

## Auth — JWT HS256

Every request needs a fresh JWT (≤30 min TTL) signed with `KLING_SECRET_KEY`.

```
Header:  { "alg": "HS256", "typ": "JWT" }
Payload: { "iss": KLING_ACCESS_KEY, "exp": now+1800, "nbf": now-5 }
Send as: Authorization: Bearer <jwt>
```

Keys live in `.env`:
```
KLING_ACCESS_KEY=...
KLING_SECRET_KEY=...
```

Token regenerated per request inside `kling_api._request()` — never cache JWTs across processes.

---

## Base URL

```
https://api-singapore.klingai.com
```

(Singapore region. Kling also exposes `api.klingai.com` for global — use Singapore unless you have a reason not to.)

---

## Endpoints — 3 the user asked about

### 1. **Element / Multi-Image-to-Video** — `POST /v1/videos/multi-image2video`

"Kling Elements" — up to **4 images** stand in as named characters / props / scenes; the prompt describes how they interact. Use when you have crisp still references and want the model to compose a scene from them.

**Body:**
```json
{
  "model_name": "kling-v1-6",          // only v1-6 supports Elements as of 2026-05; v2-x not yet
  "image_list": [                       // 1–4 images. URLs or base64.
    {"image": "https://..."},
    {"image": "https://..."}
  ],
  "prompt": "<= 2500 chars describing action / scene / interaction",
  "negative_prompt": "optional",
  "duration": "5",                      // "5" or "10" (string)
  "aspect_ratio": "16:9",               // "16:9" | "9:16" | "1:1"
  "mode": "std",                        // "std" or "pro"
  "cfg_scale": 0.5,                     // 0.0–1.0, prompt adherence
  "callback_url": "optional webhook"
}
```

**Spend:** ~$0.35–0.70 per 5s std, ~$0.70–1.40 per 10s pro (varies by region).

**Use case for Channel 8 / Underwater:**
- Character emperor + minister + princess + throne-room location image as 4 elements → "the emperor enters the underwater throne room flanked by his court" prompt.

---

### 2. **Motion Control** — `POST /v1/videos/motion-control`

Transfers motion from a **reference video** onto a **reference image** (scene-still / character anchor). Keeps the visual look from the image; copies the body motion + framing from the video.

**Body — verified live 2026-05-18:**
```json
{
  "model_name": "kling-v3",             // ACCEPTED: "kling-v3" (default, SoTA) or "kling-v2-6". Suffixes (-master/-pro/-0/-1) all rejected.
  "image_url": "https://...",           // base64 or URL — scene still / character ref. .jpg/.jpeg/.png, ≤10MB, ≥300px, AR 2:5–5:2
  "video_url": "https://...",           // base64 or URL — motion ref. .mp4/.mov, ≤100MB, 3–30s, head/shoulders/torso visible
  "mode": "pro",                        // "std" or "pro" — REQUIRED
  "character_orientation": "video",     // REQUIRED — "video" or "image"
                                        //   video: match motion ref orientation (richer motion, max 30s)
                                        //   image: match character image orientation (allows camera moves, max 10s)
  "elements": ["<element_id>"],         // optional — face/voice identity lock; reference as @Element1 in prompt
                                        //   Only active when character_orientation="video"
  "prompt": "optional scene direction <= 2500 chars",
  "negative_prompt": "optional",
  "keep_original_sound": false,
  "callback_url": "optional webhook"
}
```

**Validation order (helps debug):**
1. `model_name` parsed → "invalid" (wrong string) or "not supported" (right format wrong endpoint)
2. `image_url` missing → "imageUrl: must not be blank"
3. `video_url` missing → "videoUrl: must not be blank"
4. `mode` missing → "video mode must be specified"
5. `character_orientation` missing → "character orientation must be specified"
6. URL fetch failure → "Something went wrong when we tried to get the contents of the file."

**Spend:** ~$0.50–1.50 per call (varies by mode + duration).

**Use case for Channel 8 / Underwater:**
- Take an original shot (the blocking take, 3–30s) → use as `video_url`.
- Take the reskinned scene-still PNG (underwater palette) → use as `image_url`.
- Pass `elements: [<emperor_element_id>]` to lock the emperor's face/voice across the reskin.
- Result: same blocking + motion + voice, new visual style.

This is the workhorse for "reskin the original take while preserving choreography."

---

### 2.1. **Advanced Custom Elements (face/voice training)** — `POST /v1/general/advanced-custom-elements/`

Train a reusable identity ("element") that can be referenced in downstream `motion-control` / `multi-image2video` / `omni-video` calls via `@Element1` / element_id in the `elements: []` array.

**Two training modes:**

| `reference_type` | Source | Identity locked |
|---|---|---|
| `image_refer` | 1 frontal image + N additional angle images | Face / wardrobe only |
| `video_refer` | 1 video, 3–8s, 1080P, 16:9 or 9:16, ≤200MB | Face + motion patterns + **voice** (if audio contains human speech, cloned + added to voice library) |

**Endpoints on the same path:**
- `GET /v1/general/advanced-custom-elements/` → list existing elements
- `GET /v1/general/advanced-custom-elements/<task_id>` → fetch one element status/result
- `POST /v1/general/advanced-custom-elements/` → create new (returns task_id; poll until Active)

**Body — confirmed required fields (2026-05-18):**
```json
{
  "element_description": "<text identity prompt>",   // required — describes the look/character
  "element_name": "EMPEROR",                          // required — used as @EMPEROR in prompts later
  "reference_type": "video_refer",                    // or "image_refer"
  // ... + frontal_image / refer_images (image_refer) OR videos[] (video_refer)
  // The exact key names are NOT yet confirmed by probing — see note below.
}
```

⚠️ **Schema gap:** Probing revealed the required JSON key for the image / video payload but not the exact name. ~20 brute-force candidates (`frontal_image`, `front_image`, `image_url`, `videos`, `element_videos`, etc.) all returned "Missing element frontal image" or "The number of element videos must be 1". Likely the endpoint expects one specific Kling-internal key or a pre-uploaded file ID — get the exact field from the live docs page. The helpers in `kling_api.py` accept `**extra_fields` so you can override.

**Workflow:**
1. Cut 3–8s clean clip of each actor (single subject, 1080P, audio with their voice).
2. `create_element_video_refer(element_name="EMPEROR", element_description="...", video_url=<drive_url>)` → returns task_id.
3. `poll` via `get_element(task_id)` until status = succeed → returns `element_id`.
4. Reuse `element_id` across every motion-control / multi-image2video / omni-video call.

⚠️ **Constraint:** Voice-customized (video_refer) elements only work on `kling-video-o3`, which is **rejected on every public REST endpoint as of 2026-05-18** (`code 1201 model_name value 'kling-video-o3' is invalid`). Training may succeed but the resulting element_id is effectively unusable until Kling exposes o3 publicly. Image-only (`image_refer`) elements work today via motion-control with `kling-v3` / `kling-v2-6`.

---

### 2.5. **Omni-Video (O1) — Transformation / Unified Multimodal** — `POST /v1/videos/omni-video`

The unified multimodal endpoint. **The killer feature is "Transformation" (V2V)** — pass a source `video_url` + a style prompt, and Kling reskins the video while preserving motion, timing, blocking, and composition.

Three modes auto-selected by which inputs you pass:

| Mode | Inputs | Use case |
|---|---|---|
| **Text-to-Video** | `prompt` + `aspect_ratio` | Generate from scratch |
| **Image-conditioned** | `prompt` + (`image_list` and/or `first_image`) | Multi-ref or anchored gen |
| **Transformation (V2V)** | `prompt` + `video_url` | **Reskin existing footage. Live-action → anime, day → night, summer → winter, current → underwater palace.** Aspect inherited from source. |

**Body (verified live, default model):**
```json
{
  "prompt": "underwater palace, blue-green bioluminescent lighting, ornate gold filigree, fish swimming in BG",
  "video_url": "https://drive.../shot_04_emperor_alone.mp4",   // V2V mode trigger
  "duration": "5",                                             // "5" or "10"
  "cfg_scale": 0.5,
  "negative_prompt": "optional"
  // NO model_name — leave it off. Specific names ('kling-o1', 'kling-omni*', etc) get rejected.
  // The default routes to the O1 backbone.
  // NO aspect_ratio in V2V mode — inherits from source.
}
```

**Body (text-to-video mode):**
```json
{
  "prompt": "...",
  "aspect_ratio": "16:9",   // required when no first_image and no video_url
  "duration": "5"
}
```

**Body (image-conditioned mode):**
```json
{
  "prompt": "@image_1 hands @image_2 a sword to @image_3 ...",
  "image_list": [
    {"image": "https://.../emperor.png"},
    {"image": "https://.../sword.png"},
    {"image": "https://.../minister.png"}
  ],
  "aspect_ratio": "9:16",   // required if no first_image
  "duration": "5"
}
```

**Use `@image_N` and `@Video1`** inside the prompt to explicitly reference inputs.

**Spend:** Verified live — 5s output billed **4 credits** (~$0.50-0.70 std equivalent). Significantly pricier than v2-master image2video. Save Omni for the transformation cases where the cheaper endpoints can't do it.

**Use case for Channel 8 / Underwater:**
- This is THE endpoint for the reskin pipeline.
- Take each original shot (1920×1080, 3–30s) → pass as `video_url`.
- Prompt: `"Reskin to an underwater palace setting. Blue-green water-light, gold-trim costumes for the emperor, jade-blue robes for the minister, kelp + coral background, fish swimming in BG. Preserve all blocking, motion, and dialogue timing."`
- Output: same choreography, fully restyled.

This eliminates the need to manually composite reskinned first/end frames per shot — Omni V2V will reskin the entire take.

---

### 3. **(Singular) Element / Image-to-Video** — `POST /v1/videos/image2video`

The single-image-to-video endpoint. Use when you have ONE anchor frame (e.g. a reskinned first frame) and want Kling to animate it forward from there.

**Body:**
```json
{
  "model_name": "kling-v2-master",      // v2-master is the highest quality default
  "image": "https://...",               // base64 or URL — first frame
  "image_tail": "https://...",          // OPTIONAL — end frame (for first→end interpolation). v1-6, v2.x support.
  "prompt": "<= 2500 chars",
  "negative_prompt": "optional",
  "duration": "5",                      // "5" or "10"
  "mode": "std",                        // "std" or "pro"
  "cfg_scale": 0.5,
  "callback_url": "optional webhook"
}
```

**Spend:** ~$0.35–0.70 per 5s std, ~$0.70–1.40 per 10s pro.

**Use case for Channel 8 / Underwater:**
- Shots 04, 08, 12 have explicit first + end reskin frames → image-to-video with `image` + `image_tail`.
- Shots 01/03/07/09/10/14 have only one reskin frame → image-to-video with first frame + prompt to drive the motion forward.

---

## Polling — `GET /v1/videos/<endpoint>/<task_id>`

All 3 endpoints return:
```json
{ "code": 0, "data": { "task_id": "Cgtkl-...", "task_status": "submitted" } }
```

Then poll the same path with the task_id appended. Statuses:
- `submitted` / `processing` — keep polling (every 10s recommended)
- `succeed` — `data.task_result.videos[0].url` has the MP4
- `failed` — `data.task_status_msg` explains why

`kling_api.poll_task(endpoint, task_id)` handles the loop. Typical wall time: 60–300s per gen.

---

## Model matrix (as of 2026-05)

| Model | Endpoint(s) | Notes |
|---|---|---|
| `kling-v1-6` | multi-image2video | **Required for Elements** — v2-x not yet supported |
| `kling-v2-master` | text2video, image2video | Default for those |
| `kling-v3` | **motion-control** | ✅ Default — SoTA motion fidelity |
| `kling-v2-6` | motion-control | ✅ Older fallback. Suffixes (-master / -pro / -0 / -1) all rejected |
| `kling-video-o1` | omni-video | Required for `/omni-video` |
| `kling-video-o3` | (none — rejected publicly) | ⚠ NOT exposed on any public REST endpoint as of 2026-05-18. Likely powers the web UI's "Edit Video" tool internally but no public API access. Required by `video_refer` element-downstream gens, blocking that path. |

When firing a gen, default to:
- **Elements** (multi-image2video) → `kling-v1-6` (only option)
- **Motion Control** → `kling-v3` (SoTA, default), or `kling-v2-6` as fallback
- **Image-to-Video** → `kling-v2-master`
- **Omni-Video / Transformation** → `kling-video-o1`
- **Video-Element creation** → blocked publicly (o3 not exposed). Use `image_refer` elements + motion-control instead until Kling opens o3.

---

## Reference asset constraints

| Type | Formats | Size limit | Other |
|---|---|---|---|
| Reference image (i2v, motion-control, elements) | .jpg .jpeg .png | 10 MB | ≥300px, AR between 2:5 and 5:2 |
| Reference video (motion-control) | .mp4 .mov | 100 MB | **3–30 seconds**, subject head/shoulders/torso clearly visible |

URL must be publicly fetchable HTTPS. Drive `/uc?export=download&id=<id>` works.
For base64: embed raw `data:image/png;base64,...` or just the base64 string (Kling accepts both depending on field).

---

## Client usage (kling_api.py)

```python
from kling_api import text2video, image2video, multi_image2video, motion_control, omni_video, poll_task, extract_video_url

# Elements
resp = multi_image2video(
    image_list=["https://drive.../emperor.png", "https://drive.../throne.png"],
    prompt="The young emperor walks toward his throne...",
    model="kling-v1-6", duration=5, aspect_ratio="9:16",
)
task_id = resp["data"]["task_id"]
result = poll_task("multi-image2video", task_id)
video_url = result["task_result"]["videos"][0]["url"]

# Element creation (one-time per actor — face + voice clone)
resp = create_element_video_refer(
    element_name="EMPEROR",
    element_description="young Singaporean Chinese man, late 20s, dragon-pattern robe",
    video_url="https://drive.../emperor_clean_5s.mp4",   # 3-8s, 1080P, 16:9/9:16, ≤200MB
)
task_id = resp["data"]["task_id"]
result = poll_task("general/advanced-custom-elements", task_id)
emperor_element_id = result["task_result"]["element_id"]   # reuse forever

# Motion Control with element lock
resp = motion_control(
    image_url="https://drive.../shot4_underwater_reskin_still.png",
    video_url="https://drive.../shot4_emperor_blocking.mp4",
    elements=[emperor_element_id],     # face + voice locked to trained element
    model="kling-v2-6",
    character_orientation="video",
    mode="pro",
)

# Image-to-Video (single frame OR first+end)
resp = image2video(
    image_url="https://drive.../shot4_firstframe.png",
    image_tail="https://drive.../shot4_endframe.png",  # optional
    prompt="The emperor lowers his arm and turns away",
    model="kling-v2-master", duration=5,
)

# Omni-Video — TRANSFORMATION (V2V) — reskin the entire take
resp = omni_video(
    prompt="Underwater palace: blue-green bioluminescent lighting, ornate gold filigree on costumes, "
           "fish swimming in BG, coral and kelp. Preserve all blocking and motion.",
    video_url="https://drive.../shot_04_emperor_alone.mp4",   # source = transformation mode
    duration=5,
    # NO model_name, NO aspect_ratio (inherits from source)
)
task_id = resp["data"]["task_id"]
result = poll_task("omni-video", task_id)
video_url = extract_video_url(result)
```

---

## Failure modes seen in the wild

- **`code: 1201, message: imageUrl: must not be blank`** → field name must be `image_url` (snake_case), not `imageUrl`.
- **`code: 1201, message: File is not in a valid base64 format`** → Kling validated the URL and tried to fetch — passed a bad URL or unreachable host. For Drive, use `uc?export=download` not `/view?`.
- **`code: 1102, message: Permission denied`** → JWT expired (>30 min). Regenerate.
- **`code: 1303, message: balance not sufficient`** → top up the Kling wallet.
- **`task_status: failed, task_status_msg: ContentRiskDetected`** → moderation rejected the prompt or refs. Soften the prompt; check images don't contain banned content.

---

## Cost tracking

Append spend per call to `.kling_expense.json` (same shape as `.byteplus_expense.json`):
```json
{
  "ts": "2026-05-18T...",
  "task_id": "Cgtkl-...",
  "endpoint": "multi-image2video",
  "model": "kling-v1-6",
  "duration": 5,
  "estimated_usd": 0.50
}
```

Not yet automated — add when you start spending real budget.
