"""Orchestrate the OCR services.

To add a new model, append its class to ``_DEFAULT_SERVICE_CLASSES`` (or
register dynamically via ``OcrManager.register``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.db import transaction

from ..models import ExtractedSection, FinalLabel, OcrPrediction
from ..utils import find_consensus, validate_section_text
from .base import BaseOcrService
from .dots_ocr import DotsOcrService
from .glm_ocr import GlmOcrService
from .trocr_ocr import TrOcrService

logger = logging.getLogger(__name__)

_DEFAULT_SERVICE_CLASSES: list[type[BaseOcrService]] = [
    GlmOcrService,
    DotsOcrService,
    TrOcrService,
]


class OcrManager:
    def __init__(self, services: Iterable[BaseOcrService] | None = None) -> None:
        if services is None:
            services = [cls() for cls in _DEFAULT_SERVICE_CLASSES]
        self.services: list[BaseOcrService] = list(services)

    # --- registration helpers -------------------------------------------------
    @classmethod
    def register(cls, service_class: type[BaseOcrService]) -> None:
        if service_class not in _DEFAULT_SERVICE_CLASSES:
            _DEFAULT_SERVICE_CLASSES.append(service_class)

    @classmethod
    def registered_names(cls) -> list[str]:
        return [c.name for c in _DEFAULT_SERVICE_CLASSES]

    # --- main entry point -----------------------------------------------------
    def run_for_section(self, section: ExtractedSection, *, overwrite: bool = False) -> list[OcrPrediction]:
        """Run all OCR models on a single section and persist predictions.

        With ``overwrite=False``, models that already have a prediction for the
        section are skipped — handy for re-running after adding a new model.
        """
        absolute_path = _resolve_image_path(section.image_path)
        if not absolute_path.exists():
            logger.warning("Section %s image missing at %s", section.id, absolute_path)
            return []

        existing = {p.model_name: p for p in section.predictions.all()}
        results: list[OcrPrediction] = []

        for service in self.services:
            if not overwrite and service.name in existing:
                results.append(existing[service.name])
                continue
            out = service.run(str(absolute_path))
            obj, _ = OcrPrediction.objects.update_or_create(
                section=section,
                model_name=service.name,
                defaults={
                    "predicted_text": out.get("text", "") or "",
                    "confidence": float(out.get("confidence", 0.0) or 0.0),
                },
            )
            results.append(obj)

        self._maybe_auto_validate(section, results)
        return results

    # --- consensus ------------------------------------------------------------
    def _maybe_auto_validate(
        self, section: ExtractedSection, predictions: list[OcrPrediction]
    ) -> None:
        if hasattr(section, "final_label"):
            return  # already reviewed; don't overwrite human input

        consensus_text, agreeing = find_consensus(predictions)
        if not consensus_text:
            return

        ok, _ = validate_section_text(section.section_type, consensus_text)
        if not ok:
            return

        with transaction.atomic():
            FinalLabel.objects.update_or_create(
                section=section,
                defaults={
                    "final_text": consensus_text,
                    "selected_model": FinalLabel.MODEL_AUTO_CONSENSUS,
                    "reviewer_notes": f"Auto-validated by consensus of: {', '.join(agreeing)}",
                },
            )
            section.omr_image.recompute_status()


def _resolve_image_path(rel_or_abs: str) -> Path:
    path = Path(rel_or_abs)
    if path.is_absolute():
        return path
    return Path(settings.MEDIA_ROOT) / rel_or_abs
