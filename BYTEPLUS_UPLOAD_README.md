# BytePlus asset upload — team protocol

**Goal:** get a local file (image / video / audio) registered on BytePlus's Avatar Library so it can be referenced inside Seedance / BytePlus vidgen prompts as `asset://<asset-code>`.

This README explains the protocol **end-to-end** and ships a one-file CLI you can run.

---

## The 90-second version

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 byteplus_upload.py "/path/to/your/file.png" --name "TARA face"
```

After ~10-20 seconds you'll see:

```
=========================================================
  ✓ DONE — copy this into your vidgen / Seedance prompt:
=========================================================
  Name:        TARA face
  Asset code:  asset-20260521091203-abc12
  Use as:      asset://asset-20260521091203-abc12
  Drive view:  https://drive.google.com/file/d/.../view
=========================================================
```

Copy the `asset://...` line into your prompt's `content[]`. Done.

---

## What the protocol actually does (under the hood)

BytePlus's Avatar Library doesn't accept direct file uploads. It registers assets **by URL** — you give it a public URL, BytePlus fetches the file, and stores it in their CDN. So the protocol is:

1. **Upload the file to Google Drive** (resumable, with anyone-with-link reader permission)
2. **Build the right Drive URL** — this differs by asset type:
   - **Image** → `https://lh3.googleusercontent.com/d/<id>=w2048` ✅
   - **Video / Audio** → `https://drive.google.com/uc?export=download&id=<id>` ✅
   - **Never use** `https://drive.google.com/file/d/<id>/view?usp=drivesdk` ❌ (BytePlus rejects this as `UnsupportedImageFormat`)
3. **Call BytePlus `CreateAsset`** with the URL + `AssetType` (`Image` / `Video` / `Audio`) + `Name`. Returns an `asset_id` like `asset-20260521091203-abc12`.
4. **Poll `GetAsset`** every ~5s until `Status: Active`. Typical wall time: 5–30s for images, 30–60s for video, 5–15s for audio.
5. **Use as `asset://<asset_id>`** in any BytePlus content payload — this is the only URI scheme that bypasses face moderation.

The CLI does all five steps for you.

---

## Setup (one-time)

You need these inside `~/Desktop/Shotlist Workflows/`:

1. **`.env`** with at minimum:
   ```
   BYTEPLUS_ARK_API_KEY=<the team key>
   BYTEPLUS_ACCESS_KEY=<the team key>
   BYTEPLUS_SECRET_KEY=<the team key>
   ```
2. **`token.json`** — Google Drive OAuth credentials. If missing, run any of the existing scripts (e.g. `python3 storyboard_generate.py --help`) and it'll trigger the OAuth flow on first use.
3. **`ffmpeg`** installed locally (only needed if you ever upload `.m4a` audio):
   ```bash
   # Mac
   brew install ffmpeg
   # Linux
   sudo apt install ffmpeg
   ```

---

## Usage

```bash
python3 byteplus_upload.py <local-path> --name "<ASSET NAME>"
```

### Examples by asset type

| Type | Example |
|---|---|
| **Image** (face ref, location collage) | `python3 byteplus_upload.py "/Users/you/Downloads/face.png" --name "TARA face"` |
| **Video** (character orbit, location plate) | `python3 byteplus_upload.py "/Users/you/Downloads/clip.mp4" --name "MINISTER 5s"` |
| **Audio** (voice clone, dialogue) | `python3 byteplus_upload.py "/Users/you/Downloads/voice.mp3" --name "TARA VO"` |
| **m4a** (auto-converts) | `python3 byteplus_upload.py "/Users/you/Downloads/voice.m4a" --name "TARA VO"` |

### Flags

| Flag | Default | What it does |
|---|---|---|
| `--name` | **required** | The label that shows up in the BytePlus dashboard |
| `--group-id` | `group-20260505195134-wqx2b` | BytePlus group ID. Default = Channel 8 / Sajangnim group. Change for different projects. |
| `--drive-folder` | `Channel 8 Test Shoot — Character Refs` | Drive folder name to stage the upload in. Creates if missing. |
| `--timeout` | `300` | Seconds to wait for BytePlus to set `Status=Active`. Bump if assets are huge. |

---

## Supported file types

| Extension | BytePlus asset type | Notes |
|---|---|---|
| `.png` | Image | Best for face refs, character sheets, collages |
| `.jpg` / `.jpeg` | Image | Acceptable but PNG preferred for crispness |
| `.webp` | Image | Supported |
| `.mp4` | Video | Best for character orbits, location plates |
| `.mov` | Video | Supported but mp4 is preferred (smaller, more compatible) |
| `.mp3` | Audio | ✅ preferred for voice/dialogue |
| `.wav` | Audio | ✅ supported |
| `.m4a` | Audio | ⚠ BytePlus rejects m4a outright. **The CLI auto-converts to mp3** via ffmpeg if you pass one. |

---

## Pitfalls — the things that have wasted hours

### 1. m4a audio rejected
BytePlus returns `Unsupported audio format: mov. Allowed formats: mp3, wav.` if you upload m4a. Cause: m4a uses MPEG-4 container which BytePlus's audio probe misreads as 'mov'. Fix: the CLI auto-converts. If you want to do it manually:
```bash
ffmpeg -i input.m4a -codec:a libmp3lame -b:a 192k output.mp3
```

