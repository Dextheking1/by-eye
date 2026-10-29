"""Estimate assembly: model reads become a card-ready estimate.

Every amount carries the frame it was measured from and its band.
Amounts that fail the adversarial gate stay in the estimate, flagged,
so scoring can see exactly what would be struck from the card.
"""

from __future__ import annotations

import json
from pathlib import Path

from .clients import MeasurementRead
from .measure import BandedAmount, apply_band


def build_estimate(read: MeasurementRead, dish: str) -> dict:
    amounts: list[BandedAmount] = [
        apply_band(r.ingredient_id, r.observed_amount, r.unit, r.evidence_frame, r.note)
        for r in read.reads
    ]
    return {
        "dish": dish,
        "client": read.client,
        "amounts": [
            {
                "ingredient_id": a.ingredient_id,
                "amount": a.amount,
                "unit": a.unit,
                "band_low": a.low,
                "band_high": a.high,
                "support": a.support,
                "publishable": a.publishable,
                "evidence_frame": a.evidence_frame,
                "note": a.note,
            }
            for a in amounts
        ],
    }


def save_estimate(estimate: dict, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(estimate, indent=2, sort_keys=True) + "\n")
    return out


def load_estimate(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())
