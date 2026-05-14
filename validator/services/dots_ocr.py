"""dots.ocr (rednote-hilab/dots.ocr) via HuggingFace Transformers."""

from __future__ import annotations

import hashlib

from django.conf import settings

from .base import BaseOcrService, OcrResult

PROMPT = (
    "Extract only the text or number visible in this image. "
    "Respond with the value only, no explanation."
)


class DotsOcrService(BaseOcrService):
    name = "dots"

    def __init__(self) -> None:
        super().__init__()
        self._processor = None
        self._model = None
        self._device = "cpu"

    def _load(self) -> None:
        if settings.MOCK_OCR:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        model_id = settings.DOTS_OCR_MODEL
        self._processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._device)
        self._model.eval()

    def _predict(self, image_path: str) -> OcrResult:
        if settings.MOCK_OCR:
            return _mock_result(image_path, self.name)

        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ]
        # ``apply_chat_template(tokenize=False)`` returns the formatted prompt
        # string. We feed that plus the image into the processor to get the
        # actual model inputs (a BatchFeature with .to()).
        prompt_text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=[prompt_text],
            images=[image],
            padding=True,
            return_tensors="pt",
        ).to(self._device)
        # dots.ocr's processor includes ``mm_token_type_ids`` which the model's
        # generate() rejects. Drop any keys the model doesn't accept.
        inputs.pop("mm_token_type_ids", None)
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs, max_new_tokens=64, do_sample=False
            )
        # Drop the prompt tokens before decoding so we only get the answer.
        gen_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        text = self._processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        return {"text": text.strip(), "confidence": 0.8, "model": self.name}


def _mock_result(image_path: str, model: str) -> OcrResult:
    digest = hashlib.md5((model + image_path).encode("utf-8")).hexdigest()
    return {"text": digest[:8].upper(), "confidence": 0.5, "model": model}
