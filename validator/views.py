from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import ExtractedSection, FinalLabel, OmrImage
from .services.ocr_manager import OcrManager
from .utils import validate_section_text


def _media_url(path: str) -> str:
    return settings.MEDIA_URL + path.lstrip("/")


def _next_pending_section(after_id: int | None = None) -> ExtractedSection | None:
    qs = ExtractedSection.objects.filter(final_label__isnull=True).order_by("id")
    if after_id is not None:
        qs = qs.filter(id__gt=after_id)
    return qs.first()


def dashboard(request):
    status_filter = request.GET.get("status", "all")

    sections = (
        ExtractedSection.objects.select_related("omr_image")
        .prefetch_related("predictions", "final_label")
        .order_by("omr_image_id", "section_type")
    )

    if status_filter == "pending":
        sections = sections.filter(final_label__isnull=True)
    elif status_filter == "completed":
        sections = sections.filter(
            final_label__isnull=False
        ).exclude(final_label__selected_model=FinalLabel.MODEL_AUTO_CONSENSUS)
    elif status_filter == "auto_validated":
        sections = sections.filter(
            final_label__selected_model=FinalLabel.MODEL_AUTO_CONSENSUS
        )

    sections = sections[:500]

    rows = []
    for s in sections:
        rows.append(
            {
                "id": s.id,
                "image_name": s.omr_image.image_name,
                "section_type": s.section_type,
                "status": s.queue_status,
                "n_predictions": s.predictions.count(),
                "final_text": getattr(getattr(s, "final_label", None), "final_text", ""),
            }
        )

    totals = ExtractedSection.objects.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(final_label__isnull=False)),
        pending=Count("id", filter=Q(final_label__isnull=True)),
    )

    return render(
        request,
        "validator/dashboard.html",
        {
            "rows": rows,
            "status_filter": status_filter,
            "totals": totals,
        },
    )


@require_http_methods(["GET", "POST"])
def review(request, section_id: int):
    section = get_object_or_404(
        ExtractedSection.objects.select_related("omr_image"), pk=section_id
    )
    predictions = list(section.predictions.order_by("model_name"))

    if request.method == "POST":
        final_text = (request.POST.get("final_text") or "").strip()
        selected_model = request.POST.get("selected_model") or FinalLabel.MODEL_MANUAL
        notes = request.POST.get("reviewer_notes", "").strip()

        ok, err = validate_section_text(section.section_type, final_text)
        if not ok:
            messages.error(request, err)
            return redirect("review", section_id=section.id)

        FinalLabel.objects.update_or_create(
            section=section,
            defaults={
                "final_text": final_text,
                "selected_model": selected_model,
                "reviewer_notes": notes,
            },
        )
        section.omr_image.recompute_status()
        messages.success(request, f"Saved: {final_text}")

        nxt = _next_pending_section(after_id=section.id) or _next_pending_section()
        if nxt is not None:
            return redirect("review", section_id=nxt.id)
        return redirect("dashboard")

    final_label = getattr(section, "final_label", None)

    return render(
        request,
        "validator/review.html",
        {
            "section": section,
            "predictions": predictions,
            "final_label": final_label,
            "original_url": _media_url(section.omr_image.original_image_path),
            "section_url": _media_url(section.image_path),
            "model_names": OcrManager.registered_names(),
        },
    )


def stats(request):
    section_totals = ExtractedSection.objects.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(final_label__isnull=False)),
        pending=Count("id", filter=Q(final_label__isnull=True)),
        auto_validated=Count(
            "id",
            filter=Q(final_label__selected_model=FinalLabel.MODEL_AUTO_CONSENSUS),
        ),
    )
    by_section_type = (
        ExtractedSection.objects.values("section_type")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(final_label__isnull=False)),
        )
        .order_by("section_type")
    )
    image_totals = OmrImage.objects.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status=OmrImage.STATUS_COMPLETED)),
    )
    by_model = (
        FinalLabel.objects.values("selected_model")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    return render(
        request,
        "validator/stats.html",
        {
            "section_totals": section_totals,
            "image_totals": image_totals,
            "by_section_type": list(by_section_type),
            "by_model": list(by_model),
        },
    )


def export_json(request):
    """Export every reviewed section as JSON. Streams as a download."""
    labels = (
        FinalLabel.objects.select_related("section__omr_image")
        .order_by("section__omr_image__image_name", "section__section_type")
    )

    grouped: dict[str, dict] = {}
    for label in labels:
        image_name = label.section.omr_image.image_name
        entry = grouped.setdefault(
            image_name,
            {"image_name": image_name, "sections": {}},
        )
        entry["sections"][label.section.section_type] = {
            "final_text": label.final_text,
            "selected_model": label.selected_model,
            "reviewer_notes": label.reviewer_notes,
            "reviewed_at": label.reviewed_at.isoformat(),
        }

    payload = {"count": len(grouped), "results": list(grouped.values())}
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = 'attachment; filename="validated_labels.json"'
    return response
