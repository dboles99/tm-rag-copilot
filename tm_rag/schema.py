"""Structured output schema for a single translation."""

from pydantic import BaseModel, Field


class TranslationResult(BaseModel):
    translation: str = Field(description="The translated target text.")
    used_terms: list[str] = Field(
        default_factory=list,
        description="Target terms from the term base that apply to this source text.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Free-form notes, for example which TM match a mock provider copied.",
    )