### 2. Drive `/view` URL rejected for images
BytePlus returns `InvalidParameter.UnsupportedImageFormat` if you pass a Drive `/view?usp=drivesdk` URL. Those are HTML viewer pages, not binary images. Fix: the CLI uses `lh3.googleusercontent.com/d/<id>=w2048` for images, which serves the raw binary.

### 3. Drive permissions
BytePlus fetches your file from the URL. If the file isn't anyone-with-link reader, BytePlus gets a 403 and `CreateAsset` fails. The CLI sets this automatically. If you upload to Drive manually, **set sharing to anyone-with-link reader** before passing the URL.

### 4. The asset code is the only URI that bypasses face moderation
When you use the asset in a Seedance vidgen prompt, **always** reference it as `asset://<asset_id>`, NOT as the raw URL. Plain HTTPS URLs get re-scanned by BytePlus's face-moderation pipeline and frequently reject with `PrivacyInformation`. The `asset://` scheme tells BytePlus "you already moderated this on upload, just serve it."

✅ `asset://asset-20260521091203-abc12`
❌ `https://lh3.googleusercontent.com/d/...`
❌ `https://drive.google.com/uc?export=download&id=...`
❌ raw `asset-20260521091203-abc12` (no `asset://` prefix)

### 5. Group ID matters
Default group ID in the CLI is the **Sajangnim / Channel 8** group: `group-20260505195134-wqx2b`. If you're on a different project, pass `--group-id <your-group-id>`. Wrong group = the asset uploads fine but won't show up in your project's dashboard.

### 6. "I uploaded but I can't see the asset code"
Two common causes:
- **You read stdout but missed the final summary block.** The asset code is in the 5-line block at the bottom: `Asset code: asset-20260521091203-abc12`. Scroll up.
- **The script crashed before polling completed.** Re-run — the script is idempotent on the Drive side (it'll create a new Drive copy with the same name and a Drive de-dupe suffix), and the BytePlus call is cheap to retry. If you ran the CLI but didn't get the final summary, the asset code didn't lock in. Check stdout for an error.

### 7. Asset name uniqueness
BytePlus does **not** enforce unique names — you can upload 5 assets all named "TARA face" and they'll each get distinct asset codes. In practice that's bad for the dashboard, so use clear unique names (`TARA face v1`, `TARA face v2 cleanup`, etc.). The asset code is the canonical identifier, not the name.

---

## Using the asset code downstream

Once you have `asset-20260521091203-abc12`, here's how to wire it into a Seedance content payload:

```python
content = [
    {"type": "text", "text": "<your prompt>"},
    {"type": "image_url", "image_url": {"url": "asset://asset-20260521091203-abc12"}, "role": "reference_image"},
    {"type": "video_url", "video_url": {"url": "asset://<another-asset-id>"}, "role": "reference_video"},
    {"type": "audio_url", "audio_url": {"url": "asset://<another-asset-id>"}, "role": "reference_audio"},
]
```

**Caps to remember:**
- Max 3 `video_url` refs per fire (hard API cap — 4th rejected as `InvalidParameter`)
- Total video-ref duration ≤ 15s (the model thresholds out beyond)
- Image refs and audio refs don't count toward the 3-video cap
- 1 audio ref per fire

---

## When something goes wrong

| Error message | What it actually means | Fix |
|---|---|---|
| `Unsupported audio format: mov` | You passed `.m4a` | Re-run — CLI auto-converts. Or convert manually with ffmpeg. |
| `InvalidParameter.UnsupportedImageFormat` | You passed a Drive `/view` URL | The CLI handles this. If you bypassed it, use the `lh3.googleusercontent.com/d/<id>=w2048` form. |
| `PrivacyInformation` (during vidgen, not upload) | You referenced the raw URL instead of `asset://` | Use `asset://<asset-id>` in your prompt's `content[]`, not the source URL. |
| `Asset failed` during polling | BytePlus couldn't fetch from the source URL | Check the URL works in a private browser tab. Most common cause: Drive perm not set to anyone-with-link reader. |
| `CreateAsset failed: AccessDenied` / 403 | API key issue | Check `BYTEPLUS_ARK_API_KEY` in `.env`. |
| `ModuleNotFoundError: byteplus_asset_v2` | Running from the wrong directory | `cd ~/Desktop/Shotlist\ Workflows` first. |

---

## Where the code lives

| File | Purpose |
|---|---|
| `byteplus_upload.py` | **This CLI** — single-file upload helper for the team |
| `byteplus_asset_v2.py` | Lower-level BytePlus API client (`create_asset`, `poll_asset`, `list_assets`, etc.). Used by `byteplus_upload.py` and by every other script in the project. |
| `auth.py` | Google Drive OAuth helper. Manages `token.json`. |
| `.env` | API keys. **Never commit this.** |

---

## tl;dr — copy-paste cheat sheet

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"

# Image
python3 byteplus_upload.py "/path/to/face.png" --name "CHAR face"

# Video
python3 byteplus_upload.py "/path/to/clip.mp4" --name "CHAR orbit 5s"

# Audio (mp3/wav direct; m4a auto-converts)
python3 byteplus_upload.py "/path/to/voice.mp3" --name "CHAR VO"
python3 byteplus_upload.py "/path/to/voice.m4a" --name "CHAR VO"

# Different project group?
python3 byteplus_upload.py "/path/to/x.png" --name "X" --group-id "group-<other>"
```

Asset code prints to stdout at the end. Copy `asset://<code>` into your prompt. Done.
