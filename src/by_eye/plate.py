"""Plate mode: one photo of a finished plate in, measured items out.

The video pipeline reads amounts out of cooking footage. Plate mode is
the consumer shape of the same engine: a single overhead photo of a
plated meal, and every food item on it spotted, outlined, and measured.

Flow, mirroring the video pipeline's evidence discipline:

1. Muse Spark looks at the photo and names each distinct food item,
   in plain words a home cook uses, with a short segmentation prompt
   per item.
2. SAM 3.1 segments each item. All pieces of one food (tomato wedges,
   salad leaves) merge into one item mask. The mask coverage is the
   measurement anchor, the same role it plays on video frames.
3. Muse Spark reads the amounts with the SAM coverage in front of it,
   and every amount goes through the shared band logic in measure.py:
   a number is published with a band, and weak reads are flagged for
   the app to strike, never quietly sharpened.

Nothing here invents a mask or an amount. An item SAM cannot find is
still listed, with no outline, and the app shows it as text only.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .clients import META_SPARK_MODEL, MetaModelClient, _extract_json_array
from .measure import apply_band

CREDIT_LINE = "Measured by SAM 3.1 and Muse Spark"


@dataclass
class PlateSegment:
    """One SAM 3.1 piece of one food item, mask decoded to a raster."""

    box: tuple[int, int, int, int]  # x1, y1, x2, y2 exclusive, source px
    mask: object  # numpy bool array, shape (box height, box width)
    outline_path: str  # SVG path in box-local coordinates
    area_px: int


@dataclass
class PlateItem:
    """One food item on the plate, after segmentation and measuring."""

    item_id: str
    name: str
    amount: float | None = None
    unit: str = ""
    band_low: float | None = None
    band_high: float | None = None
    support: str = ""
    publishable: bool = False
    note: str = ""
    segments: list[PlateSegment] = field(default_factory=list)
    frame_width: int = 0
    frame_height: int = 0

    @property
    def mask_area_px(self) -> int:
        return sum(s.area_px for s in self.segments)

    @property
    def coverage_fraction(self) -> float | None:
        if not self.segments or not self.frame_width or not self.frame_height:
            return None
        return self.mask_area_px / (self.frame_width * self.frame_height)

    @property
    def union_box(self) -> tuple[int, int, int, int] | None:
        if not self.segments:
            return None
        return (
            min(s.box[0] for s in self.segments),
            min(s.box[1] for s in self.segments),
            max(s.box[2] for s in self.segments),
            max(s.box[3] for s in self.segments),
        )

    def full_mask(self):
        """Union of all piece masks as one full-frame bool array."""
        import numpy as np

        full = np.zeros((self.frame_height, self.frame_width), dtype=bool)
        for seg in self.segments:
            x1, y1, x2, y2 = seg.box
            h, w = seg.mask.shape
            cx2, cy2 = min(x2, self.frame_width), min(y2, self.frame_height)
            if cx2 <= x1 or cy2 <= y1:
                continue
            full[y1:cy2, x1:cx2] |= seg.mask[: cy2 - y1, : cx2 - x1]
        return full

    @property
    def centroid(self) -> tuple[float, float] | None:
        """Mask centroid in source px, box centre when no mask decoded."""
        import numpy as np

        if self.segments:
            full = self.full_mask()
            ys, xs = np.nonzero(full)
            if len(xs):
                return float(xs.mean()), float(ys.mean())
        box = self.union_box
        if box:
            return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        return None


def decode_segments(sam_text: str) -> list[PlateSegment]:
    """Decode SAM 3.1 output text into segments with real mask rasters.

    Box and mask records pair by object id. A mask that does not
    decode is dropped rather than replaced with its box: an outline
    must be the model's own mask, never a rectangle dressed up as one.
    """
    if not sam_text.strip():
        return []
    try:
        from meta_sam_parser import (
            CompletedOutcome,
            decode_mask_to_raster,
            decode_mask_to_svg_path,
            image_segmentation_format,
        )
    except ImportError:
        return []
    import numpy as np

    parser = image_segmentation_format().create_parser()
    parser.push(sam_text)
    result = parser.finish(CompletedOutcome()).result
    boxes: dict[str, object] = {}
    masks: dict[str, object] = {}
    for record in result.records:
        kind = type(record).__name__
        if kind == "SegmentationBoxRecord":
            boxes[record.object_id] = record
        elif kind == "SegmentationMaskRecord":
            masks[record.object_id] = record
    segments: list[PlateSegment] = []
    for object_id, box_rec in boxes.items():
        mask_rec = masks.get(object_id)
        if mask_rec is None:
            continue
        try:
            raster = decode_mask_to_raster(mask_rec.mask)
            outline = decode_mask_to_svg_path(mask_rec.mask)
        except Exception:
            continue
        w, h = int(mask_rec.mask.width), int(mask_rec.mask.height)
        if len(raster) != w * h:
            continue
        arr = np.frombuffer(bytes(raster), dtype=np.uint8).reshape(h, w) > 0
        segments.append(
            PlateSegment(
                box=(int(box_rec.left), int(box_rec.top), int(box_rec.right), int(box_rec.bottom)),
                mask=arr,
                outline_path=outline,
                area_px=int(arr.sum()),
            )
        )
    return segments


_WORD_FRACTIONS = {0.25: "a quarter", 0.5: "half", 0.75: "three quarters"}


def format_amount(amount: float, unit: str) -> str:
    """An amount the way a person would say it: 'about 180 g', '2'."""
    if unit in ("count", "whole"):
        if amount in _WORD_FRACTIONS:
            return _WORD_FRACTIONS[amount]
        if amount == int(amount):
            return f"{int(amount)}"
        return f"{amount:g}"
    if unit in ("g", "ml"):
        rounded = round(amount / 5) * 5
        return f"about {rounded:g} {unit}"
    if amount == int(amount):
        return f"{int(amount)} {unit}"
    return f"about {amount:g} {unit}"


def format_band(low: float, high: float, unit: str) -> str:
    if unit in ("g", "ml"):
        lo, hi = round(low / 5) * 5, round(high / 5) * 5
        return f"{lo:g} to {hi:g} {unit}"
    return f"{low:g} to {high:g} {unit}"


def shape_plate_response(
    items: list[PlateItem],
    image_width: int,
    image_height: int,
    mask_url_for=None,
) -> dict:
    """Shape analysed items into the API response the app renders.

    Pure shaping: no model calls, no I/O. mask_url_for, when given,
    maps an item id to the URL of its rendered mask image.
    """
    shaped = []
    for item in items:
        box = item.union_box
        centroid = item.centroid
        coverage = item.coverage_fraction
        entry = {
            "id": item.item_id,
            "name": item.name,
            "amount": item.amount,
            "unit": item.unit,
            "amount_label": (
                format_amount(item.amount, item.unit) if item.amount is not None else None
            ),
            "band_low": item.band_low,
            "band_high": item.band_high,
            "band_label": (
                format_band(item.band_low, item.band_high, item.unit)
                if item.band_low is not None and item.band_high is not None
                else None
            ),
            "support": item.support,
            "publishable": item.publishable,
            "note": item.note,
            "coverage_percent": (
                round(coverage * 100, 1) if coverage is not None else None
            ),
            "box": (
                {
                    "x": box[0] / image_width,
                    "y": box[1] / image_height,
                    "w": (box[2] - box[0]) / image_width,
                    "h": (box[3] - box[1]) / image_height,
                }
                if box
                else None
            ),
            "anchor": (
                {"x": centroid[0] / image_width, "y": centroid[1] / image_height}
                if centroid
                else None
            ),
            "outlines": [
                {"d": seg.outline_path, "tx": seg.box[0], "ty": seg.box[1]}
                for seg in item.segments
            ],
            "mask_url": mask_url_for(item.item_id) if mask_url_for else None,
        }
        shaped.append(entry)
    return {
        "image": {"width": image_width, "height": image_height},
        "items": shaped,
        "credit": CREDIT_LINE,
    }


_IDENTIFY_TEXT = (
    "You are looking at a photo of a finished plate of food, taken "
    "from above. List each distinct food item on the plate. Return "
    "one JSON object per item with keys: id (snake_case), name (plain "
    "words a home cook uses, like 'grilled chicken' or 'white rice', "
    "never a brand or a recipe title), sam_prompt (a short singular "
    "noun phrase naming exactly that food, for image segmentation). "
    "A sauce or side served in its own small bowl on or beside the "
    "plate counts as an item. The plate itself, cutlery, the table "
    "and any drink are not items. If two foods are mixed so they "
    "cannot be separated by eye, list them as one item. Return only "
    "a JSON array."
)

_MEASURE_TEXT = (
    "You are the measurement reader for a photo of a finished plate "
    "of food. Segmentation evidence from SAM 3.1 is listed below: "
    "how much of the photo each food covers, measured, not guessed. "
    "Use it as a size anchor. A standard dinner plate is about 27 cm "
    "across; when the plate fills most of the photo, its rim is your "
    "ruler. For each item, return one JSON object with keys: id, "
    "observed_amount, unit, note. Units a home cook uses: g for "
    "foods best weighed (meat, rice, pasta, vegetables by weight), "
    "count for whole discrete things (eggs, sausages, meatballs, "
    "rolls), Tbsp or ml for sauces. The note must say what you "
    "anchored on, in plain words: 'counted directly', 'covers about "
    "a fifth of the plate, a palm-sized piece', 'one spoon of sauce "
    "in the bowl'. If an amount is a genuine guess with no anchor, "
    "put the word 'guess' in the note so the app can show it as "
    "approximate. If you cannot support an amount for an item at "
    "all, omit it. Return only a JSON array."
)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "item"


class PlateAnalyzer:
    """The plate pipeline: identify, segment, measure, band."""

    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def _spark_json(self, image_path: Path, text: str) -> list:
        return self._spark_json_bytes(image_path.read_bytes(), text)

    def _spark_json_bytes(self, data: bytes, text: str) -> list:
        encoded = base64.b64encode(data).decode()
        body = self.client._post_json(
            "/chat/completions",
            {
                "model": META_SPARK_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 4000,
            },
            timeout=240,
        )
        content = body["choices"][0]["message"].get("content") or ""
        return _extract_json_array(content)

    def identify(self, image_path: str | Path) -> list[dict]:
        return self.identify_bytes(Path(image_path).read_bytes())

    def identify_bytes(self, data: bytes) -> list[dict]:
        raw = self._spark_json_bytes(data, _IDENTIFY_TEXT)
        seen: set[str] = set()
        items = []
        for entry in raw:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            item_id = _slug(str(entry.get("id") or name))
            if item_id in seen:
                continue
            seen.add(item_id)
            items.append(
                {
                    "id": item_id,
                    "name": name,
                    "sam_prompt": str(entry.get("sam_prompt") or name).strip(),
                }
            )
        return items

    def segment_items(
        self, image_path: str | Path, identified: list[dict], width: int, height: int
    ) -> list[PlateItem]:
        return self.segment_items_bytes(
            Path(image_path).read_bytes(), identified, width, height
        )

    def segment_items_bytes(
        self, data: bytes, identified: list[dict], width: int, height: int
    ) -> list[PlateItem]:
        items = []
        for entry in identified:
            text = self.client.segment_raw_bytes(data, entry["sam_prompt"])
            segments = decode_segments(text)
            items.append(
                PlateItem(
                    item_id=entry["id"],
                    name=entry["name"],
                    segments=segments,
                    frame_width=width,
                    frame_height=height,
                )
            )
        return items

    def measure(self, image_path: str | Path, items: list[PlateItem]) -> list[PlateItem]:
        return self.measure_bytes(Path(image_path).read_bytes(), items)

    def measure_bytes(self, data: bytes, items: list[PlateItem]) -> list[PlateItem]:
        evidence_lines = []
        for item in items:
            coverage = item.coverage_fraction
            if coverage is not None:
                evidence_lines.append(
                    f"SAM 3.1: '{item.name}' covers {coverage * 100:.1f}% of the photo "
                    f"in {len(item.segments)} piece(s)."
                )
            else:
                evidence_lines.append(
                    f"SAM 3.1: no mask for '{item.name}'; read it from the photo alone."
                )
        text = (
            _MEASURE_TEXT
            + "\nItems to measure (use these exact ids): "
            + json.dumps([{"id": i.item_id, "name": i.name} for i in items])
            + "\n"
            + "\n".join(evidence_lines)
        )
        raw = self._spark_json_bytes(data, text)
        by_id = {item.item_id: item for item in items}
        for entry in raw:
            item = by_id.get(str(entry.get("id", "")))
            if item is None:
                continue
            try:
                amount = float(entry["observed_amount"])
            except (KeyError, TypeError, ValueError):
                continue
            unit = str(entry.get("unit", "")).strip()
            note = str(entry.get("note", "")).strip()
            banded = apply_band(item.item_id, amount, unit, "plate photo", note)
            item.amount = amount
            item.unit = unit
            item.band_low = banded.low
            item.band_high = banded.high
            item.support = banded.support
            item.publishable = banded.publishable
            item.note = note
        return items

    def analyze(self, image_path: str | Path) -> list[PlateItem]:
        return self.analyze_bytes(Path(image_path).read_bytes())

    def analyze_bytes(self, data: bytes) -> list[PlateItem]:
        """Plate analysis on an in-memory JPEG: identify, segment,
        measure, band. Same pipeline as analyze(), no file needed."""
        import io

        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
        identified = self.identify_bytes(data)
        if not identified:
            return []
        items = self.segment_items_bytes(data, identified, width, height)
        return self.measure_bytes(data, items)
