# Meta Model API capability tests, 2026-10-29

Run before integrating, per the build order: test the real hosted API
first, integrate what passes. Key: META_API_KEY in
~/workspace/free-tiers/keys.env (value never printed). Base URL for
all HTTP calls: https://api.meta.ai/v1, Bearer auth. Model list
verified live via GET /v1/models on 2026-10-29: muse-wonder-1.0,
sam-3.1, muse-spark-1.3, muse-spark-1.3-contributor, muse-spark-1.2,
muse-spark-1.1, muse-image-1.0, muse-voice-transcribe-1.0.

## SAM 3.1 segmentation: PASS, integrated

- Endpoint: POST /v1/responses, model sam-3.1. Chat completions
  refuses it with a pointer: "The model `sam-3.1` is not available on
  this endpoint. Use /v1/responses."
- Request: Responses input with one input_text (a short noun phrase
  prompt) and one input_image (base64 data URL).
- Response: output_text in the SAM special-token format, one record
  per object: box (x1, y1, x2, y2 in source pixels, with frame w/h)
  plus a mask (height, width, base85 payload, first char ~ for the
  lossless encoding). Masks decode strictly with the meta-sam-parser
  package (decode_mask_to_raster); an empty output_text is a valid
  no-match response, not an error.
- Measured results on the synthetic Pad Woon Sen frames (854x480):
  - tomato, prompt "tomato": 1 object, box 332,130 to 522,320, mask
    21,688 px, 60.1 percent of its box, 5.3 percent of frame. Tight.
  - cabbage, prompt "cabbage": 1 object, the filled cup contents,
    box 306,165 to 555,415, mask 46,860 px, 75.2 percent of box.
  - oyster sauce frame, prompt "measuring jug": 1 object, the liquid
    region inside the jug, mask 9,442 px, 63.8 percent of box. It
    found the liquid, not the glass.
  - eggs, prompt "egg": 2 objects, one real egg (mask 8,042 px) plus
    a false positive on the printed count banner (mask 23,548 px).
    Only one of the two drawn eggs matched.
  - chicken, prompts "chicken" and "raw chicken pieces": no match.
    The flat drawn chicken pieces are not recognized.
  - noodles, prompts "glass noodles" and "noodles": no match. Thin
    drawn lines are not recognized.
- Verdict: mask quality is good enough for measurement evidence on
  solid, photo-like objects (produce, vessels, liquid levels). It is
  weak on flat illustration-style content, which is what the
  synthetic frames are. On real footage the solid-object case is the
  one that matters. Integrated as the measurement evidence pass: SAM
  runs on every frame, its box and mask coverage ride on each amount
  as evidence, and a no-match is recorded as no-match, never hidden.

## Muse Voice Transcribe: PASS, integrated

- Batch endpoint POST /v1/audio/transcriptions does not exist (404).
  The file route is POST /v1/asr/transcribe, multipart with two
  parts: "request" (JSON: model plus audioEncoding) and "audio"
  (the file). Input is narrow: WAV only in practice; the encoding
  value that works is "WAV" (PCM_S16LE, LINEAR16, pcm16 and PCM all
  return "Malformed request"). Mono 16-bit PCM WAV at 16 kHz was
  accepted.
- Test sample: synthesized narration (gTTS voice, synthetic, no real
  person), exact text known: "Add the glass noodles now, just until
  it feels right. Then the chicken, and a splash of water at the
  end." 7.84 seconds.
- Returned transcript: "Add the glass noodles now. Just until it
  until it feels right. Then the chicken. And a splash of water at
  the end." One duplicated word, one dropped conjunction; every
  content word correct. Good enough for the product use: the cook's
  own phrases are captured verbatim for the card.
