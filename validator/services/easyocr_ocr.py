"""EasyOCR — pragmatic, reliable OCR for printed and handwritten text.

Downloads a ~100MB detector + recognizer the first time it runs. After
that everything is cached at ``~/.EasyOCR/model``.
"""

from __future__ import annotations

import hashlib

from django.conf import settings

from .base import BaseOcrService, OcrResult


class EasyOcrService(BaseOcrService):
    name = "easyocr"

    def __init__(self) -> None:
        super().__init__()
        self._reader = None

    def _load(self) -> None:
        if settings.MOCK_OCR:
            return

        import easyocr  # type: ignore

        # ``gpu=False`` keeps things sane on CPU-only laptops.
        # English only — speeds up loading and avoids spurious matches.
        self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def _predict(self, image_path: str) -> OcrResult:
        if settings.MOCK_OCR:
            return _mock_result(image_path, self.name)

        # detail=1 → [(bbox, text, confidence), ...]
        # paragraph=False keeps each detection separate; we join them ourselves.
        results = self._reader.readtext(image_path, detail=1, paragraph=False)

        if not results:
            return {"text": "", "confidence": 0.0, "model": self.name}

        # Concatenate detections in left-to-right reading order.
        # bbox is [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] — sort by x1.
        results.sort(key=lambda r: r[0][0][0])
        text = "".join(r[1] for r in results).strip()
        confidences = [float(r[2]) for r in results if r[1]]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Strip whitespace inside the value (OCR loves to split "2 5 89")
        text = "".join(text.split())

        return {"text": text, "confidence": confidence, "model": self.name}


def _mock_result(image_path: str, model: str) -> OcrResult:
    digest = hashlib.md5((model + image_path).encode("utf-8")).hexdigest()
    return {"text": digest[:8].upper(), "confidence": 0.5, "model": model}
