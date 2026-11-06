"""Deterministic QA checks on a source/translation pair.

Every check returns a Finding; a translation passes QA only when all findings
pass. The checks are pure string operations so results are reproducible and
need no model.
"""

import re
from dataclasses import dataclass
from typing import Iterable

from .tbx import TermEntry

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}|%\d*(?:\.\d+)?[a-zA-Z]")
TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Finding:
    check: str
    passed: bool
    detail: str


def check_placeholders(source: str, translation: str) -> Finding:
    missing = [p for p in PLACEHOLDER_RE.findall(source) if p not in translation]
    return Finding(
        check="placeholder_preservation",
        passed=not missing,
        detail="all placeholders kept" if not missing else f"missing placeholders: {missing}",
    )


def check_tags(source: str, translation: str) -> Finding:
    missing = [t for t in TAG_RE.findall(source) if t not in translation]
    return Finding(
        check="tag_preservation",
        passed=not missing,
        detail="all tags kept" if not missing else f"missing tags: {missing}",
    )


def check_character_limit(translation: str, max_chars: int | None) -> Finding:
    if max_chars is None:
        return Finding(check="character_limit", passed=True, detail="no limit set")
    passed = len(translation) <= max_chars
    return Finding(
        check="character_limit",
        passed=passed,
        detail=f"{len(translation)}/{max_chars} characters"
        if passed
        else f"over limit: {len(translation)}/{max_chars} characters",
    )


def required_terms(source: str, terms: Iterable[TermEntry]) -> list[TermEntry]:
    """Terms whose source form appears in the source text (case-insensitive)."""
    lowered = source.lower()
    return [t for t in terms if t.source and t.source.lower() in lowered]


def check_required_terms(
    source: str, translation: str, terms: Iterable[TermEntry]
) -> Finding:
    missing = [t.target for t in required_terms(source, terms) if t.target not in translation]
    return Finding(
        check="required_term_used",
        passed=not missing,
        detail="all required terms used" if not missing else f"missing term targets: {missing}",
    )


def check_forbidden_terms(translation: str, terms: Iterable[TermEntry]) -> Finding:
    present = [
        f for t in terms for f in t.forbidden if f and f in translation
    ]
    return Finding(
        check="forbidden_term_absent",
        passed=not present,
        detail="no forbidden terms present" if not present else f"forbidden terms present: {present}",
    )


def check_numbers(source: str, translation: str) -> Finding:
    missing = [n for n in NUMBER_RE.findall(source) if n not in translation]
    return Finding(
        check="number_preservation",
        passed=not missing,
        detail="all numbers kept" if not missing else f"missing numbers: {missing}",
    )


def run_qa(
    source: str,
    translation: str,
    terms: Iterable[TermEntry] = (),
    max_chars: int | None = None,
) -> list[Finding]:
    """Run all QA checks and return the findings."""
    terms = list(terms)
    return [
        check_placeholders(source, translation),
        check_tags(source, translation),
        check_character_limit(translation, max_chars),
        check_required_terms(source, translation, terms),
        check_forbidden_terms(translation, terms),
        check_numbers(source, translation),
    ]


def all_passed(findings: Iterable[Finding]) -> bool:
    return all(f.passed for f in findings)
