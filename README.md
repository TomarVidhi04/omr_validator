# OMR OCR Validator

A small Django app for validating OCR outputs extracted from OMR sheets.
Loads the original sheet, the extracted section crop, and side-by-side OCR
predictions from multiple models — a human picks the correct one with
keyboard shortcuts and the validated value is saved to SQLite.

## What's in it

- **Three OCR backends** (modular, easy to extend):
  - `glm` — GLM Vision via the [zhipuai API](https://open.bigmodel.cn/)
  - `dots` — [rednote-hilab/dots.ocr](https://huggingface.co/rednote-hilab/dots.ocr)
  - `trocr` — [microsoft/trocr-base-printed](https://huggingface.co/docs/transformers/model_doc/trocr)
- **Auto-consensus**: if ≥2 models agree (and the text passes section regex), the section is auto-validated.
- **Regex validation**: `registration_no` / `roll_no` → digits, `course_code` → alphanumeric.
- **Pages**: `/dashboard/`, `/review/<id>/`, `/stats/`, `/export/`.
- **Keyboard shortcuts** on the review page: `1` / `2` / `3` pick a prediction, `Enter` saves and moves to the next pending section.
- **SQLite** out of the box, server-rendered Django templates, vanilla JS.

## Folder layout

```
data screen/
    part-d/01/<sheet>.jpg              # raw scans you drop in
output/
    cropped/part-d/<sheet>.jpg         # crop_omr.py output
    sections/part-d/<sheet>/<section>.jpg   # extract_sections.py output
```

Both `data screen/` and `output/` are gitignored.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
```

## Run

```bash
# 0a. Drop your raw scans into:
#       data screen/part-d/01/*.jpg

# 0b. Crop each scan down to the Part-D area (600x1400).
python crop_omr.py
# -> writes output/cropped/part-d/<sheet>.jpg

# 0c. Slice each cropped sheet into 15 sections.
python extract_sections.py
# -> writes output/sections/part-d/<sheet>/<section>.jpg

# 1. Index the pipeline output into the DB
python manage.py ingest_data

# 2. Run OCR over every section (only fills in missing predictions by default)
python manage.py run_ocr

# 3. Start the server
python manage.py runserver
# → http://127.0.0.1:8000/dashboard/
```

### Quick UI iteration without ML deps

Set `OMR_MOCK_OCR=1` to skip loading the heavy ML models and return deterministic
stub predictions instead. Useful when you only want to exercise the review UI.

```bash
OMR_MOCK_OCR=1 python manage.py run_ocr
OMR_MOCK_OCR=1 python manage.py runserver
```

### GLM Vision

Set `ZHIPUAI_API_KEY` in your environment. Optional: `GLM_MODEL` (defaults to `glm-4v-flash`).

```bash
export ZHIPUAI_API_KEY=sk-...
python manage.py run_ocr
```

If the key is missing the GLM service is skipped (the other two still run).

## CLI reference

| Command | What it does |
| --- | --- |
| `python manage.py ingest_data` | Walk `data/` and populate `OmrImage` + `ExtractedSection`. |
| `python manage.py run_ocr` | Run all OCR models on sections without predictions. |
| `python manage.py run_ocr --all` | Re-run all models on every section (overwrites). |
| `python manage.py run_ocr --section-id 42` | Run on a single section. |

## Adding a new OCR model

1. Create `validator/services/myocr.py` with a class extending `BaseOcrService`:

   ```python
   from .base import BaseOcrService, OcrResult

   class MyOcrService(BaseOcrService):
       name = "myocr"
       def _load(self): ...
       def _predict(self, image_path: str) -> OcrResult:
           return {"text": "...", "confidence": 0.9, "model": self.name}
   ```

2. Add it to `_DEFAULT_SERVICE_CLASSES` in `validator/services/ocr_manager.py`.
3. Re-run `python manage.py run_ocr` (it will only fill in missing predictions
   for the new model — old predictions stay intact).

## Data model

```
OmrImage
  ├── id, image_name, original_image_path, status, created_at
  └── ExtractedSection (FK)
        ├── id, section_type, image_path, created_at
        ├── OcrPrediction (FK, one row per model)
        │     id, model_name, predicted_text, confidence, created_at
        └── FinalLabel (1:1)
              id, final_text, selected_model, reviewer_notes, reviewed_at
```

`selected_model` is the OCR model name the human picked, or `manual` if they
typed it themselves, or `auto_consensus` if it was filled in automatically.

## Export

`GET /export/` downloads every reviewed section as JSON, grouped by OMR image.
