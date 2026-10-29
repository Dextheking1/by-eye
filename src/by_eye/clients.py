"""Model client layer.

One interface, several implementations:

- StubClient: deterministic, offline, no key needed. Produces a fixed
  sample read of the Pad Woon Sen ingredients so the whole pipeline can
  run end to end on day one.
- BasetenClient: Muse Spark Open over Baseten's OpenAI-compatible API
  (base https://inference.baseten.co/v1, model
  meta-models/muse-spark-open-1026). The key is read from
  ~/workspace/free-tiers/keys.env as BASETEN_API_KEY, or from the
  BASETEN_API_KEY environment variable. Key values are never printed
  and never stored in this repo.
- OpenAICompatClient: a generic OpenAI-compatible chat client for the
  reasoning pass. Base URL, model id and key name are parameters (or
  BY_EYE_* environment variables), so any provider that speaks
  /chat/completions can fill the reasoning slot without new code:
  Pollinations, Mistral, OpenRouter, Nebius Token Factory. Named
  presets live in get_client.
- MetaModelClient: the hosted Meta Model API (base
  https://api.meta.ai/v1, key META_API_KEY in keys.env). SAM 3.1
  segmentation is the measurement evidence pass (POST /v1/responses;
  boxes and masks parsed from the SAM output format), Muse Spark 1.3
  hosted does the frame read with the SAM evidence in its prompt,
  Muse Voice Transcribe turns narration audio into the cook's own
  words (POST /v1/asr/transcribe), and Muse Image 1.0 is available
  for card art. Capability evidence: meta-api-capability-20261029.md.

The pipeline does not depend on which client produced the reads.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

BASETEN_BASE_URL = "https://inference.baseten.co/v1"
BASETEN_MODEL = "meta-models/muse-spark-open-1026"
META_BASE_URL = "https://api.meta.ai/v1"
META_SPARK_MODEL = "muse-spark-1.3"
META_SAM_MODEL = "sam-3.1"
META_VOICE_MODEL = "muse-voice-transcribe-1.0"
META_IMAGE_MODEL = "muse-image-1.0"
KEYS_ENV_PATH = Path.home() / "workspace" / "free-tiers" / "keys.env"


@dataclass
class FrameRead:
    """One model's read of one ingredient in the footage."""

    ingredient_id: str
    observed_amount: float
    unit: str
    evidence_frame: str
    note: str = ""


@dataclass
class MeasurementRead:
    """Everything one client pass returns for one dish."""

    client: str
    reads: list[FrameRead] = field(default_factory=list)


class ModelClient:
    """Interface the pipeline codes against."""

    name = "base"

    def read_ingredients(self, frame_refs: list[str]) -> MeasurementRead:
        raise NotImplementedError


class StubClient(ModelClient):
    """Deterministic sample read, used when no key is available.

    The numbers are deliberately imperfect. They exist so scoring and
    band logic can be exercised honestly, not to fake a result.
    """

    name = "stub"

    SAMPLE = [
        ("glass_noodles_dry", 48.0, "g", "frame_000120", "dry bundle fills the small bowl, compared against hand width"),
        ("chicken", 140.0, "g", "frame_000240", "sliced pieces in one layer on the board"),
        ("soy_sauce_marinade", 5.0, "ml", "frame_000260", "one spoon over the chicken"),
        ("garlic", 3.0, "cloves", "frame_000310", "small pile, count is a guess, cloves vary"),
        ("onion", 0.5, "whole", "frame_000315", "a handful of strips, reads as half a small onion"),
        ("eggs", 2.0, "count", "frame_000410", "two eggs cracked into the pan, counted directly"),
        ("cabbage", 1.3, "cup", "frame_000520", "two loose handfuls"),
        ("carrots", 0.4, "cup", "frame_000525", "one small handful of slices"),
        ("white_pepper", 0.25, "tsp", "frame_000700", "one shake over the noodles, hard to read"),
        ("tomato", 1.0, "count", "frame_000900", "one tomato in wedges, counted directly"),
        ("green_onion", 1.0, "count", "frame_000905", "one stalk chopped over the top"),
        ("oyster_sauce", 18.0, "ml", "frame_000640", "sauce bowl pour, stream width plus duration"),
        ("soy_sauce", 8.0, "ml", "frame_000645", "sauce bowl pour"),
        ("golden_mountain_sauce", 7.0, "ml", "frame_000650", "sauce bowl pour"),
        ("sugar", 9.0, "ml", "frame_000655", "one heaped spoon, heap is the uncertainty"),
        ("water", 45.0, "ml", "frame_000800", "splash from the bowl rinse, weakest read in the set"),
    ]

    def read_ingredients(self, frame_refs: list[str]) -> MeasurementRead:
        reads = [
            FrameRead(
                ingredient_id=ing,
                observed_amount=amount,
                unit=unit,
                evidence_frame=frame,
                note=note,
            )
            for ing, amount, unit, frame, note in self.SAMPLE
        ]
        return MeasurementRead(client=self.name, reads=reads)


