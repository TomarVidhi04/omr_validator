"""Walk the pipeline output folders and populate the database.

Reads from settings.OMR_IMAGES_DIR (default: output/cropped/part-d/) and
settings.EXTRACTED_SECTIONS_DIR (default: output/sections/part-d/), and
stores paths relative to settings.MEDIA_ROOT so the labeling UI can serve
them via MEDIA_URL.

Each sub-folder under EXTRACTED_SECTIONS_DIR is matched to an OMR image by
its base name (without extension).
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...models import ExtractedSection, OmrImage

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class Command(BaseCommand):
    help = "Scan output/cropped/part-d and output/sections/part-d, populating the DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--omr-dir",
            type=Path,
            default=None,
            help="Override settings.OMR_IMAGES_DIR.",
        )
        parser.add_argument(
            "--sections-dir",
            type=Path,
            default=None,
            help="Override settings.EXTRACTED_SECTIONS_DIR.",
        )
        parser.add_argument(
            "--types",
            nargs="+",
            default=None,
            help="Section types to ingest (default: settings.LABEL_SECTION_TYPES).",
        )

    def handle(self, *args, **opts):
        omr_dir: Path = opts["omr_dir"] or settings.OMR_IMAGES_DIR
        sections_dir: Path = opts["sections_dir"] or settings.EXTRACTED_SECTIONS_DIR
        media_root: Path = Path(settings.MEDIA_ROOT)
        wanted_types = set(opts["types"] or settings.LABEL_SECTION_TYPES)

        if not omr_dir.exists():
            self.stderr.write(self.style.ERROR(f"Missing folder: {omr_dir}"))
            return
        if not sections_dir.exists():
            self.stderr.write(self.style.ERROR(f"Missing folder: {sections_dir}"))
            return

        n_images = 0
        n_sections = 0

        for image_file in sorted(omr_dir.iterdir()):
            if image_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            rel_path = image_file.resolve().relative_to(media_root.resolve()).as_posix()
            omr, created = OmrImage.objects.get_or_create(
                image_name=image_file.stem,
                defaults={"original_image_path": rel_path},
            )
            if not created and omr.original_image_path != rel_path:
                omr.original_image_path = rel_path
                omr.save(update_fields=["original_image_path"])
            n_images += 1

            section_folder = sections_dir / image_file.stem
            if not section_folder.exists():
                continue

            for crop in sorted(section_folder.iterdir()):
                if crop.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if crop.stem not in wanted_types:
                    continue
                rel_crop = crop.resolve().relative_to(media_root.resolve()).as_posix()
                _, sec_created = ExtractedSection.objects.update_or_create(
                    omr_image=omr,
                    section_type=crop.stem,
                    defaults={"image_path": rel_crop},
                )
                if sec_created:
                    n_sections += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {n_images} OMR images, {n_sections} new sections."
            )
        )
