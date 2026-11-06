"""LLM providers.

The default provider is MockProvider: it is not a model. It copies the closest
retrieved TM match into the output template and says so in its notes. A real
OpenAI-compatible endpoint can be enabled by name: "ollama" points at a local
Ollama server (http://localhost:11434/v1, model qwen2.5-coder:14b, no API key
needed) and "openai"/"openai-compatible" read TM_RAG_LLM_BASE_URL,
TM_RAG_LLM_MODEL and optionally TM_RAG_LLM_API_KEY. Real providers are asked
for a JSON reply (prompt version 2.0); thinking text and fenced JSON are
stripped before parsing, one retry is made on a bad JSON reply, and a reply
that is still bad JSON after the retry is reported as a failure, not hidden.
"""

import json
import os
import re
from typing import NamedTuple, Protocol

import httpx

from .index import Match
from .tbx import TermEntry

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "qwen2.5-coder:14b"

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
FENCE_RE = re.compile(r"```[^\S\n]*(\w*)[^\S\n]*\n?(.*?)```", re.DOTALL | re.IGNORECASE)

RETRY_SUFFIX = (
    '\nReturn only the JSON object {"translation": "...", "used_terms": [], "notes": []} '
    "with no other text, no markdown fences and no thinking."
)


class GenContext(NamedTuple):
    source: str
    matches: list[Match]
    terms: list[TermEntry]
    max_chars: int | None = None


class Provider(Protocol):
    name: str

    def generate(self, prompt: str, context: GenContext) -> str: ...


class MockProvider:
    """Deterministic offline stand-in: fills the closest match into a template.

    The template is just the retrieved target text, so the mock output is the
    TM target of the top match. It performs no translation of its own.
    """

    name = "mock"
    template = "{target}"

    def generate(self, prompt: str, context: GenContext) -> str:
        if not context.matches:
            return ""
        return self.template.format(target=context.matches[0].unit.target)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks some models prepend to their reply."""
    return THINK_RE.sub("", text).strip()


def _try_loads(candidate: str):
    try:
        return json.loads(candidate)
    except (ValueError, TypeError):
        return None


def _find_json_object(text: str) -> dict | None:
    """Find the first balanced {...} substring that parses as a JSON object."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parsed = _try_loads(text[start : i + 1])
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None


def extract_json(text: str) -> dict | None:
    """Extract a JSON object from a raw model reply.

    Handles plain JSON, thinking text around it, ```json fenced blocks and
    JSON embedded in surrounding prose. Returns None when nothing parses.
    """
    cleaned = strip_thinking(text)
    parsed = _try_loads(cleaned)
    if isinstance(parsed, dict):
        return parsed
    for _lang, block in FENCE_RE.findall(cleaned):
        candidate = block.strip()
        parsed = _try_loads(candidate)
        if isinstance(parsed, dict):
            return parsed
        embedded = _find_json_object(candidate)
        if embedded is not None:
            return embedded
    return _find_json_object(cleaned)


def extract_translation(raw: str) -> tuple[str, dict | None]:
    """Return (translation, parsed_json) from a raw reply.

    The translation is the "translation" field of the extracted JSON object.
    Returns ("", None) when no JSON object with a translation field is found.
    """
    parsed = extract_json(raw)
    if parsed is None:
        return "", None
    translation = parsed.get("translation")
    if isinstance(translation, str):
        return translation, parsed
    return "", None


class OpenAICompatibleProvider:
    """Provider for any OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        name: str = "openai-compatible",
        json_mode: bool = False,
        system: str = "You translate game strings.",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = name
        self.json_mode = json_mode
        self.system = system

    @classmethod
    def from_env(
        cls,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> "OpenAICompatibleProvider | None":
        base_url = base_url or os.environ.get("TM_RAG_LLM_BASE_URL")
        model = model or os.environ.get("TM_RAG_LLM_MODEL")
        api_key = api_key if api_key is not None else os.environ.get("TM_RAG_LLM_API_KEY", "")
        if not (base_url and model):
            return None
        return cls(base_url=base_url, api_key=api_key, model=model)

    def _chat(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        if self.json_mode:
            payload["format"] = "json"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"].get("content") or ""
        return content.strip()

    def generate(self, prompt: str, context: GenContext) -> str:
        return self._chat(prompt)

    def generate_translation(self, prompt: str, context: GenContext) -> tuple[str, dict]:
        """Generate a translation from a JSON-answering prompt.

        A bad JSON reply is retried exactly once; if the retry is also bad,
        the failure is reported in the meta dict (bad_json=True) and the
        translation is empty so QA counts it as a failure.
        """
        raw = self._chat(prompt)
        translation, parsed = extract_translation(raw)
        attempts = 1
        if parsed is None:
            raw = self._chat(prompt + RETRY_SUFFIX)
            translation, parsed = extract_translation(raw)
            attempts = 2
        if parsed is None:
            return "", {"bad_json": True, "attempts": attempts, "raw": raw}
        return translation, {"bad_json": False, "attempts": attempts, "raw": raw}


def get_provider(
    name: str = "mock",
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        return OpenAICompatibleProvider(
            base_url=base_url or os.environ.get("TM_RAG_LLM_BASE_URL") or OLLAMA_BASE_URL,
            api_key=api_key if api_key is not None else os.environ.get("TM_RAG_LLM_API_KEY", ""),
            model=model or os.environ.get("TM_RAG_LLM_MODEL") or OLLAMA_MODEL,
            timeout=timeout,
            name="ollama",
            json_mode=True,
            system='You translate game strings. Reply with only a JSON object {"translation": "..."}.',
        )
    if name in ("openai", "openai-compatible"):
        provider = OpenAICompatibleProvider.from_env(base_url=base_url, model=model, api_key=api_key)
        if provider is None:
            raise RuntimeError(
                "OpenAI-compatible provider requested but TM_RAG_LLM_BASE_URL and "
                "TM_RAG_LLM_MODEL are not both set."
            )
        return provider
    raise ValueError(f"unknown provider: {name}")