def load_key(name: str, keys_path: Path | None = None) -> str | None:
    """Read one key from the environment or the shared keys.env file.

    Returns None when absent. Never logs the value. keys_path defaults
    to the module-level KEYS_ENV_PATH resolved at call time, so tests
    can point it elsewhere.
    """
    if keys_path is None:
        keys_path = KEYS_ENV_PATH
    if os.environ.get(name):
        return os.environ[name]
    try:
        for line in keys_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                value = line.split("=", 1)[1].strip()
                return value or None
    except FileNotFoundError:
        return None
    return None


class BasetenClient(ModelClient):
    """Muse Spark Open on Baseten, vision reads over sampled frames."""

    name = "baseten"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or load_key("BASETEN_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "BASETEN_API_KEY not found in environment or "
                f"{KEYS_ENV_PATH}. Run in stub mode until the key lands."
            )

    def read_ingredients(self, frame_refs: list[str]) -> MeasurementRead:
        """Ask the model to read ingredient amounts from frame images.

        Expects a JSON array back, one object per ingredient. Any parse
        failure raises, so a bad read never silently becomes an amount.
        """
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "You are the measurement reader for a cooking video. "
                    "For each ingredient you can see being added, return one "
                    "JSON object with keys ingredient_id, observed_amount, "
                    "unit, evidence_frame, note. Amounts are your best "
                    "physical estimate from the frames. If you cannot "
                    "support an amount with what is visible, omit the "
                    "ingredient instead of guessing. Return only a JSON "
                    "array."
                ),
            }
        ]
        for ref in frame_refs:
            path = Path(ref)
            if path.is_file():
                data = base64.b64encode(path.read_bytes()).decode()
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
                    }
                )
            else:
                content.append({"type": "text", "text": f"frame reference: {ref}"})
        payload = {
            "model": BASETEN_MODEL,
            "messages": [{"role": "user", "content": content}],
        }
        request = urllib.request.Request(
            f"{BASETEN_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read())
        text = body["choices"][0]["message"]["content"]
        raw = json.loads(text)
        reads = [
            FrameRead(
                ingredient_id=item["ingredient_id"],
                observed_amount=float(item["observed_amount"]),
                unit=item["unit"],
                evidence_frame=item.get("evidence_frame", ""),
                note=item.get("note", ""),
            )
            for item in raw
        ]
        return MeasurementRead(client=self.name, reads=reads)


class OpenAICompatClient(ModelClient):
    """Generic OpenAI-compatible chat client for the reasoning pass.

    Text in, text out: this client fills the reasoning slot (estimating
    withheld amounts, calibrating bands, the adversarial strike pass),
    not the vision frame-read slot, so read_ingredients is not
    implemented. The key, when the provider needs one, is referenced by
    NAME and resolved through load_key; the value never lands in this
    repo or in any log.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        key_name: str | None = None,
        name: str = "openai-compat",
        api_key: str | None = None,
        timeout: int = 180,
        key_required: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key_name = key_name
        self.name = name
        self.timeout = timeout
        self._api_key = api_key
        if (
            key_required
            and key_name
            and api_key is None
            and load_key(key_name) is None
        ):
            raise RuntimeError(
                f"{key_name} not found in environment or {KEYS_ENV_PATH}."
            )

    def _key(self) -> str | None:
        if self._api_key is not None:
            return self._api_key
        if self.key_name:
            return load_key(self.key_name)
        return None

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> tuple[str, dict]:
        """One chat completion. Returns (content, usage dict).

        Raises on HTTP or parse failure, so a bad call never silently
        becomes an empty answer downstream.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        key = self._key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        message = body["choices"][0]["message"]
        content = (
            message.get("content")
            or message.get("reasoning_content")
            or message.get("reasoning")
            or ""
        )
        return content, body.get("usage") or {}

    def read_ingredients(self, frame_refs: list[str]) -> MeasurementRead:
        raise NotImplementedError(
            "OpenAICompatClient is the text reasoning pass; frame reads "
            "belong to a vision client (Baseten today)."
        )


@dataclass
class SegmentObject:
    """One SAM 3.1 object: a box, and a mask when it could be decoded."""

    object_id: str
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 inclusive, source px
    frame_width: int
    frame_height: int
    mask_area_px: int | None = None

    @property
    def box_area_px(self) -> int:
        x1, y1, x2, y2 = self.box
        return max(0, x2 - x1 + 1) * max(0, y2 - y1 + 1)

    @property
    def coverage_fraction(self) -> float | None:
        """Mask area as a fraction of the whole frame, when decoded."""
        if self.mask_area_px is None or not self.frame_width or not self.frame_height:
            return None
        return self.mask_area_px / (self.frame_width * self.frame_height)


_SAM_OBJECT_RE = re.compile(
    r"(?P<oid>\d+)<\|box;x1=(?P<x1>\d+);y1=(?P<y1>\d+);x2=(?P<x2>\d+);"
    r"y2=(?P<y2>\d+);w=(?P<w>\d+);h=(?P<h>\d+)\|>"
    r"(?:<\|mask;x=\d+;y=\d+;data=(?P<mh>\d+),(?P<mw>\d+),"
    r"(?P<payload>[^|>]+)\|>)?"
)


def _decode_mask_area(one_object_line: str) -> int | None:
    """Decode one SAM mask to a pixel count via meta-sam-parser.

    The wire payload is a custom base85 lossless encoding; the
    published parser decodes it strictly (streaming push/finish API,
    raster returned as raw bytes, one byte per pixel). When the
    package is not installed, or the payload does not decode, return
    None and let the box stand as the evidence. Never guess an area.
    """
    try:
        from meta_sam_parser import (
            CompletedOutcome,
            decode_mask_to_raster,
            image_segmentation_format,
        )

        parser = image_segmentation_format().create_parser()
        parser.push(one_object_line)
        result = parser.finish(CompletedOutcome()).result
        for record in result.records:
            mask = getattr(record, "mask", None)
            if mask is not None:
                raster = decode_mask_to_raster(mask)
                if isinstance(raster, (bytes, bytearray)):
                    return sum(1 for b in raster if b)
                try:
                    return int((raster > 0).sum())
                except TypeError:
                    return int(raster.sum())
    except Exception:
        return None
    return None


def parse_sam_output(text: str) -> list[SegmentObject]:
    """Parse SAM 3.1 output_text into segment objects.

    Empty text is a valid no-match response and returns []. Box
    fields are always parsed; mask areas are filled in when the
    payload decodes.
    """
    objects: list[SegmentObject] = []
    for line in text.splitlines():
        for match in _SAM_OBJECT_RE.finditer(line):
            obj = SegmentObject(
                object_id=match.group("oid"),
                box=(
                    int(match.group("x1")),
                    int(match.group("y1")),
                    int(match.group("x2")),
                    int(match.group("y2")),
                ),
                frame_width=int(match.group("w")),
                frame_height=int(match.group("h")),
            )
            if match.group("payload"):
                one = "<0f>" + line[match.start(): match.end()]
                obj.mask_area_px = _decode_mask_area(one)
            objects.append(obj)
    return objects


def _extract_json_array(text: str) -> list:
    """Pull a JSON array out of a model reply, fences and all."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON array in model reply: {text[:200]!r}")
    return json.loads(cleaned[start: end + 1])


class MetaModelClient(ModelClient):
    """Hosted Meta Model API: SAM 3.1 evidence plus Spark frame reads.

    read_ingredients runs SAM 3.1 on every frame first (one text
    prompt per frame, derived from the frame name or supplied), then
    asks hosted Muse Spark 1.3 to read the amounts with the SAM
    boxes and mask coverage in the prompt as measured evidence. The
    SAM result for each frame is appended to that read's note, so the
    evidence chain survives into the estimate and the card. A SAM
    no-match is recorded as a no-match.

    transcribe() and generate_image() cover the other two Meta
    specialists the product uses: narration in, card art out.
    """

    name = "meta"
    # One frame per Spark call. Batched calls were measured on
    # 2026-10-29 to anchor on whichever frames carried SAM evidence
    # and drop the rest (2 of 16 reads), whatever the instruction
    # wording. Per-frame calls read 8 of 8 in the control run.
    SPARK_BATCH = 1

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or load_key("META_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "META_API_KEY not found in environment or "
                f"{KEYS_ENV_PATH}. Run in stub mode until the key lands."
            )

    # -- transport -------------------------------------------------
    def _post_json(self, path: str, payload: dict, timeout: int = 180) -> dict:
        request = urllib.request.Request(
            f"{META_BASE_URL}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    # -- SAM 3.1 ---------------------------------------------------
    def segment(self, frame_path: str | Path, prompt: str) -> list[SegmentObject]:
        """Segment one frame with one noun-phrase prompt."""
        path = Path(frame_path)
        data = base64.b64encode(path.read_bytes()).decode()
        body = self._post_json(
            "/responses",
            {
                "model": META_SAM_MODEL,
                "temperature": 0,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{data}",
                            },
                        ],
                    }
                ],
            },
        )
        text = ""
        for item in body.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")
        return parse_sam_output(text)

    @staticmethod
    def prompt_for_frame(frame_ref: str) -> str:
        """Default SAM prompt from a frame file name.

        frame_10_tomato.jpg becomes "tomato"; frame_03_soy_marinade
        becomes "soy marinade". Callers with real footage pass their
        own prompts per frame instead.
        """
        stem = Path(frame_ref).stem
        stem = re.sub(r"^frame_\d+_", "", stem)
        words = stem.replace("_", " ").split()
        if words:
            last = words[-1]
            # SAM prompts work best as singular noun phrases:
            # "eggs" -> "egg", "glass noodles" -> "glass noodle".
            if len(last) > 3 and last.endswith("s") and not last.endswith("ss"):
                words[-1] = last[:-1]
        return " ".join(words).strip() or stem

    def _sam_evidence(
        self, frame_refs: list[str], prompts: dict[str, str] | None
    ) -> dict[str, tuple[str, list[SegmentObject]]]:
        evidence: dict[str, tuple[str, list[SegmentObject]]] = {}
        for ref in frame_refs:
            if not Path(ref).is_file():
                continue
            prompt = (prompts or {}).get(ref) or self.prompt_for_frame(ref)
            evidence[ref] = (prompt, self.segment(ref, prompt))
        return evidence

    @staticmethod
    def _evidence_note(prompt: str, objects: list[SegmentObject]) -> str:
        if not objects:
            return f"SAM 3.1: no match for '{prompt}'."
        best = max(objects, key=lambda o: o.mask_area_px or o.box_area_px)
        x1, y1, x2, y2 = best.box
        if best.mask_area_px is not None and best.coverage_fraction is not None:
            return (
                f"SAM 3.1: '{prompt}' mask {best.mask_area_px} px, "
                f"{best.coverage_fraction * 100:.1f}% of frame, "
                f"box {x1},{y1}-{x2},{y2}."
            )
        return f"SAM 3.1: '{prompt}' box {x1},{y1}-{x2},{y2} (mask undecodable)."

    # -- Muse Spark frame reads ------------------------------------
    def read_ingredients(
        self,
        frame_refs: list[str],
        prompts: dict[str, str] | None = None,
    ) -> MeasurementRead:
        evidence = self._sam_evidence(frame_refs, prompts)
        reads: list[FrameRead] = []
        files = [r for r in frame_refs if Path(r).is_file()]
        covered: set[str] = set()
        for start in range(0, len(files), self.SPARK_BATCH):
            batch = files[start: start + self.SPARK_BATCH]
            batch_reads = self._read_batch(batch, evidence)
            reads.extend(batch_reads)
            covered.update(
                r.evidence_frame for r in batch_reads
            )
        # Completion pass: the hosted reader intermittently returns
        # an empty array for a frame it reads fine on a retry
        # (measured 2026-10-29 on the rice frame: read, empty, read).
        # One retry per skipped frame, same as the Baseten run's
        # completion pass. A frame that stays empty stays missing;
        # the estimate then honestly lacks that ingredient.
        names = {Path(r).name: r for r in files}
        for name, ref in names.items():
            if name not in covered:
                reads.extend(self._read_batch([ref], evidence))
        if not files and frame_refs:
            raise ValueError("MetaModelClient needs frame image files on disk.")
        by_name = {Path(r).name: r for r in frame_refs}
        for read in reads:
            ref = by_name.get(read.evidence_frame)
            if ref and ref in evidence:
                prompt, objects = evidence[ref]
                note = self._evidence_note(prompt, objects)
                read.note = f"{read.note} {note}".strip()
        return MeasurementRead(client=self.name, reads=reads)

    def _read_batch(
        self,
        batch: list[str],
        evidence: dict[str, tuple[str, list[SegmentObject]]],
    ) -> list[FrameRead]:
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "You are the measurement reader for a cooking video. "
                    "For each ingredient you can see being added, return one "
                    "JSON object with keys ingredient_id, observed_amount, "
                    "unit, evidence_frame, note. evidence_frame must be the "
                    "exact frame file name the ingredient was read from. "
                    "Amounts are your best physical estimate from the "
                    "frames. Segmentation evidence from SAM 3.1 may be "
                    "listed for the frame; it is a supporting signal "
                    "only. A SAM no-match does NOT mean the ingredient is "
                    "absent: SAM misses thin, flat and drawn objects. For "
                    "counted items SAM may segment only one instance: "
                    "its count is a floor, not a total; count from the "
                    "image. If you cannot support an amount with what is "
                    "visible, omit the ingredient instead of guessing. "
                    "Return only a JSON array."
                ),
            }
        ]
        for ref in batch:
            path = Path(ref)
            data = base64.b64encode(path.read_bytes()).decode()
            content.append({"type": "text", "text": f"frame file: {path.name}"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{data}"},
                }
            )
            if ref in evidence:
                prompt, objects = evidence[ref]
                # Only positive SAM evidence goes in the prompt. A
                # no-match block makes the reader defer to SAM and
                # drop reads the image itself supports (measured on
                # the 2026-10-29 run: 8 of 8 reads without evidence,
                # 0 of 8 with no-match blocks). No-matches are still
                # recorded on the amount's note after the read.
                if objects:
                    content.append(
                        {"type": "text", "text": f"SAM evidence for {path.name}: "
                         + self._evidence_note(prompt, objects)}
                    )
        body = self._post_json(
            "/chat/completions",
            {
                "model": META_SPARK_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 6000,
            },
            timeout=240,
        )
        message = body["choices"][0]["message"]
        text = message.get("content") or ""
        raw = _extract_json_array(text)
        names = [Path(r).name for r in batch]
        stems = {Path(n).stem: n for n in names}
        reads = []
        for item in raw:
            frame = item.get("evidence_frame", "")
            if isinstance(frame, int) or (isinstance(frame, str) and frame.isdigit()):
                idx = int(frame)
                frame = names[idx - 1] if 1 <= idx <= len(names) else str(frame)
            elif isinstance(frame, str) and Path(frame).name in names:
                frame = Path(frame).name
            elif isinstance(frame, str) and Path(frame).stem in stems:
                frame = stems[Path(frame).stem]
            reads.append(
                FrameRead(
                    ingredient_id=item["ingredient_id"],
                    observed_amount=float(item["observed_amount"]),
                    unit=item["unit"],
                    evidence_frame=frame,
                    note=item.get("note", ""),
                )
            )
        return reads

    # -- Muse Voice Transcribe --------------------------------------
    def transcribe(self, audio_path: str | Path) -> dict:
        """Transcribe a narration recording (WAV) via /v1/asr/transcribe.

        The file route takes a multipart body with a "request" JSON
        part and an "audio" part. Only WAV is accepted in practice;
        anything else raises with the conversion hint.
        """
        path = Path(audio_path)
        if path.suffix.lower() != ".wav":
            raise ValueError(
                "Muse Voice file transcription takes WAV input; convert "
                f"first (ffmpeg -i in.mp3 -ar 16000 -ac 1 out.wav): {path}"
            )
        boundary = "----by-eye-" + uuid.uuid4().hex
        request_part = json.dumps(
            {"model": META_VOICE_MODEL, "audioEncoding": "WAV"}
        ).encode()
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f"name=\"request\"\r\nContent-Type: application/json\r\n\r\n"
        ).encode() + request_part + b"\r\n"
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f"name=\"audio\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode() + path.read_bytes() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            f"{META_BASE_URL}/asr/transcribe",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read())
        return {
            "transcript": result.get("transcript", ""),
            "audio_duration_ms": result.get("audioDurationMs"),
            "turns": result.get("turns", []),
            "model": META_VOICE_MODEL,
        }

    # -- Muse Image ---------------------------------------------------
    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        """One Muse Image generation, returned as raw image bytes."""
        body = self._post_json(
            "/images/generations",
            {"model": META_IMAGE_MODEL, "prompt": prompt, "size": size},
        )
        return base64.b64decode(body["data"][0]["b64_json"])


# Named presets for the reasoning slot. Model ids can be overridden
# with the BY_EYE_MODEL environment variable at construction time via
# get_client; key names refer to ~/workspace/free-tiers/keys.env.
OPENAI_PRESETS = {
    # Anonymous tier answers today for some models; paid_only models
    # need a Pollinations key (POLLINATIONS_API_KEY) when one lands.
    "pollinations": {
        "base_url": "https://gen.pollinations.ai/v1",
        "model": "openai/gpt-5.5",
        # Optional: anonymous tier works for some models today; when a
        # POLLINATIONS_API_KEY lands in keys.env it is used instead.
        "key_name": "POLLINATIONS_API_KEY",
        "key_required": False,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "magistral-medium-latest",
        "key_name": "MISTRAL_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-opus-5.5",
        "key_name": "OPENROUTER_API_KEY",
    },
    "nebius": {
        "base_url": "https://api.tokenfactory.nebius.com/v1",
        "model": "nvidia/Nemotron-3-Ultra-550b-a55b",
        "key_name": "NEBIUS_API_KEY",
    },
    "baseten-text": {
        "base_url": BASETEN_BASE_URL,
        "model": BASETEN_MODEL,
        "key_name": "BASETEN_API_KEY",
    },
}


def get_client(mode: str) -> ModelClient:
    """Resolve a mode name to a client.

    'auto' picks Baseten when a key exists and stub otherwise, so the
    pipeline runs today and upgrades itself the moment the key lands.
    'openai' builds the generic client from BY_EYE_BASE_URL,
    BY_EYE_MODEL and BY_EYE_KEY_NAME environment variables. A preset
    name from OPENAI_PRESETS builds the generic client for that
    provider, with BY_EYE_MODEL overriding the preset model id.
    """
    if mode == "stub":
        return StubClient()
    if mode == "baseten":
        return BasetenClient()
    if mode == "meta":
        return MetaModelClient()
    if mode == "auto":
        if load_key("BASETEN_API_KEY"):
            return BasetenClient()
        return StubClient()
    if mode == "openai":
        base_url = os.environ.get("BY_EYE_BASE_URL")
        model = os.environ.get("BY_EYE_MODEL")
        if not base_url or not model:
            raise ValueError(
                "mode 'openai' needs BY_EYE_BASE_URL and BY_EYE_MODEL "
                "(BY_EYE_KEY_NAME optional for keyless providers)."
            )
        return OpenAICompatClient(
            base_url=base_url,
            model=model,
            key_name=os.environ.get("BY_EYE_KEY_NAME") or None,
            name="openai-env",
        )
    if mode in OPENAI_PRESETS:
        preset = OPENAI_PRESETS[mode]
        return OpenAICompatClient(
            base_url=preset["base_url"],
            model=os.environ.get("BY_EYE_MODEL") or preset["model"],
            key_name=preset["key_name"],
            name=mode,
            key_required=preset.get("key_required", True),
        )
    raise ValueError(f"unknown mode: {mode}")
