"""Scoring: estimate vs ground truth, per ingredient, honest bands.

The design's success bar: main amounts within about plus or minus 25
percent, and bands that contain the truth. A narrow band that misses
scores worse in this report than a wide band that holds: honesty is
the product.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BAR_PERCENT = 25.0


def load_ground_truth(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def score(estimate: dict, ground_truth: dict) -> dict:
    truth = {i["id"]: i for i in ground_truth["ingredients"]}
    bar = float(ground_truth.get("success_bar_percent", DEFAULT_BAR_PERCENT))
    rows = []
    for amount in estimate["amounts"]:
        ing = truth.get(amount["ingredient_id"])
        if ing is None:
            rows.append(
                {
                    "ingredient_id": amount["ingredient_id"],
                    "status": "not_in_ground_truth",
                }
            )
            continue
        expected = float(ing["amount"])
        got = float(amount["amount"])
        error_percent = None if expected == 0 else (got - expected) / expected * 100
        in_band = amount["band_low"] - 1e-9 <= expected <= amount["band_high"] + 1e-9
        within_bar = error_percent is not None and abs(error_percent) <= bar
        rows.append(
            {
                "ingredient_id": amount["ingredient_id"],
                "name": ing["name"],
                "unit": ing["unit"],
                "ground_truth": expected,
                "estimate": got,
                "error_percent": None if error_percent is None else round(error_percent, 1),
                "within_bar": within_bar,
                "band_low": amount["band_low"],
                "band_high": amount["band_high"],
                "band_contains_truth": in_band,
                "support": amount["support"],
                "publishable": amount["publishable"],
                "status": "scored",
            }
        )
    scored = [r for r in rows if r["status"] == "scored"]
    missing = [i for i in truth if i not in {a["ingredient_id"] for a in estimate["amounts"]}]
    return {
        "dish": ground_truth["dish"],
        "bar_percent": bar,
        "rows": rows,
        "missing_ingredients": missing,
        "summary": {
            "ingredients_scored": len(scored),
            "within_bar": sum(1 for r in scored if r["within_bar"]),
            "bands_containing_truth": sum(1 for r in scored if r["band_contains_truth"]),
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
        if row["status"] != "scored":
            lines.append(f"{row['ingredient_id']:<28} not in ground truth")
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
    return "\n".join(lines)
