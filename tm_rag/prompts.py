"""Versioned few-shot prompt templates built from retrieval matches and terms."""

from .index import Match
from .tbx import TermEntry

PROMPT_VERSION = "1.0"
PROMPT_VERSION_JSON = "2.0"

SYSTEM_INSTRUCTION = (
    "You are a game localisation engine. Translate the SOURCE segment into "
    "Simplified Chinese (zh-CN). Keep placeholders, tags and numbers exactly. "
    "Use the approved terms. Return only the translation."
)

SYSTEM_INSTRUCTION_JSON = (
    "You are a game localisation engine. Translate the SOURCE segment into "
    "Simplified Chinese (zh-CN). Keep placeholders, tags and numbers exactly. "
    "Use the approved terms. Reply with only a JSON object of the form "
    '{"translation": "...", "used_terms": [...], "notes": [...]} and no other text.'
)


def _format_example(match: Match) -> str:
    return f"SOURCE: {match.unit.source}\nTRANSLATION: {match.unit.target}"


def build_prompt(
    source: str,
    matches: list[Match],
    terms: list[TermEntry],
    max_chars: int | None = None,
) -> str:
    """Build the few-shot prompt for one source segment.

    The first two retrieval matches are used as few-shot examples, the term
    base is listed as approved terminology, and the query segment is last.
    """
    lines = [
        f"# prompt version {PROMPT_VERSION}",
        SYSTEM_INSTRUCTION,
        "",
        "## Examples",
    ]
    for match in matches[:2]:
        lines.append(_format_example(match))
        lines.append("")
    if terms:
        lines.append("## Approved terms")
        for term in terms:
            line = f"- {term.source} = {term.target}"
            if term.forbidden:
                line += f" (do not use: {', '.join(term.forbidden)})"
            lines.append(line)
        lines.append("")
    lines.append("## Task")
    lines.append(f"SOURCE: {source}")
    if max_chars is not None:
        lines.append(f"Keep the translation within {max_chars} characters.")
    lines.append("TRANSLATION:")
    return "\n".join(lines)


def build_prompt_json(
    source: str,
    matches: list[Match],
    terms: list[TermEntry],
    max_chars: int | None = None,
) -> str:
    """Build the JSON-answering prompt (version 2.0) for real model providers.

    Same few-shot structure as build_prompt, but the task asks for a single
    JSON object so the reply can be parsed and retried deterministically.
    """
    lines = [
        f"# prompt version {PROMPT_VERSION_JSON}",
        SYSTEM_INSTRUCTION_JSON,
        "",
        "## Examples",
    ]
    for match in matches[:2]:
        lines.append(_format_example(match))
        lines.append("")
    if terms:
        lines.append("## Approved terms")
        for term in terms:
            line = f"- {term.source} = {term.target}"
            if term.forbidden:
                line += f" (do not use: {', '.join(term.forbidden)})"
            lines.append(line)
        lines.append("")
    lines.append("## Task")
    lines.append(f"SOURCE: {source}")
    if max_chars is not None:
        lines.append(f"Keep the translation within {max_chars} characters.")
    lines.append('Reply with only {"translation": "...", "used_terms": [...], "notes": [...]}.')
    return "\n".join(lines)
