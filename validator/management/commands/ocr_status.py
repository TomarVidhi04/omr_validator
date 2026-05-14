"""Diagnose the OCR pipeline.

Shows which models load successfully, which are skipped (and why), and
optionally runs each model on one sample image so you can eyeball the
output.

    python manage.py ocr_status
    python manage.py ocr_status --section-id 1
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from ...models import ExtractedSection
from ...services.ocr_manager import OcrManager, _resolve_image_path


class Command(BaseCommand):
    help = "Show which OCR models are loaded / unavailable and (optionally) test-run them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--section-id",
            type=int,
            default=None,
            help="Run each model on this section's crop and print the result.",
        )

    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE("OCR configuration:"))
        self.stdout.write(f"  OMR_MOCK_OCR        = {settings.MOCK_OCR}")
        self.stdout.write(f"  ZHIPUAI_API_KEY set = {bool(settings.GLM_API_KEY)}")
        self.stdout.write(f"  TROCR_MODEL         = {settings.TROCR_MODEL}")
        self.stdout.write(f"  DOTS_OCR_MODEL      = {settings.DOTS_OCR_MODEL}")
        self.stdout.write("")

        manager = OcrManager()
        self.stdout.write(self.style.NOTICE("Model availability:"))
        for svc in manager.services:
            ok = svc.is_available()
            if ok and settings.MOCK_OCR:
                self.stdout.write(f"  • {svc.name:8s}  MOCK (using deterministic stubs)")
            elif ok:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {svc.name:8s}  loaded"))
            else:
                reason = svc._load_error or "unknown"
                self.stdout.write(self.style.WARNING(f"  ✗ {svc.name:8s}  unavailable ({reason})"))

        section_id = opts.get("section_id")
        if section_id is None:
            self.stdout.write("")
            self.stdout.write("Tip: pass --section-id N to test-run on a real crop.")
            return

        section = ExtractedSection.objects.filter(pk=section_id).first()
        if section is None:
            self.stderr.write(self.style.ERROR(f"No section with id={section_id}"))
            return

        path = _resolve_image_path(section.image_path)
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(f"Test run on section #{section.id} ({section.section_type})"))
        self.stdout.write(f"  image: {path}")
        for svc in manager.services:
            out = svc.run(str(path))
            self.stdout.write(
                f"  {svc.name:8s} text={out.get('text')!r:30s} conf={out.get('confidence'):.2f}"
            )
