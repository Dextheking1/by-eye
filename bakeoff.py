"""Reasoning-pass bake-off harness.

Fixed tasks drawn from the Pad Woon Sen ground truth. Every candidate
model gets the same prompts, built from the StubClient observations
(the pipeline's day-one sample reads), so the comparison is about the
reasoning pass only: estimating what was not observed, calibrating
honest bands, and applying the adversarial strike gate.

Tasks:
  A  completion: 10 ingredients observed, 6 withheld. Estimate the
     withheld amounts, each with a band.
  B  calibration: all 16 observed. Return a final amount and band for
     each; counted reads stay tight, weak reads (a shake, a splash, a
     heap) get wide bands.
  C  strike gate: 6 candidate amounts with mixed evidence. Decide
     which may be published as numbers on the card under the rule:
     publishable only when the read is not weak AND an evidence frame
     exists.

Scoring per model: JSON format reliability per task, MAE percent
against ground truth, share within the plus/minus 25 percent bar,
band coverage (truth inside the model's own band), strike accuracy.
Raw outputs and usage are saved next to this file as
bakeoff-results-20261027.json.

Run: PYTHONPATH=src python3 bakeoff.py [model_label ...]
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from by_eye.clients import OpenAICompatClient, StubClient  # noqa: E402
from by_eye.estimate import build_estimate  # noqa: E402
from by_eye.evaluate import load_ground_truth, score  # noqa: E402

ROOT = Path(__file__).parent
TRUTH = load_ground_truth(ROOT / "data" / "ground_truth_pad_woon_sen.json")
TRUTH_BY_ID = {i["id"]: i for i in TRUTH["ingredients"]}
OBS = {ing: (amt, unit, note) for ing, amt, unit, _f, note in StubClient.SAMPLE}

WITHHELD = [
    "glass_noodles_dry",
    "chicken",
    "cabbage",
    "oyster_sauce",
    "sugar",
    "water",
]
OBSERVED = [i for i in OBS if i not in WITHHELD]

JSON_RULE = (
    "Return only a JSON array, no prose, no code fences. One object per "
    "ingredient with keys: ingredient_id, amount, band_low, band_high. "
    "amount, band_low and band_high are numbers in the ingredient's unit. "
    "The band is your honest uncertainty range: the true amount should "
    "plausibly fall inside it."
)


def obs_lines(ids):
    lines = []
    for i in ids:
        amt, unit, note = OBS[i]
        lines.append(
            f"- {i} ({TRUTH_BY_ID[i]['name']}): observed {amt} {unit}. "
            f"Reader note: {note}"
        )
    return "\n".join(lines)


def task_a_prompt() -> str:
    withheld_lines = "\n".join(
        f"- {i} ({TRUTH_BY_ID[i]['name']}, unit {TRUTH_BY_ID[i]['unit']})"
        for i in WITHHELD
    )
    return (
        "You are the reasoning pass of a cooking measurement system. "
        "The dish is Pad Woon Sen (Thai glass noodle stir fry, 2 servings). "
        "A vision reader observed these ingredients being added:\n"
        f"{obs_lines(OBSERVED)}\n\n"
        "These ingredients were also added but NOT observed. Estimate each "
        "amount from the dish, the servings and the observed amounts:\n"
        f"{withheld_lines}\n\n"
        f"{JSON_RULE}"
    )


def task_b_prompt() -> str:
    return (
        "You are the reasoning pass of a cooking measurement system. "
        "The dish is Pad Woon Sen (Thai glass noodle stir fry, 2 servings). "
        "A vision reader produced these reads. The reader note tells you "
        "how each amount was seen: counted directly (tight), sized "
        "against a hand or bowl (medium), a pour judged by stream and "
        "duration (loose), or a shake, splash or heap (very loose).\n"
        f"{obs_lines(list(OBS))}\n\n"
        "Return a final estimate for every ingredient. Keep your amount "
        "near the read unless the dish itself says otherwise, and set "
        "the band width to match how the amount was seen.\n\n"
        f"{JSON_RULE}"
    )


STRIKE_CANDIDATES = [
    ("eggs", 2.0, "count", "frame_000410", "two eggs cracked into the pan, counted directly"),
    ("chicken", 150.0, "g", "frame_000240", "sliced pieces in one layer on the board, sized against the board"),
    ("oyster_sauce", 16.0, "ml", "frame_000640", "sauce bowl pour, stream width plus duration"),
    ("white_pepper", 0.25, "tsp", "frame_000700", "one shake over the noodles"),
    ("water", 40.0, "ml", "frame_000800", "splash from the bowl rinse"),
    ("cabbage", 1.2, "cup", "", "two loose handfuls, no usable frame"),
]
STRIKE_PUBLISH = {"eggs", "chicken", "oyster_sauce"}
STRIKE_STRIKE = {"white_pepper", "water", "cabbage"}


def task_c_prompt() -> str:
    lines = "\n".join(
        f"- {i}: {amt} {unit}, evidence frame: {frame or 'NONE'}, "
        f"reader note: {note}"
        for i, amt, unit, frame, note in STRIKE_CANDIDATES
    )
    return (
        "You are the adversarial reviewer of a recipe card. Rule: an "
        "amount may be published as a number only when its read is "
        "supported AND an evidence frame exists. A read is weak when it "
        "rests on a shake, a splash, a heap or a guess; weak reads are "
        "struck even when a frame exists. A read with no evidence frame "
        "is struck even when the read itself looks solid.\n\n"
        f"Candidate amounts:\n{lines}\n\n"
        "Return only a JSON object, no prose, no code fences, with keys "
        '"publish" and "strike", each a list of ingredient_id strings. '
        "Every candidate goes in exactly one list."
    )


def extract_json(text: str):
    """Best-effort JSON extraction: strip fences, take the outermost
    array or object. Returns None when nothing parses."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def score_amounts(rows, expected_ids):
    """rows: parsed JSON list. Returns metrics dict or None if unusable."""
    if not isinstance(rows, list):
        return None
    by_id = {}
    for r in rows:
        if isinstance(r, dict) and "ingredient_id" in r:
            try:
                by_id[r["ingredient_id"]] = (
                    float(r["amount"]),
                    float(r["band_low"]),
                    float(r["band_high"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
    scored = [i for i in expected_ids if i in by_id]
    if not scored:
        return {"format_ok": False, "ids_returned": sorted(by_id)}
    errors, covered, within = [], 0, 0
    detail = {}
    for i in scored:
        truth = float(TRUTH_BY_ID[i]["amount"])
        amt, low, high = by_id[i]
        err = abs(amt - truth) / truth * 100 if truth else 0.0
        errors.append(err)
        if low - 1e-9 <= truth <= high + 1e-9:
            covered += 1
        if err <= 25.0:
            within += 1
        detail[i] = {
            "truth": truth,
            "amount": amt,
            "err_percent": round(err, 1),
            "band": [low, high],
            "band_holds": low - 1e-9 <= truth <= high + 1e-9,
        }
    return {
        "format_ok": len(scored) == len(expected_ids),
        "ids_scored": len(scored),
        "mae_percent": round(sum(errors) / len(errors), 1),
        "within_25": within,
        "band_coverage": covered,
        "detail": detail,
    }


def score_strike(parsed):
    if not isinstance(parsed, dict):
        return {"format_ok": False}
    publish = set(parsed.get("publish") or [])
    strike = set(parsed.get("strike") or [])
    correct = len(publish & STRIKE_PUBLISH) + len(strike & STRIKE_STRIKE)
    return {
        "format_ok": publish | strike == STRIKE_PUBLISH | STRIKE_STRIKE
        and not (publish & strike),
        "decisions_correct": correct,
        "decisions_total": 6,
        "publish": sorted(publish),
        "strike": sorted(strike),
    }


def call_with_retry(client, prompt, attempts=3, max_tokens=8000):
    last = None
    for n in range(attempts):
        try:
            return client.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0,
            )
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503) and n < attempts - 1:
                time.sleep(20 * (n + 1))
                continue
            raise
    raise last


def run_model(label, client):
    print(f"== {label} ({client.model}) ==", flush=True)
    out = {"label": label, "model": client.model, "base_url": client.base_url}
    tasks = [
        ("task_a_completion", task_a_prompt(), lambda p: score_amounts(p, WITHHELD)),
        ("task_b_calibration", task_b_prompt(), lambda p: score_amounts(p, list(OBS))),
        ("task_c_strike", task_c_prompt(), score_strike),
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for name, prompt, scorer in tasks:
        started = time.time()
        try:
            content, usage = call_with_retry(client, prompt)
            parsed = extract_json(content)
            result = scorer(parsed) if parsed is not None else {"format_ok": False}
            result["latency_s"] = round(time.time() - started, 1)
            result["usage"] = usage
            result["raw"] = content[:4000]
            for k in total_usage:
                total_usage[k] += int(usage.get(k) or 0)
            print(f"  {name}: {json.dumps({k: v for k, v in result.items() if k not in ('raw', 'detail')})}", flush=True)
        except Exception as e:  # recorded, not hidden: failure is data
            result = {"format_ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            print(f"  {name}: ERROR {result['error']}", flush=True)
        out[name] = result
        time.sleep(3)
    out["total_usage"] = total_usage
    return out


def candidate_clients():
    return {
        "baseten-muse-spark-open": OpenAICompatClient(
            base_url="https://inference.baseten.co/v1",
            model="meta-models/muse-spark-open-1026",
            key_name="BASETEN_API_KEY",
            name="baseten-muse-spark-open",
        ),
        "pollinations-gpt-5.5": OpenAICompatClient(
            base_url="https://gen.pollinations.ai/v1",
            model="openai/gpt-5.5",
            key_name=None,
            name="pollinations-gpt-5.5",
        ),
        "pollinations-deepseek-v4.1-flash": OpenAICompatClient(
            base_url="https://gen.pollinations.ai/v1",
            model="deepseek/deepseek-v4.1-flash",
            key_name=None,
            name="pollinations-deepseek-v4.1-flash",
        ),
        "mistral-magistral-medium": OpenAICompatClient(
            base_url="https://api.mistral.ai/v1",
            model="magistral-medium-latest",
            key_name="MISTRAL_API_KEY",
            name="mistral-magistral-medium",
        ),
        "mistral-medium-3.5": OpenAICompatClient(
            base_url="https://api.mistral.ai/v1",
            model="mistral-medium-3.5",
            key_name="MISTRAL_API_KEY",
            name="mistral-medium-3.5",
        ),
    }


def main():
    wanted = sys.argv[1:]
    clients = candidate_clients()
    labels = wanted or list(clients)
    results = []
    for label in labels:
        results.append(run_model(label, clients[label]))
    # Reference row: the pipeline's own rule-based bands on the stub
    # reads (task B context, no LLM involved).
    ref = score(build_estimate(StubClient().read_ingredients([]), TRUTH["dish"]), TRUTH)
    payload = {
        "dish": TRUTH["dish"],
        "results": results,
        "pipeline_reference_task_b": ref["summary"],
    }
    out_path = ROOT / "bakeoff-results-20261027.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
