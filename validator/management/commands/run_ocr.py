"""Batch-run OCR over sections that don't have predictions yet."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ...models import ExtractedSection
from ...services.ocr_manager import OcrManager


class Command(BaseCommand):
    help = "Run all OCR models over sections and store predictions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-run even sections that already have predictions.",
        )
        parser.add_argument(
            "--section-id",
            type=int,
            default=None,
            help="Run only one section (by ID).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cap the number of sections processed.",
        )

    def handle(self, *args, **opts):
        manager = OcrManager()

        qs = ExtractedSection.objects.all().order_by("id")
        if opts["section_id"] is not None:
            qs = qs.filter(id=opts["section_id"])
        elif not opts["all"]:
            qs = qs.filter(predictions__isnull=True).distinct()

        if opts["limit"]:
            qs = qs[: opts["limit"]]

        total = qs.count()
        self.stdout.write(f"Running OCR over {total} section(s).")

        for i, section in enumerate(qs.iterator(), start=1):
            preds = manager.run_for_section(section, overwrite=opts["all"])
            preview = ", ".join(f"{p.model_name}={p.predicted_text!r}" for p in preds)
            self.stdout.write(f"[{i}/{total}] section={section.id} {preview}")

        self.stdout.write(self.style.SUCCESS("Done."))
