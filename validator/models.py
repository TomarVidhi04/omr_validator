from django.db import models


class OmrImage(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
    ]

    image_name = models.CharField(max_length=255, unique=True)
    original_image_path = models.CharField(max_length=512)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["image_name"]

    def __str__(self):
        return self.image_name

    def recompute_status(self):
        sections = list(self.sections.all())
        if sections and all(s.is_reviewed for s in sections):
            self.status = self.STATUS_COMPLETED
        else:
            self.status = self.STATUS_PENDING
        self.save(update_fields=["status"])


class ExtractedSection(models.Model):
    # Section types we know how to validate. Anything else falls through as
    # free-form text.
    SECTION_REGISTRATION_NO = "registration_no"
    SECTION_ROLL_NO = "roll_no"
    SECTION_COURSE_CODE = "course_code"

    omr_image = models.ForeignKey(
        OmrImage, on_delete=models.CASCADE, related_name="sections"
    )
    section_type = models.CharField(max_length=64)
    image_path = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["omr_image_id", "section_type"]
        unique_together = [("omr_image", "section_type")]

    def __str__(self):
        return f"{self.omr_image.image_name}:{self.section_type}"

    @property
    def is_reviewed(self) -> bool:
        return hasattr(self, "final_label")

    @property
    def queue_status(self) -> str:
        """One of pending / completed / auto_validated."""
        label = getattr(self, "final_label", None)
        if label is None:
            return "pending"
        if label.selected_model == FinalLabel.MODEL_AUTO_CONSENSUS:
            return "auto_validated"
        return "completed"


class OcrPrediction(models.Model):
    section = models.ForeignKey(
        ExtractedSection, on_delete=models.CASCADE, related_name="predictions"
    )
    model_name = models.CharField(max_length=64)
    predicted_text = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section_id", "model_name"]
        unique_together = [("section", "model_name")]

    def __str__(self):
        return f"{self.model_name}={self.predicted_text!r}"


class FinalLabel(models.Model):
    MODEL_MANUAL = "manual"
    MODEL_AUTO_CONSENSUS = "auto_consensus"

    section = models.OneToOneField(
        ExtractedSection, on_delete=models.CASCADE, related_name="final_label"
    )
    final_text = models.CharField(max_length=255)
    selected_model = models.CharField(max_length=64)
    reviewer_notes = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.section}={self.final_text!r}"
