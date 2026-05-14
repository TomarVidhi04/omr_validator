"""Base class for OCR services.

Every model returns a dict like::

    {"text": "22017452", "confidence": 0.95, "model": "glm"}

Models lazy-load their weights/clients the first time ``run`` is called and
cache the result on the instance. If loading fails (missing dependency,
missing API key, network error), the service degrades to returning empty
predictions with confidence 0 — the app stays usable and the section just
needs full manual review.
"""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class OcrResult(TypedDict):
    text: str
    confidence: float
    model: str


class BaseOcrService:
    name: str = "base"

    def __init__(self) -> None:
        self._loaded = False
        self._available = True
        self._load_error: str | None = None

    def is_available(self) -> bool:
        """Try to load the model once and remember the outcome."""
        if not self._loaded:
            try:
                self._load()
            except Exception as exc:  # noqa: BLE001 - any failure -> unavailable
                self._available = False
                self._load_error = f"{type(exc).__name__}: {exc}"
                logger.warning("OCR model %s unavailable: %s", self.name, self._load_error)
            self._loaded = True
        return self._available

    def run(self, image_path: str) -> OcrResult:
        if not self.is_available():
            return self._empty(reason=self._load_error or "unavailable")
        try:
            return self._predict(image_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OCR model %s failed on %s", self.name, image_path)
            return self._empty(reason=f"{type(exc).__name__}: {exc}")

    def _empty(self, reason: str = "") -> OcrResult:
        return {"text": "", "confidence": 0.0, "model": self.name}

    # Subclasses override these.
    def _load(self) -> None:  # pragma: no cover - implementation specific
        raise NotImplementedError

    def _predict(self, image_path: str) -> OcrResult:  # pragma: no cover
        raise NotImplementedError
