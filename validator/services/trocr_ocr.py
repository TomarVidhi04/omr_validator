"""TrOCR via HuggingFace Transformers (microsoft/trocr-*)."""

from __future__ import annotations

import hashlib

from django.conf import settings

from .base import BaseOcrService, OcrResult


class TrOcrService(BaseOcrService):
    name = "trocr"

    def __init__(self) -> None:
        super().__init__()
        self._processor = None
        self._model = None
        self._device = "cpu"

    def _load(self) -> None:
        if settings.MOCK_OCR:
            return

        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        model_id = settings.TROCR_MODEL
        self._processor = TrOCRProcessor.from_pretrained(model_id)
        self._model = VisionEncoderDecoderModel.from_pretrained(model_id)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._device)
        self._model.eval()

    def _predict(self, image_path: str) -> OcrResult:
        if settings.MOCK_OCR:
            return _mock_result(image_path, self.name)

        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        pixel_values = self._processor(images=image, return_tensors="pt").pixel_values.to(
            self._device
        )
        with torch.no_grad():
            output = self._model.generate(
                pixel_values,
                max_length=64,
                output_scores=True,
                return_dict_in_generate=True,
            )
        text = self._processor.batch_decode(output.sequences, skip_special_tokens=True)[0]
        confidence = _avg_token_confidence(output)
        return {"text": text.strip(), "confidence": confidence, "model": self.name}


def _avg_token_confidence(output) -> float:
    """Mean softmax probability of the top token at each step."""
    import torch

    if not getattr(output, "scores", None):
        return 0.0
    probs = []
    for step_logits in output.scores:
        step_probs = torch.softmax(step_logits, dim=-1)
        probs.append(step_probs.max(dim=-1).values.item())
    return float(sum(probs) / len(probs)) if probs else 0.0


def _mock_result(image_path: str, model: str) -> OcrResult:
    """Deterministic stub output keyed off file path — for UI dev only."""
    digest = hashlib.md5(image_path.encode("utf-8")).hexdigest()
    return {
        "text": digest[:8].upper(),
        "confidence": 0.5,
        "model": model,
    }
