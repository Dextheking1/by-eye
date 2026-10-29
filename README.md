# By Eye

Pre-existing vs built this week: nothing in this repo predates the event. The concept and design notes were written before the build window; every line of code, data, and documentation in this repository was built this week, during the event period (Oct 27 to Nov 4, 2026).

Tagline: measured from her hands.

## What it is

A family cook who never measures anything cooks a dish on phone video, narrating the way she always does: "flour, until it feels right." By Eye turns that footage into a written recipe card where every amount is an estimate with its evidence attached: the frame it was measured from, the measurement behind it, and an honest approximation band. Her own phrases stay verbatim wherever a number would be a lie. The card is the artifact: printable, shareable, written to be cooked from by the next generation.

## Pipeline

1. Frames in. Video is sampled into frames and scene segments.
2. Measure. A vision model reads the frames: which ingredient, what vessel, how full, pour start and stop. A known-size anchor in frame (a hand, a standard mug) converts pixels to physical size. A small density table converts volume to grams.
3. Estimate out. Each amount leaves with its anchor chain and an approximation band. Amounts with no anchor and no evidence frame get struck by an adversarial pass and demoted to the cook's own words.
4. Score. Estimates are compared against a weighed or published ground truth, per ingredient, as percentage error, with the band checked for honesty: the band should contain the truth.

## Ground-truth test target

Pailin Chongchitnant's Pad Woon Sen (glass noodle stir fry), Hot Thai Kitchen.

- Video: https://www.youtube.com/watch?v=Amd2NR0n0WQ
- Ground truth recipe: https://hot-thai-kitchen.com/glass-noodle-stir-fry/ (the recipe page for that exact video), stored in `data/ground_truth_pad_woon_sen.json`
- Success bar: main ingredient amounts within about plus or minus 25 percent, with honest bands that contain the truth. Where the bar fails, bands widen and the cook's phrases carry the recipe instead of a number.

Note: the video and recipe are the creator's work. Permission from the creator is required before any public or demo use of the footage. In this repo the video is a reference link only; the pipeline runs on the published recipe data and on stills the project has the rights to use.

## Run it

No dependencies beyond Python 3.11+.

Stub mode (no API key needed, deterministic sample estimate):

```sh
python -m by_eye.cli run --mode stub --out out/estimate.json
python -m by_eye.cli evaluate --estimate out/estimate.json
```

Live mode (Baseten, Muse Spark Open) once the key is in `~/workspace/free-tiers/keys.env` as `BASETEN_API_KEY`:

```sh
python -m by_eye.cli run --mode baseten --frames path/to/frames_dir --out out/estimate.json
python -m by_eye.cli evaluate --estimate out/estimate.json
```

Meta mode (hosted Meta Model API) once the key is in `~/workspace/free-tiers/keys.env` as `META_API_KEY`. SAM 3.1 segments every frame first and its boxes and mask coverage ride on each amount as evidence; hosted Muse Spark 1.3 does the frame read; one retry per skipped frame:

```sh
python -m by_eye.cli run --mode meta --frames path/to/frames_dir --out out/estimate.json
```

Narration: Muse Voice Transcribe turns the cook's narration (WAV, mono 16-bit PCM) into the phrases the card keeps verbatim. Attach it to a run, or transcribe on its own:

```sh
python -m by_eye.cli run --mode meta --frames path/to/frames_dir --narration narration.wav --out out/estimate.json
python -m by_eye.cli transcribe --audio narration.wav --out out/transcript.json
```

The SAM mask decoder uses the optional `meta-sam-parser` package when installed (`pip install meta-sam-parser`); without it, SAM boxes still land as evidence and mask areas are reported as undecodable instead of guessed.

Tests:

```sh
python -m pytest tests/ -q
```

## Layout

- `src/by_eye/frames.py` - frame sampling and segmentation interface
- `src/by_eye/clients.py` - model client layer: stub, Baseten, generic OpenAI-compatible, and the hosted Meta Model API client (SAM 3.1 segmentation evidence, Muse Spark 1.3 reads, Muse Voice transcription, Muse Image) behind one interface
- `src/by_eye/measure.py` - anchors, density table, band logic
- `src/by_eye/estimate.py` - estimate schema and recipe card assembly
- `src/by_eye/evaluate.py` - per-ingredient scoring against ground truth
- `src/by_eye/cli.py` - command line entry point
- `data/ground_truth_pad_woon_sen.json` - published recipe amounts, the scoring target
- `examples/sample_estimate.json` - the sample estimate the stub produces
