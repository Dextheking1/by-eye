# By Eye plate server

A thin API wrapper around the By Eye plate pipeline (`src/by_eye/plate.py`).
The mobile app talks to this; this talks to the Meta Model API.

## Run

From the repo root:

```bash
server/.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
```

The venv is created with system site packages so the pipeline's own
dependencies (meta-sam-parser, numpy, Pillow) stay shared:

```bash
python3 -m venv --system-site-packages server/.venv
server/.venv/bin/pip install fastapi "uvicorn[standard]" python-multipart meta-sam-parser click
```

`meta-sam-parser` is load-bearing, not optional: without it the SAM
decode step silently returns no masks (amounts still appear, outlines
and anchors come back empty). `click` is required by uvicorn.

The Meta API key is read from `~/workspace/free-tiers/keys.env`
(`META_API_KEY`), never from this repo.

## Endpoints

- `GET /health` returns `{"ok": true}`.
- `POST /scan` takes a multipart photo upload (field name `photo`),
  runs the plate pipeline (Muse Spark identifies the items, SAM 3.1
  segments each one, Muse Spark measures amounts against the mask
  coverage, bands come from the shared measure logic), keeps the scan
  in memory, and returns the analysis JSON:
  items with name, amount, unit, band, support, coverage, normalized
  box and anchor, SVG mask outlines in source pixel coordinates, and a
  `mask_url` per item. A full scan takes about 40 to 100 seconds;
  the SAM calls run one per item. Scans stored under
  `server/data/<scan_id>/` by earlier runs are still listed and
  served; new scans live in memory only and are gone when the server
  restarts, which is the right shape for this prototype.
- `GET /scans` lists past scans (newest first) with photo and overlay
  URLs, for the app's recent scans row.
- `GET /scans/<id>/photo.jpg`, `/overlay.png`, `/result.json`,
  `/masks/<item_id>.png` serve the stored pieces. Mask PNGs are
  transparent, full frame, with the item's real SAM mask tinted.
- `GET /sample.jpg` serves the bundled sample plate photo (a real
  plate photo from Pexels, by Nascimento Jr.) behind the app's
  "Try a sample plate" action. The sample goes through the same live
  pipeline as any upload; nothing about it is precomputed.

## Honesty rules

Amounts are published with bands, and weak reads come back flagged
(`publishable: false`) so the app can strike the number instead of
sharpening it. An item SAM cannot segment is still listed, with no
outline and no mask URL. Credit line in every response:
"Measured by SAM 3.1 and Muse Spark".
