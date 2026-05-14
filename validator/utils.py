"""Shared helpers: text normalization, consensus, regex validation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .models import ExtractedSection

# Section type -> regex the final text must match.
SECTION_VALIDATORS = {
    ExtractedSection.SECTION_REGISTRATION_NO: re.compile(r"^\d+$"),
    ExtractedSection.SECTION_ROLL_NO: re.compile(r"^\d+$"),
    ExtractedSection.SECTION_COURSE_CODE: re.compile(r"^[A-Za-z0-9]+$"),
}


def normalize_text(text: str) -> str:
    """Strip whitespace and uppercase. Used for consensus comparison only."""
    if text is None:
        return ""
    return re.sub(r"\s+", "", text).upper()


def validate_section_text(section_type: str, text: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Unknown section types pass through."""
    pattern = SECTION_VALIDATORS.get(section_type)
    if pattern is None:
        return True, ""
    if not text:
        return False, "Value cannot be empty."
    if not pattern.match(text):
        if section_type in (
            ExtractedSection.SECTION_REGISTRATION_NO,
            ExtractedSection.SECTION_ROLL_NO,
        ):
            return False, f"{section_type} must be numeric."
        return False, f"{section_type} must be alphanumeric."
    return True, ""


def find_consensus(predictions: Iterable) -> tuple[str | None, list[str]]:
    """If 2+ predictions agree (after normalization), return (consensus_text, agreeing_models).

    consensus_text is the raw text from the first agreeing prediction, so the
    user sees the prediction exactly as one model produced it.
    """
    preds = list(predictions)
    if len(preds) < 2:
        return None, []

    norm_counts = Counter(normalize_text(p.predicted_text) for p in preds if p.predicted_text)
    if not norm_counts:
        return None, []

    winner, count = norm_counts.most_common(1)[0]
    if count < 2 or not winner:
        return None, []

    agreeing = [p for p in preds if normalize_text(p.predicted_text) == winner]
    return agreeing[0].predicted_text, [p.model_name for p in agreeing]
