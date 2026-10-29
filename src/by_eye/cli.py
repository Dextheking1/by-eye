"""By Eye command line.

run:      frames in, estimate out (stub mode works with no key)
evaluate: estimate vs ground truth, per-ingredient report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from by_eye.clients import get_client
from by_eye.estimate import build_estimate, load_estimate, save_estimate
from by_eye.evaluate import format_report, load_ground_truth, score
from by_eye.frames import sample_frames

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GROUND_TRUTH = REPO_ROOT / "data" / "ground_truth_pad_woon_sen.json"
DEFAULT_DISH = "Pad Woon Sen (glass noodle stir fry)"


def cmd_run(args: argparse.Namespace) -> int:
    client = get_client(args.mode)
    frame_refs: list[str] = []
    if args.frames:
        frame_refs = sample_frames(args.frames).frames
    read = client.read_ingredients(frame_refs)
    estimate = build_estimate(read, dish=args.dish)
    if args.narration:
        from by_eye.clients import MetaModelClient

        narration = MetaModelClient().transcribe(args.narration)
        estimate["narration"] = {
            "transcript": narration["transcript"],
            "model": narration["model"],
            "audio_duration_ms": narration["audio_duration_ms"],
        }
        print(f"narration: {narration['transcript'][:80]}")
    out = save_estimate(estimate, args.out)
    print(f"client: {read.client}")
    print(f"amounts: {len(estimate['amounts'])}")
    print(f"estimate written: {out}")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    from by_eye.clients import MetaModelClient

    result = MetaModelClient().transcribe(args.audio)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"model: {result['model']}")
    print(f"transcript: {result['transcript']}")
    print(f"written: {out}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    estimate = load_estimate(args.estimate)
    truth = load_ground_truth(args.ground_truth)
    result = score(estimate, truth)
    print(format_report(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="by_eye")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="frames in, estimate out")
    p_run.add_argument("--mode", choices=["auto", "stub", "baseten", "meta"], default="auto")
    p_run.add_argument("--frames", default=None, help="video file or directory of frames")
    p_run.add_argument("--dish", default=DEFAULT_DISH)
    p_run.add_argument("--narration", default=None, help="narration WAV to transcribe with Muse Voice and attach to the estimate")
    p_run.add_argument("--out", default="out/estimate.json")
    p_run.set_defaults(fn=cmd_run)

    p_tr = sub.add_parser("transcribe", help="narration WAV in, transcript out (Muse Voice Transcribe)")
    p_tr.add_argument("--audio", required=True)
    p_tr.add_argument("--out", default="out/transcript.json")
    p_tr.set_defaults(fn=cmd_transcribe)

    p_eval = sub.add_parser("evaluate", help="score an estimate against ground truth")
    p_eval.add_argument("--estimate", required=True)
    p_eval.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    p_eval.set_defaults(fn=cmd_evaluate)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
