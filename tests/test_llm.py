from tm_rag.llm import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OpenAICompatibleProvider,
    extract_json,
    extract_translation,
    get_provider,
    strip_thinking,
)


def test_strip_thinking_removes_think_blocks():
    raw = "<think>the source says New Game</think>\n{\"translation\": \"新游戏\"}"
    assert strip_thinking(raw) == '{"translation": "新游戏"}'


def test_extract_json_plain():
    assert extract_json('{"translation": "新游戏"}') == {"translation": "新游戏"}


def test_extract_json_from_fenced_block():
    raw = '```json\n{\n  "translation": "保存游戏",\n  "used_terms": []\n}\n```'
    assert extract_json(raw)["translation"] == "保存游戏"


def test_extract_json_from_thinking_plus_fence():
    raw = '<think>planning</think>\n```json\n{"translation": "设置"}\n```'
    assert extract_json(raw)["translation"] == "设置"


def test_extract_json_embedded_in_prose():
    raw = 'Here is the reply: {"translation": "退出游戏", "notes": ["ok"]} hope that helps.'
    assert extract_json(raw)["translation"] == "退出游戏"


def test_extract_json_returns_none_for_non_json():
    assert extract_json("just a plain translation") is None
    assert extract_json('{"translation": ') is None
    assert extract_json("") is None


def test_extract_translation_reads_translation_field():
    translation, parsed = extract_translation('```json\n{"translation": "新游戏"}\n```')
    assert translation == "新游戏"
    assert parsed == {"translation": "新游戏"}


def test_extract_translation_rejects_json_without_translation():
    translation, parsed = extract_translation('{"result": "新游戏"}')
    assert translation == ""
    assert parsed is None


class _FakeChatProvider(OpenAICompatibleProvider):
    def __init__(self, replies):
        super().__init__(base_url="http://example.invalid/v1", api_key="", model="fake")
        self.replies = list(replies)
        self.calls = 0

    def _chat(self, prompt: str) -> str:
        self.calls += 1
        return self.replies.pop(0)


def test_generate_translation_retries_bad_json_once():
    provider = _FakeChatProvider(["not json at all", '```json\n{"translation": "新游戏"}\n```'])
    translation, meta = provider.generate_translation("prompt", None)
    assert translation == "新游戏"
    assert meta["bad_json"] is False
    assert meta["attempts"] == 2
    assert provider.calls == 2


def test_generate_translation_counts_persistent_bad_json_as_failure():
    provider = _FakeChatProvider(["nope", "still nope"])
    translation, meta = provider.generate_translation("prompt", None)
    assert translation == ""
    assert meta["bad_json"] is True
    assert meta["attempts"] == 2
    assert provider.calls == 2


def test_generate_translation_no_retry_when_first_reply_is_good():
    provider = _FakeChatProvider(['{"translation": "设置"}'])
    translation, meta = provider.generate_translation("prompt", None)
    assert translation == "设置"
    assert meta["attempts"] == 1
    assert provider.calls == 1


def test_get_provider_ollama_defaults():
    provider = get_provider("ollama")
    assert provider.name == "ollama"
    assert provider.base_url == OLLAMA_BASE_URL
    assert provider.model == OLLAMA_MODEL
    assert provider.api_key == ""
    assert provider.json_mode is True


def test_get_provider_ollama_overrides():
    provider = get_provider("ollama", base_url="http://other:1234/v1", model="m", api_key="k")
    assert provider.base_url == "http://other:1234/v1"
    assert provider.model == "m"
    assert provider.api_key == "k"


def test_get_provider_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        get_provider("nope")
