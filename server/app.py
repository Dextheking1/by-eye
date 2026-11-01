"""By Eye plate server: a thin API wrapper around the plate pipeline.

One endpoint does the work: POST /scan takes a plate photo and returns
the shaped plate analysis (items, amounts, bands, mask outlines, mask
image URLs). Rendered masks and a composite overlay are served back so
the app can draw the HUD without shipping rasters around.

Scans are kept in memory only. This build runs in a sandbox where the
server process cannot write binary files to disk, and in-memory scans
are the right shape for a prototype anyway; scans stored on disk by
earlier runs are still readable and listed.

Run it with the project venv:

    server/.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000

or from this directory:

    .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image

from by_eye.plate import PlateAnalyzer, PlateItem, shape_plate_response

SERVER_DIR = Path(__file__).resolve().parent
DATA_DIR = SERVER_DIR / "data"
SAMPLE_PHOTO = SERVER_DIR / "sample-plate.jpg"
TERRACOTTA = (180, 85, 45)
MAX_DIM = 1280

app = FastAPI(title="By Eye plate server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_analyzer: PlateAnalyzer | None = None

# scan_id -> {"response": dict, "photo": bytes, "overlay": bytes,
#             "masks": {item_id: bytes}, "created_at": str}
_scans: dict[str, dict] = {}


def analyzer() -> PlateAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = PlateAnalyzer()
    return _analyzer


def _mask_edge(mask: np.ndarray) -> np.ndarray:
    """One-pixel inner edge of a bool mask, by neighbour subtraction."""
    eroded = np.ones_like(mask)
    eroded[1:, :] &= mask[:-1, :]
    eroded[:-1, :] &= mask[1:, :]
    eroded[:, 1:] &= mask[:, :-1]
    eroded[:, :-1] &= mask[:, 1:]
    eroded &= mask
    return mask & ~eroded


def render_mask_png(item: PlateItem) -> bytes:
    """Transparent full-frame PNG: the item's real mask, tinted."""
    rgba = np.zeros((item.frame_height, item.frame_width, 4), dtype=np.uint8)
    full = item.full_mask()
    rgba[full] = (*TERRACOTTA, 110)
    rgba[_mask_edge(full)] = (*TERRACOTTA, 255)
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


def render_overlay_png(photo_bytes: bytes, items: list[PlateItem]) -> bytes:
    """The plate photo with every item's mask tinted and outlined."""
    base = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    layer_arr = np.zeros((base.size[1], base.size[0], 4), dtype=np.uint8)
    for item in items:
        if not item.segments:
            continue
        full = item.full_mask()
        layer_arr[full] = (*TERRACOTTA, 70)
        layer_arr[_mask_edge(full)] = (*TERRACOTTA, 255)
    layer = Image.fromarray(layer_arr, "RGBA")
    buf = io.BytesIO()
    Image.alpha_composite(base, layer).convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _get_scan(scan_id: str) -> dict:
    """In-memory scan, falling back to scans stored on disk earlier."""
    if scan_id in _scans:
        return _scans[scan_id]
    folder = DATA_DIR / scan_id
    result_file = folder / "result.json"
    if not result_file.is_file():
        raise HTTPException(status_code=404, detail="No such scan.")
    entry = {
        "response": json.loads(result_file.read_text()),
        "photo": (folder / "photo.jpg").read_bytes()
        if (folder / "photo.jpg").is_file()
        else b"",
        "overlay": (folder / "overlay.png").read_bytes()
        if (folder / "overlay.png").is_file()
        else b"",
        "masks": {},
        "created_at": None,
    }
    masks_dir = folder / "masks"
    if masks_dir.is_dir():
        for mask_file in masks_dir.iterdir():
            entry["masks"][mask_file.stem] = mask_file.read_bytes()
    _scans[scan_id] = entry
    return entry


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "by-eye-plate"}


@app.get("/sample.jpg")
def sample_photo():
    if not SAMPLE_PHOTO.is_file():
        raise HTTPException(status_code=404, detail="No sample photo on this server.")
    return FileResponse(SAMPLE_PHOTO, media_type="image/jpeg")


@app.post("/scan")
async def scan(photo: UploadFile = File(...)) -> dict:
    raw = await photo.read()
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="That file is not a photo I can read.")
    image.thumbnail((MAX_DIM, MAX_DIM))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=88)
    photo_bytes = buf.getvalue()

    scan_id = uuid.uuid4().hex[:12]
    items = analyzer().analyze_bytes(photo_bytes)
    width, height = image.size

    masks = {
        item.item_id: render_mask_png(item) for item in items if item.segments
    }
    overlay = render_overlay_png(photo_bytes, items)

    response = shape_plate_response(
        items,
        width,
        height,
        mask_url_for=lambda item_id: f"/scans/{scan_id}/masks/{item_id}.png",
    )
    created_at = datetime.now(timezone.utc).isoformat()
    response["scan_id"] = scan_id
    response["photo_url"] = f"/scans/{scan_id}/photo.jpg"
    response["overlay_url"] = f"/scans/{scan_id}/overlay.png"
    response["created_at"] = created_at
    _scans[scan_id] = {
        "response": response,
        "photo": photo_bytes,
        "overlay": overlay,
        "masks": masks,
        "created_at": created_at,
    }
    return response


@app.get("/scans")
def list_scans() -> dict:
    seen: set[str] = set()
    scans = []
    if DATA_DIR.is_dir():
        for folder in DATA_DIR.iterdir():
            if (folder / "result.json").is_file():
                seen.add(folder.name)
    for scan_id in list(seen) + [s for s in _scans if s not in seen]:
        try:
            entry = _get_scan(scan_id)
        except HTTPException:
            continue
        result = entry["response"]
        scans.append(
            {
                "scan_id": result["scan_id"],
                "created_at": result.get("created_at"),
                "item_count": len(result["items"]),
                "photo_url": result["photo_url"],
                "overlay_url": result["overlay_url"],
            }
        )
    scans.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return {"scans": scans}


@app.get("/scans/{scan_id}/photo.jpg")
def scan_photo(scan_id: str):
    entry = _get_scan(scan_id)
    if not entry["photo"]:
        raise HTTPException(status_code=404, detail="No photo for that scan.")
    return Response(entry["photo"], media_type="image/jpeg")


@app.get("/scans/{scan_id}/overlay.png")
def scan_overlay(scan_id: str):
    entry = _get_scan(scan_id)
    if not entry["overlay"]:
        raise HTTPException(status_code=404, detail="No overlay for that scan.")
    return Response(entry["overlay"], media_type="image/png")


@app.get("/scans/{scan_id}/result.json")
def scan_result(scan_id: str):
    entry = _get_scan(scan_id)
    return Response(
        json.dumps(entry["response"], indent=2), media_type="application/json"
    )


@app.get("/scans/{scan_id}/masks/{item_id}.png")
def scan_mask(scan_id: str, item_id: str):
    entry = _get_scan(scan_id)
    mask = entry["masks"].get(item_id)
    if mask is None:
        raise HTTPException(status_code=404, detail="No mask for that item.")
    return Response(mask, media_type="image/png")
