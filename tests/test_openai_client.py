import io
import json

import pytest

from by_eye import clients
from by_eye.clients import OpenAICompatClient, get_client


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen_factory(captured):
    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["auth"] = request.headers.get("Authorization")
        return FakeResponse(
            {
                "choices": [{"message": {"content": "[{\"a\": 1}]"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )

    return fake_urlopen


def test_chat_posts_openai_shape_and_returns_usage(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        clients.urllib.request, "urlopen", fake_urlopen_factory(captured)
    )
    client = OpenAICompatClient(
        base_url="https://example.test/v1/",
        model="some/model-1",
        api_key="test-key-not-real",
    )
    content, usage = client.chat([{"role": "user", "content": "hi"}])
    assert content == '[{"a": 1}]'
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5}
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "some/model-1"
    assert captured["auth"] == "Bearer test-key-not-real"


def test_keyless_client_sends_no_auth_header(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        clients.urllib.request, "urlopen", fake_urlopen_factory(captured)
    )
    client = OpenAICompatClient(
        base_url="https://example.test/v1", model="m", key_name=None
    )
    client.chat([{"role": "user", "content": "hi"}])
    assert captured["auth"] is None


def test_missing_required_key_raises(monkeypatch, tmp_path):
    monkeypatch.setattr("by_eye.clients.KEYS_ENV_PATH", tmp_path / "absent.env")
    monkeypatch.delenv("DEFINITELY_ABSENT_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenAICompatClient(
            base_url="https://example.test/v1",
            model="m",
            key_name="DEFINITELY_ABSENT_KEY",
        )


def test_preset_modes_are_removed(monkeypatch, tmp_path):
    # The non-Meta provider presets were removed from get_client on
    # 2026-11-01. None of them may resolve to a client any more.
    monkeypatch.setattr("by_eye.clients.KEYS_ENV_PATH", tmp_path / "absent.env")
    for mode in ("pollinations", "mistral", "openrouter", "nebius", "baseten-text"):
        with pytest.raises(ValueError):
            get_client(mode)


def test_env_mode_is_removed(monkeypatch):
    # The generic BY_EYE_* environment fallback was removed with the
    # presets: setting those variables must not build a client.
    monkeypatch.setenv("BY_EYE_BASE_URL", "https://router.test/v1")
    monkeypatch.setenv("BY_EYE_MODEL", "anthropic/claude-opus-5.5")
    monkeypatch.setenv("BY_EYE_KEY_NAME", "OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    with pytest.raises(ValueError):
        get_client("openai")


def test_read_ingredients_not_implemented_for_text_client():
    client = OpenAICompatClient(
        base_url="https://example.test/v1", model="m", key_name=None
    )
    with pytest.raises(NotImplementedError):
        client.read_ingredients([])
