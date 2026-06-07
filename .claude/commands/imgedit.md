---
description: Edit ONE image via Higgsfield Nano Banana 2 — feed a source image + a plain-English edit instruction, get the edited image back (local + optional Drive upload).
argument-hint: --image <path|drive-url|drive-id|http-url> --prompt "<edit>" [--model nano_banana_2] [--aspect auto] [--resolution 1k] [--out <path>] [--upload]
---

User invoked /imgedit. Args: `$ARGUMENTS`

## What this does

Threads ONE source image into Higgsfield (Nano Banana 2 by default) along with a
plain-English edit instruction, and writes back the edited result. This is the
image-EDIT counterpart to `/blockinggen` and `/imggen` — use it for surgical edits
("change the sign to X", "make the facade black", "remove the person on the left")
where you want to keep the rest of the frame intact.

## The source image (--image)

Accepts any of:
- a **local file path** — `/Users/.../darkroom_src.png`
- a **Google Drive share URL** — `https://drive.google.com/file/d/<id>/view`
- a **bare Drive file id** — `1kr_HKFCiQ-wCAHidGVUAXNSJRET5z8hW`
- a **plain http(s) image URL**

If the user pasted an image into chat (not a file), it is NOT on disk — ask them to
save it to a path first (e.g. into the project folder), then pass that path. Nano Banana
edits require the image as a file.

## Run

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
/usr/bin/python3 imgedit.py $ARGUMENTS
```

Defaults:
- `--model nano_banana_2` (Nano Banana 2 on Higgsfield; pass another Higgsfield slug to override)
- `--aspect auto` — detects the source image's aspect ratio and snaps to the nearest
  supported ratio so the frame isn't re-cropped (override with e.g. `--aspect 16:9`)
- `--resolution 1k`
- output saved to `~/Documents/Good Light Generated Videos/_Edits/` unless `--out` is given
- `--upload` also pushes the result to Drive (anyone-with-link reader) and prints the URL.
  Set env `IMGEDIT_DRIVE_FOLDER` to drop uploads into a specific folder.

## Prompt guidance

Nano Banana honors the source image strongly. For surgical edits, state what to change
AND what to preserve, e.g.:

> "Keep everything in this image identical. Change ONLY the storefront sign text to read
> 'Darkroom'. Restyle the facade as an edgy photo-studio exterior with a black colour
> palette. Do not change the people, framing, lighting, or street."

## Notes

- One source image per call (single `image_ref_path`). For multi-reference composites,
  use the vidgen/storyboard paths instead.
- This does not write to any sheet — it's a standalone edit tool. Wire the result URL
  into a bible column manually if needed.
