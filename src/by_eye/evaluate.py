"""Scoring: estimate vs ground truth, per ingredient, honest bands.

The design's success bar: main amounts within about plus or minus 25
percent, and bands that contain the truth. A narrow band that misses
scores worse in this report than a wide band that holds: honesty is
the product.

Two comparability rules sit in front of the arithmetic, because the
first real-footage run showed both failure shapes:

- Units are converted before comparing. A read of 0.5 Tbsp against a
  ground truth stored as 7.5 ml is a correct read, not a -93 percent
  miss (run 2, 2026-10-29). Volume converts inside the volume family
  and weight inside the weight family; the two never convert into
  each other without a density, and this scorer invents none. Count
  units (count, whole, cloves, pieces) compare only inside the count
  family, one for one. A read whose unit cannot be reconciled with
  the truth's unit (22 onion "slices" against 0.25 whole onions) is
  reported as unit_mismatch: visible in the rows, excluded from the
  scored counts, never silently scored as a number.

- Ingredient ids are matched by a normalizing rule, not by string
  equality: case folded, each token singularized, trailing qualifier
  tokens (dry, dried, fresh) dropped, then exact-normalized match,
  then a unique token-subset match (glass_noodles reads match the
  glass_noodles_dry truth entry). An ambiguous read, one that fits
  two truth entries equally well, matches neither rather than
  double counting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_BAR_PERCENT = 25.0

# Conversion factors to each family's base unit. Volume base: ml.
# Weight base: g. Factors are the standard definitions (US cup and
# fluid ounce; the recipe's own card uses the same rounded values:
# 1 Tbsp = 15 ml, 1 tsp = 5 ml).
_VOLUME_TO_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 5.0,
    "tbsp": 15.0,
    "cup": 236.588,
    "fl_oz": 29.5735,
}
_WEIGHT_TO_G = {
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.349523125,
    "lb": 453.59237,
}
_COUNT_UNITS = {"count", "whole", "clove", "piece", "each"}

_UNIT_SYNONYMS = {
    "milliliter": "ml", "milliliters": "ml",
    "millilitre": "ml", "millilitres": "ml", "cc": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tbs": "tbsp", "tbsps": "tbsp",
    "cups": "cup",
    "floz": "fl_oz", "fluidounce": "fl_oz", "fluidounces": "fl_oz",
    "gram": "g", "grams": "g", "gramme": "g", "grammes": "g",
    "kilogram": "kg", "kilograms": "kg",
    "ounce": "oz", "ounces": "oz",
    "lbs": "lb", "pound": "lb", "pounds": "lb",
    "cloves": "clove", "pieces": "piece",
}


def _canonical_unit(unit: str) -> str:
    u = re.sub(r"[^a-z ]", "", str(unit).lower()).strip()
    u = _UNIT_SYNONYMS.get(u.replace(" ", ""), u.replace(" ", "_"))
    return _UNIT_SYNONYMS.get(u, u)


def unit_family(unit: str) -> tuple[str, float] | None:
    """(family, factor to the family base) for a unit, or None.

    Families: "volume" (base ml), "weight" (base g), "count" (base:
    the item itself, factor 1 between members by definition here).
    """
    canon = _canonical_unit(unit)
    if canon in _VOLUME_TO_ML:
        return ("volume", _VOLUME_TO_ML[canon])
    if canon in _WEIGHT_TO_G:
        return ("weight", _WEIGHT_TO_G[canon])
    if canon in _COUNT_UNITS:
        return ("count", 1.0)
    return None


def convert_amount(value: float, from_unit: str, to_unit: str) -> float | None:
    """value expressed in to_unit, or None when no honest conversion.

    Conversion only happens inside one family. A unit string that is
    the ingredient read's own name (a read of 0.25 "onion") is handled
    by the caller, not here.
    """
    src = unit_family(from_unit)
    dst = unit_family(to_unit)
    if src is None or dst is None or src[0] != dst[0]:
        return None
    return value * src[1] / dst[1]


def _singular(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes", "oes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us")):
        return word[:-1]
    return word


_QUALIFIER_SUFFIXES = {"dry", "dried", "fresh"}


def normalize_id(ingredient_id: str) -> tuple[str, ...]:
    """An id as a tuple of normalized tokens.

    Case folded, split on non-alphanumerics, each token singularized,
    trailing qualifier tokens (dry, dried, fresh) dropped: the
    difference between a read id and a ground truth id is usually one
    of those three, not a different ingredient.
    """
    tokens = [
        _singular(t) for t in re.split(r"[^a-z0-9]+", str(ingredient_id).lower()) if t
    ]
    while tokens and tokens[-1] in _QUALIFIER_SUFFIXES:
        tokens.pop()
    return tuple(tokens)


def match_ingredient(read_id: str, truth_ids: list[str]) -> str | None:
    """The single ground truth id a read refers to, or None.

    Tiers, strictest first: exact id; normalized-token equality; a
    unique token-subset relation in either direction (read tokens a
    subset of the truth's, or the truth's a subset of the read's).
    A tier that fits two truth entries equally well is ambiguous and
    matches neither: soy_sauce exact-matches its own entry and never
    leaks into soy_sauce_marinade.
    """
    if read_id in truth_ids:
        return read_id
    read_tokens = normalize_id(read_id)
    if not read_tokens:
        return None
    normalized = {tid: normalize_id(tid) for tid in truth_ids}
    exact = [tid for tid, toks in normalized.items() if toks == read_tokens]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    read_set = set(read_tokens)
    candidates = []
    for tid, toks in normalized.items():
        tset = set(toks)
        if read_set <= tset or tset <= read_set:
            candidates.append((abs(len(read_set) - len(tset)), tid))
    if not candidates:
        return None
    candidates.sort()
    best = candidates[0]
    if len(candidates) > 1 and candidates[1][0] == best[0]:
        return None
    return best[1]


def load_ground_truth(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def score(estimate: dict, ground_truth: dict) -> dict:
    truth = {i["id"]: i for i in ground_truth["ingredients"]}
    truth_ids = list(truth)
    bar = float(ground_truth.get("success_bar_percent", DEFAULT_BAR_PERCENT))
    rows = []
    matched_truth: set[str] = set()
    for amount in estimate["amounts"]:
        matched_id = match_ingredient(amount["ingredient_id"], truth_ids)
        if matched_id is None:
            rows.append(
                {
                    "ingredient_id": amount["ingredient_id"],
                    "status": "not_in_ground_truth",
                }
            )
            continue
        matched_truth.add(matched_id)
        ing = truth[matched_id]
        expected = float(ing["amount"])
        got = convert_amount(float(amount["amount"]), amount["unit"], ing["unit"])
        band_low = convert_amount(
            float(amount["band_low"]), amount["unit"], ing["unit"]
        )
        band_high = convert_amount(
            float(amount["band_high"]), amount["unit"], ing["unit"]
        )
        if got is None:
            # A read in the ingredient's own name as its unit ("0.25
            # onion") is a count of that ingredient; that is the one
            # unit reconciliation outside the families, and it lands
            # in the count family or nowhere.
            own_name = _singular(
                re.sub(r"[^a-z]", "", str(amount["unit"]).lower())
            )
            if own_name and own_name in normalize_id(matched_id) and (
                unit_family(ing["unit"]) or (None, 0)
            )[0] == "count":
                got = float(amount["amount"])
                band_low = float(amount["band_low"])
                band_high = float(amount["band_high"])
        if got is None:
            rows.append(
                {
                    "ingredient_id": amount["ingredient_id"],
                    "matched_id": matched_id,
                    "name": ing["name"],
                    "unit": ing["unit"],
                    "estimate_unit": amount["unit"],
                    "status": "unit_mismatch",
                }
            )
            continue
        error_percent = None if expected == 0 else (got - expected) / expected * 100
        in_band = band_low - 1e-9 <= expected <= band_high + 1e-9
        within_bar = error_percent is not None and abs(error_percent) <= bar
        rows.append(
            {
                "ingredient_id": amount["ingredient_id"],
                "matched_id": matched_id,
                "name": ing["name"],
                "unit": ing["unit"],
                "ground_truth": expected,
                "estimate": round(got, 4),
                "estimate_as_read": float(amount["amount"]),
                "estimate_unit": amount["unit"],
                "error_percent": None if error_percent is None else round(error_percent, 1),
                "within_bar": within_bar,
                "band_low": band_low,
                "band_high": band_high,
                "band_contains_truth": in_band,
                "support": amount["support"],
                "publishable": amount["publishable"],
                "status": "scored",
            }
        )
    scored = [r for r in rows if r["status"] == "scored"]
    missing = [i for i in truth_ids if i not in matched_truth]
    return {
        "dish": ground_truth["dish"],
        "bar_percent": bar,
        "rows": rows,
        "missing_ingredients": missing,
        "summary": {
            "ingredients_scored": len(scored),
            "within_bar": sum(1 for r in scored if r["within_bar"]),
            "bands_containing_truth": sum(1 for r in scored if r["band_contains_truth"]),
            "unit_mismatches": sum(1 for r in rows if r["status"] == "unit_mismatch"),
            "mean_abs_error_percent": (
                round(sum(abs(r["error_percent"]) for r in scored) / len(scored), 1)
                if scored
                else None
            ),
        },
    }


def format_report(result: dict) -> str:
    lines = [
        f"By Eye evaluation: {result['dish']}",
        f"Bar: plus or minus {result['bar_percent']:.0f} percent. "
        "Band must contain the truth to count as honest.",
        "",
        f"{'ingredient':<28} {'truth':>8} {'estimate':>9} {'error':>8} "
        f"{'in bar':>6} {'band holds':>10}  support",
    ]
    for row in result["rows"]:
        if row["status"] == "not_in_ground_truth":
            lines.append(f"{row['ingredient_id']:<28} not in ground truth")
            continue
        if row["status"] == "unit_mismatch":
            lines.append(
                f"{row['ingredient_id']:<28} read in {row['estimate_unit']}, "
                f"ground truth in {row['unit']}: no honest conversion, not scored"
            )
            continue
        lines.append(
            f"{row['ingredient_id']:<28} {row['ground_truth']:>8} "
            f"{row['estimate']:>9} {row['error_percent']:>+7.1f}% "
            f"{'yes' if row['within_bar'] else 'NO':>6} "
            f"{'yes' if row['band_contains_truth'] else 'NO':>10}  "
            f"{row['support']}{'' if row['publishable'] else ' (struck from card)'}"
        )
    if result["missing_ingredients"]:
        lines.append("")
        lines.append("Missing from estimate: " + ", ".join(result["missing_ingredients"]))
    s = result["summary"]
    lines += [
        "",
        f"Scored: {s['ingredients_scored']} ingredients, "
        f"{s['within_bar']} within the bar, "
        f"{s['bands_containing_truth']} bands contain the truth, "
        f"mean absolute error {s['mean_abs_error_percent']} percent.",
    ]
    if s.get("unit_mismatches"):
        lines.append(
            f"Unit mismatches (listed, not scored): {s['unit_mismatches']}."
        )
    return "\n".join(lines)
