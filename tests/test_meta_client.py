import pytest

from by_eye.clients import (
    MetaModelClient,
    _extract_json_array,
    get_client,
    parse_sam_output,
)

# SAM 3.1 wire format, one frame line with two objects: the first
# carries a mask payload (an undecodable stub payload here, so the
# area must come back None rather than a guess), the second is a
# box-only record.
SAM_LINE = (
    "<0f>0<|box;x1=332;y1=130;x2=521;y2=319;w=854;h=480|>"
    "<|mask;x=0;y=0;data=190,190,~notarealpayload|>,"
    "1<|box;x1=10;y1=20;x2=110;y2=220;w=854;h=480|>"
)


def test_parse_sam_output_boxes():
    objects = parse_sam_output(SAM_LINE)
    assert len(objects) == 2
    first, second = objects
    assert first.box == (332, 130, 521, 319)
    assert first.frame_width == 854 and first.frame_height == 480
    assert first.box_area_px == 190 * 190
    assert second.object_id == "1"
    assert second.box == (10, 20, 110, 220)
    # The stub payload must not decode into a made-up area.
    assert first.mask_area_px is None
    assert first.coverage_fraction is None


def test_parse_sam_output_empty_is_no_match():
    assert parse_sam_output("") == []
    assert parse_sam_output("no objects here") == []


def test_prompt_for_frame():
    assert MetaModelClient.prompt_for_frame("frame_10_tomato.jpg") == "tomato"
    assert MetaModelClient.prompt_for_frame("/x/frame_03_soy_marinade.jpg") == "soy marinade"
    assert MetaModelClient.prompt_for_frame("frame_000120") == "frame 000120"


def test_extract_json_array_handles_fences():
    text = "```json\n[{\"a\": 1}]\n```"
    assert _extract_json_array(text) == [{"a": 1}]
    assert _extract_json_array("noise [1, 2] tail") == [1, 2]


def test_meta_client_requires_key(tmp_path, monkeypatch):
    monkeypatch.setattr("by_eye.clients.KEYS_ENV_PATH", tmp_path / "absent.env")
    monkeypatch.delenv("META_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        MetaModelClient()
    with pytest.raises(RuntimeError):
        get_client("meta")


def test_meta_client_constructs_with_key(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "test-key-not-real")
    client = get_client("meta")
    assert client.name == "meta"


def test_transcribe_rejects_non_wav(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "test-key-not-real")
    client = MetaModelClient()
    with pytest.raises(ValueError):
        client.transcribe("narration.mp3")
