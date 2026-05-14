from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("review/<int:section_id>/", views.review, name="review"),
    path("stats/", views.stats, name="stats"),
    path("export/", views.export_json, name="export"),
]
