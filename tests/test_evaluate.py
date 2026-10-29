"""Evaluator comparability: unit conversion and ingredient matching.

Both rules exist because of the first real-footage run (2026-10-29):
a correct 0.5 Tbsp read scored -93.3 percent against ml ground
truth, and correct reads named glass_noodles, egg and carrot matched
nothing because the truth ids are glass_noodles_dry, eggs, carrots.
"""

from by_eye.evaluate import (
    convert_amount,
    match_ingredient,
    normalize_id,
    score,
    unit_family,
)


def test_volume_conversions():
    assert convert_amount(0.5, "Tbsp", "ml") == 7.5
    assert convert_amount(1, "tsp", "ml") == 5.0
    assert convert_amount(1, "tablespoons", "ml") == 15.0
    assert convert_amount(2, "l", "ml") == 2000.0
    assert convert_amount(15, "ml", "Tbsp") == 1.0
    assert convert_amount(1, "cup", "ml") == 236.588
    assert convert_amount(1, "fl oz", "ml") == 29.5735


def test_weight_conversions():
    assert convert_amount(1, "kg", "g") == 1000.0
    assert convert_amount(16, "oz", "lb") == 16 * 28.349523125 / 453.59237
    assert convert_amount(170, "g", "g") == 170.0


def test_no_cross_family_conversion():
    # No density is invented: volume never becomes weight here.
    assert convert_amount(1, "cup", "g") is None
    assert convert_amount(100, "g", "ml") is None
    assert convert_amount(2, "count", "ml") is None


def test_count_family_is_one_for_one():
    assert unit_family("cloves")[0] == "count"
    assert unit_family("whole")[0] == "count"
    assert convert_amount(2, "cloves", "count") == 2.0
    assert convert_amount(1, "whole", "count") == 1.0


def test_unknown_unit_has_no_family():
    assert unit_family("slices") is None
    assert convert_amount(22, "slices", "whole") is None


def test_normalize_id():
    assert normalize_id("glass_noodles_dry") == ("glass", "noodle")
    assert normalize_id("Eggs") == ("egg",)
    assert normalize_id("carrots") == ("carrot",)
    assert normalize_id("green_onion") == ("green", "onion")
    assert normalize_id("soy_sauce_marinade") == ("soy", "sauce", "marinade")


def test_match_ingredient_tiers():
    truth = ["glass_noodles_dry", "eggs", "carrots", "soy_sauce",
             "soy_sauce_marinade", "onion", "green_onion"]
    assert match_ingredient("soy_sauce", truth) == "soy_sauce"
    assert match_ingredient("glass_noodles", truth) == "glass_noodles_dry"
    assert match_ingredient("egg", truth) == "eggs"
    assert match_ingredient("carrot", truth) == "carrots"
    assert match_ingredient("onion", truth) == "onion"
    assert match_ingredient("green_onion", truth) == "green_onion"
    assert match_ingredient("vanilla", truth) is None


def test_match_ingredient_ambiguous_matches_neither():
    # "sauce" is one token away from both entries: a tie, so no match.
    truth = ["soy_sauce", "chili_sauce"]
    assert match_ingredient("sauce", truth) is None


def _estimate(amounts):
    return {
        "dish": "test",
        "amounts": [
            {
                "ingredient_id": ing,
                "amount": amount,
                "unit": unit,
                "band_low": low,
                "band_high": high,
                "support": "anchored",
                "publishable": True,
                "evidence_frame": "frame_01.jpg",
                "note": "",
            }
            for ing, amount, unit, low, high in amounts
        ],
    }


_TRUTH = {
    "dish": "test",
    "success_bar_percent": 25,
    "ingredients": [
        {"id": "soy_sauce", "name": "soy sauce", "amount": 7.5, "unit": "ml"},
        {"id": "onion", "name": "onion", "amount": 0.25, "unit": "whole"},
        {"id": "eggs", "name": "eggs", "amount": 2, "unit": "count"},
    ],
}


def test_score_converts_units_before_comparing():
    result = score(_estimate([("soy_sauce", 0.5, "Tbsp", 0.4, 0.6)]), _TRUTH)
    row = result["rows"][0]
    assert row["status"] == "scored"
    assert row["estimate"] == 7.5
    assert row["error_percent"] == 0.0
    assert row["within_bar"] is True
    assert row["band_contains_truth"] is True


def test_score_matches_normalized_ids():
    result = score(_estimate([("egg", 2, "count", 1, 3)]), _TRUTH)
    assert result["rows"][0]["status"] == "scored"
    assert result["rows"][0]["matched_id"] == "eggs"
    assert "eggs" not in result["missing_ingredients"]


def test_score_unit_mismatch_is_listed_not_scored():
    result = score(_estimate([("onion", 22, "slices", 20, 24)]), _TRUTH)
    row = result["rows"][0]
    assert row["status"] == "unit_mismatch"
    assert result["summary"]["ingredients_scored"] == 0
    assert result["summary"]["unit_mismatches"] == 1
    # The ingredient was read, so it is not "missing"; it is unscored.
    assert "onion" not in result["missing_ingredients"]


def test_score_own_name_unit_counts_the_ingredient():
    # A read of 0.25 "onion" is a quarter of an onion.
    result = score(_estimate([("onion", 0.25, "onion", 0.0, 0.5)]), _TRUTH)
    row = result["rows"][0]
    assert row["status"] == "scored"
    assert row["error_percent"] == 0.0
