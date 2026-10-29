import json
from pathlib import Path

from by_eye.clients import StubClient, get_client, load_key
from by_eye.estimate import build_estimate
from by_eye.evaluate import load_ground_truth, score

ROOT = Path(__file__).resolve().parents[1]
TRUTH = load_ground_truth(ROOT / "data" / "ground_truth_pad_woon_sen.json")


def stub_estimate():
    return build_estimate(StubClient().read_ingredients([]), dish=TRUTH["dish"])


def test_stub_covers_every_ground_truth_ingredient():
    estimate = stub_estimate()
    result = score(estimate, TRUTH)
    assert result["missing_ingredients"] == []
    assert result["summary"]["ingredients_scored"] == len(TRUTH["ingredients"])


def test_counted_amounts_are_exact_in_stub():
    result = score(stub_estimate(), TRUTH)
    by_id = {r["ingredient_id"]: r for r in result["rows"]}
    assert by_id["eggs"]["error_percent"] == 0.0
    assert by_id["tomato"]["error_percent"] == 0.0


def test_weak_reads_are_struck_from_the_card():
    estimate = stub_estimate()
    by_id = {a["ingredient_id"]: a for a in estimate["amounts"]}
    # A shake of pepper, a heaped spoon, a splash of water: no numbers
    # on the card without support. They stay in the data, flagged.
    assert by_id["white_pepper"]["publishable"] is False
    assert by_id["water"]["publishable"] is False


def test_bands_widen_as_support_weakens():
    estimate = stub_estimate()
    by_id = {a["ingredient_id"]: a for a in estimate["amounts"]}

    def frac(a):
        return (a["band_high"] - a["band_low"]) / 2 / a["amount"]

    assert frac(by_id["chicken"]) < frac(by_id["oyster_sauce"]) < frac(by_id["water"])


def test_counted_bands_carry_one_step_of_uncertainty():
    estimate = stub_estimate()
    by_id = {a["ingredient_id"]: a for a in estimate["amounts"]}
    eggs = by_id["eggs"]
    assert eggs["band_low"] <= 1.0 and eggs["band_high"] >= 3.0
    garlic = by_id["garlic"]
    assert garlic["band_low"] <= 2.0 <= garlic["band_high"]


def test_score_reports_bar_and_band_honesty():
    result = score(stub_estimate(), TRUTH)
    assert result["bar_percent"] == 25.0
    assert result["summary"]["within_bar"] >= 10
    assert result["summary"]["bands_containing_truth"] >= result["summary"]["within_bar"]


def test_auto_mode_falls_back_to_stub_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr("by_eye.clients.KEYS_ENV_PATH", tmp_path / "absent.env")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    assert get_client("auto").name == "stub"
    assert load_key("BASETEN_API_KEY") is None


def test_ground_truth_matches_published_recipe():
    by_id = {i["id"]: i for i in TRUTH["ingredients"]}
    assert by_id["glass_noodles_dry"]["amount"] == 40
    assert by_id["chicken"]["amount"] == 170
    assert by_id["oyster_sauce"]["amount"] == 15
    assert TRUTH["video_url"].endswith("Amd2NR0n0WQ")


def test_sample_estimate_file_matches_stub_output():
    sample = json.loads((ROOT / "examples" / "sample_estimate.json").read_text())
    assert sample == stub_estimate()
