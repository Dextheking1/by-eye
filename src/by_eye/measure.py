"""Anchors and bands.

An amount is only as good as its anchor chain: what known-size thing in
the frame turned pixels into a physical size. Amounts are published
with a band, not as bare numbers. The band starts from the read's
support level and widens where the read is weak. The adversarial rule
for the card: no anchor and no evidence frame, no number; the amount
is demoted to the cook's own words.
"""

from __future__ import annotations

from dataclasses import dataclass

# Rough densities for turning a read volume into grams later.
# Values are grams per millilitre, kitchen references.
DENSITY_G_PER_ML = {
    "glass_noodles_dry": 0.35,
    "cabbage": 0.09,
    "carrots": 0.12,
}

# Default half-width of the approximation band, as a fraction of the
# amount, by support level.
BAND_FRACTION = {
    "counted": 0.05,  # eggs cracked on camera, tomatoes wedged on camera
    "anchored": 0.20,  # sized against a hand, a mug, a known bowl
    "flow": 0.30,  # pour duration times stream width
    "weak": 0.50,  # a shake, a splash, a heap: a number would pretend
}

COUNTABLE_UNITS = {"count", "cloves", "whole"}


@dataclass
class BandedAmount:
    ingredient_id: str
    amount: float
    unit: str
    low: float
    high: float
    support: str
    evidence_frame: str
    note: str = ""

    @property
    def band_fraction(self) -> float:
        if self.amount == 0:
            return 0.0
        return (self.high - self.low) / 2 / self.amount

    @property
    def publishable(self) -> bool:
        """The adversarial gate: a number needs support and a frame."""
        return self.support != "weak" and bool(self.evidence_frame)


def support_for(unit: str, note: str) -> str:
    text = note.lower()
    if unit in COUNTABLE_UNITS:
        return "counted"
    if "pour" in text or "stream" in text:
        return "flow"
    if "shake" in text or "splash" in text or "heap" in text or "guess" in text:
        return "weak"
    return "anchored"


# Smallest honest step for counted things. Two eggs read on camera is
# still plus or minus one egg once hands cross the frame; a quarter of
# an onion is the smallest piece anyone cuts.
COUNTABLE_STEP = {"count": 1.0, "cloves": 1.0, "whole": 0.25}


def apply_band(ingredient_id: str, amount: float, unit: str, evidence_frame: str, note: str) -> BandedAmount:
    support = support_for(unit, note)
    frac = BAND_FRACTION[support]
    half = amount * frac
    if unit in COUNTABLE_STEP:
        half = max(half, COUNTABLE_STEP[unit])
    return BandedAmount(
        ingredient_id=ingredient_id,
        amount=amount,
        unit=unit,
        low=round(max(amount - half, 0.0), 3),
        high=round(amount + half, 3),
        support=support,
        evidence_frame=evidence_frame,
        note=note,
    )
