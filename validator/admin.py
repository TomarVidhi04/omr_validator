from django.contrib import admin

from .models import ExtractedSection, FinalLabel, OcrPrediction, OmrImage


@admin.register(OmrImage)
class OmrImageAdmin(admin.ModelAdmin):
    list_display = ("id", "image_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("image_name",)


@admin.register(ExtractedSection)
class ExtractedSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "omr_image", "section_type", "queue_status")
    list_filter = ("section_type",)
    search_fields = ("omr_image__image_name",)


@admin.register(OcrPrediction)
class OcrPredictionAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "model_name", "predicted_text", "confidence")
    list_filter = ("model_name",)
    search_fields = ("predicted_text",)


@admin.register(FinalLabel)
class FinalLabelAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "final_text", "selected_model", "reviewed_at")
    search_fields = ("final_text",)