- A realtime WebSocket route also exists
  (wss://api.meta.ai/v1/asr/realtime) but it cannot be driven from
  this VM: the egress proxy mangles the upgrade and direct egress
  times out. From the lab (direct internet) the socket connects, but
  the native handshake is a first JSON frame carrying the auth, not
  the OpenAI-style session.update we sent; the server answered
  "Handshake timeout" and closed 1008. The file route covers the
  pipeline's need (narration arrives as a recording), so realtime is
  noted, not integrated.

## Muse Spark 1.3 (hosted): PASS, integrated as the Meta reader

- Endpoint: POST /v1/chat/completions, model muse-spark-1.3.
- It is a reasoning model: at max_tokens 50 the whole budget went to
  reasoning tokens and the content came back null. Budgets of 4000
  work. Same behaviour as the Baseten Spark route, same mitigation.
- Vision test, 3 frames in one call (noodles, chicken, tomato):
  returned clean JSON reads, 40 g noodles, 170 g chicken, 1 tomato,
  all correct against ground truth. Usage: 1,614 prompt tokens,
  1,126 completion tokens (1,018 of them reasoning).
- Role in the build: the Meta client's frame reader, with SAM
  evidence in the prompt. The reasoning slot for the completion and
  strike passes stays on Baseten Spark per the bake-off.

## Muse Image 1.0: PASS, not pipeline-critical

- Endpoint: POST /v1/images/generations, model muse-image-1.0.
  Returns b64_json (WebP data). One test image generated: an
  overhead plate of pad woon sen for recipe card art, saved at
  out/meta-image-test.webp (918 KB response, $0.01).
- The measurement pipeline does not need image generation. It is
  demo asset tooling (card art), used only there.

## Integration outcome, 2026-10-29

MetaModelClient in src/by_eye/clients.py, mode "meta":

- segment(): SAM 3.1 per frame, boxes always parsed, mask areas
  decoded via meta-sam-parser when installed (optional; without it
  the box is the evidence and the area is reported undecodable).
  temperature 0 set after early calls showed mask variance.
- read_ingredients(): per-frame Spark calls, NOT batches. Measured
  reason: in batched calls the reader anchored on whichever frames
  carried SAM evidence and dropped the rest (2 of 16 reads), and
  no-match evidence blocks made it drop supported reads entirely
  (0 of 8 in the control). Per-frame calls with positive-only
  evidence in the prompt read 16 of 16. SAM results for every frame,
  match or no-match, are appended to each amount's note after the
  read, so the evidence chain is complete on the card.
- Completion pass: the hosted reader intermittently returns an
  empty array for a frame it reads fine on retry (rice frame:
  read, empty, read). One retry per skipped frame is now built in.
- transcribe(): Muse Voice file route as tested above.
- generate_image(): Muse Image, demo card art only.
- CLI: --mode meta, run --narration <wav> attaches the transcript
  to the estimate, and a transcribe subcommand.
- Tests: 22 of 22 green (7 new Meta client tests).

## Live runs on the Meta path

- Dish 1 (Pad Woon Sen, 16 synthetic frames): 16 of 16 within the
  bar, 16 of 16 bands hold, MAE 0.1 percent. Baseten on the same
  frames: 14 of 16, MAE 5.5 percent. Record:
  out/meta-run/run-summary.md.
- Dish 2 (garlic shrimp fried rice, synthetic fixture created for
  this retest, data/ground_truth_garlic_shrimp_fried_rice.json):

| Provider | Scored | In bar | MAE | Missing |
|---|---|---|---|---|
| Meta (SAM 3.1 + Spark 1.3 hosted) | 10 of 10 | 10 | 0.0% | none (completion pass caught rice) |
| DeepSeek v4-flash (web bridge) | 10 of 10 | 10 | 0.0% | none |
| Baseten Spark Open | 7 of 10 | 7 | 3.8% | rice, green onion, salt |
| MarsAI Opus 5.5 | not callable | | | HTTP 402 today |
| Forest DeepSeek-V4.1-Flash | 10 of 10 | 10 | 0.0% | none (slow, about 170 s for both batches; one later repeat attempt returned HTTP 400 with an empty error body, so the route is flaky, not dead) |

  DeepSeek completion-pass probe (text only, 6 observed amounts
  given, 4 withheld): rice and salt exact, soy and oil doubled
  (30 ml against 15). Its vision reads were exact on all 10.
  Caveat for the whole table: the synthetic frames print their
  values, so this ranks extraction reliability and coverage, not
  raw-footage estimation. The model split stands as: Meta models
  core (SAM evidence + Spark reads + Voice narration), Baseten
  Spark as the paid-stable reasoning route for the completion and
  strike passes, DeepSeek bridge as a free second reader.

## Spend tally (final for this build, 2026-10-29)

Prices: SAM $2.50 per 1,000 images; Spark standard $1.25 in /
$4.25 out per million tokens; Muse Image $0.01 per image; Voice
$0.18 per audio hour.

| Provider | Use in this build | Estimated spend |
|---|---|---|
| Meta Model API | about 110 SAM images across probes, integration runs and both dishes; about 200k Spark tokens; 1 Muse Image; about 40 s of voice transcription across tests | about $0.60 of the $150 credit. Nowhere near the credit edge; no card charges beyond credit expected |
| Baseten | dish 2 eval, 2 batched calls (10 frames) | $0 out of pocket (partner credit) |
| DeepSeek web bridge | dish 2 vision eval (2 calls) plus completion probe | $0 (Benjamin's web account route) |
| MarsAI | 1 call attempt | $0, HTTP 402 |
| Forest proxy | dish 2 vision eval, 2 batched calls (10 frames), plus one failed repeat attempt | $0 (free route); eval succeeded 10 of 10, route flaky |
| Fireworks | no API key in keys.env, cannot call | $0, blocked on key |
| Modal | no token configured on this VM, cannot call | $0, blocked on setup |

Fireworks and Modal detail: the credits exist ($100 each, Fireworks
redeem-by Nov 3 2026), but there is no Fireworks API key and no
Modal token anywhere on this machine, so neither route could be
spent. Both need a credential step from Benjamin or the main agent
before the build can use them. Nothing was rationed on the routes
that do work; the Meta path ran at full width on every frame of
both dishes.
