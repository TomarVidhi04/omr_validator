"""GLM Vision OCR via the zhipuai API (or any OpenAI-compatible endpoint).

Reads the API key from the ZHIPUAI_API_KEY environment variable.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from django.conf import settings

from .base import BaseOcrService, OcrResult

PROMPT = (
    "You are an OCR engine. Extract only the text or number visible in this "
    "image and return JUST that value with no extra words. If nothing is "
    "readable, return an empty string."
)


class GlmOcrService(BaseOcrService):
    name = "glm"

    def __init__(self) -> None:
        super().__init__()
        self._client = None

    def _load(self) -> None:
        if settings.MOCK_OCR:
            return
        if not settings.GLM_API_KEY:
            raise RuntimeError("ZHIPUAI_API_KEY is not set")

        # The zhipuai SDK is optional. Importing here keeps the dependency
        # truly optional for users who only run TrOCR/Dots.
        from zhipuai import ZhipuAI

        self._client = ZhipuAI(api_key=settings.GLM_API_KEY)

    def _predict(self, image_path: str) -> OcrResult:
        if settings.MOCK_OCR:
            return _mock_result(image_path, self.name)

        b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        response = self._client.chat.completions.create(
            model=settings.GLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        )
        text = response.choices[0].message.content or ""
        # GLM sometimes wraps the answer in quotes or extra whitespace.
        text = text.strip().strip('"').strip("'")
        return {"text": text, "confidence": 0.9, "model": self.name}


def _mock_result(image_path: str, model: str) -> OcrResult:
    digest = hashlib.md5((model + image_path).encode("utf-8")).hexdigest()
    return {"text": digest[:8].upper(), "confidence": 0.5, "model": model}
