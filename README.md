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

No non-Meta model is called at runtime by the app, the server, or the CLI.

Live mode (Meta, the default) once the key is in `~/workspace/free-tiers/keys.env` as `META_API_KEY`. This is the hosted Meta Model API route. SAM 3.1 segments every frame first and its boxes and mask coverage ride on each amount as evidence; hosted Muse Spark 1.3 does the frame read; one retry per skipped frame:

```sh
python -m by_eye.cli run --mode meta --frames path/to/frames_dir --out out/estimate.json
python -m by_eye.cli evaluate --estimate out/estimate.json
```

The CLI default is `--mode meta`, and `--mode auto` also resolves to the Meta client when `META_API_KEY` exists, falling back to stub when it does not. Auto never selects Baseten.

Stub mode (no API key needed, deterministic sample estimate):

```sh
python -m by_eye.cli run --mode stub --out out/estimate.json
python -m by_eye.cli evaluate --estimate out/estimate.json
```

Narration: Muse Voice Transcribe turns the cook's narration (WAV, mono 16-bit PCM) into the phrases the card keeps verbatim. Attach it to a run, or transcribe on its own:

```sh
python -m by_eye.cli run --mode meta --frames path/to/frames_dir --narration narration.wav --out out/estimate.json
python -m by_eye.cli transcribe --audio narration.wav --out out/transcript.json
```

Baseten (explicit only, never the default): `--mode baseten` runs Muse Spark Open, a Meta open weight model served by Baseten, a third party host. It runs only when named explicitly:

```sh
python -m by_eye.cli run --mode baseten --frames path/to/frames_dir --out out/estimate.json
```

The SAM mask decoder uses the optional `meta-sam-parser` package when installed (`pip install meta-sam-parser`); without it, SAM boxes still land as evidence and mask areas are reported as undecodable instead of guessed.

Recorded runs and judge rerun: the scored runs recorded in this repo were live Meta Model API runs (mode meta), and the demo footage of a scan is a recording of those runs. A judge can rerun live with a `META_API_KEY` of their own in `~/workspace/free-tiers/keys.env` or in the environment. The hosted route needs no GPU and no gated model weights. The optional `meta-sam-parser` package only decodes SAM masks locally; it makes no model call.

Demo narration disclosure: the demo video narration was generated offline with ElevenLabs text to speech. It is not a product feature, and the product makes no text to speech call at runtime.

Tests:

```sh
python -m pytest tests/ -q
```

## Layout

The shipped product is the plate pipeline below: the app sends a plate photo to the server, the server runs the plate pipeline, and the app renders the result.

- `src/by_eye/plate.py` - plate pipeline, the product runtime: Muse Spark 1.3 identifies each item on the plate and measures its amount, SAM 3.1 segments each item so the mask is the measurement evidence, both via the hosted Meta Model API
- `server/` - FastAPI server: `POST /scan` runs the plate pipeline above, so its only runtime models are Muse Spark 1.3 and SAM 3.1
- `app/` - Expo mobile app: uploads the plate photo to the server and renders the returned amounts and outlines; the app makes no AI call of its own
- `src/by_eye/frames.py` - frame sampling and segmentation interface
- `src/by_eye/clients.py` - model client layer behind one interface: the hosted Meta Model API client first (SAM 3.1 segmentation evidence, Muse Spark 1.3 reads, Muse Voice transcription, Muse Image), plus stub and an explicit Baseten client. The generic OpenAI-compatible client in this file is a dev comparison harness only, used by `bakeoff.py`; it is not reachable from `get_client`, the CLI, the app, or the server
- `src/by_eye/measure.py` - anchors, density table, band logic
- `src/by_eye/estimate.py` - estimate schema and recipe card assembly
- `src/by_eye/evaluate.py` - per-ingredient scoring against ground truth
- `src/by_eye/cli.py` - command line entry point; the run default is `--mode meta`
- `data/ground_truth_pad_woon_sen.json` - published recipe amounts, the scoring target
- `examples/sample_estimate.json` - the sample estimate the stub produces
