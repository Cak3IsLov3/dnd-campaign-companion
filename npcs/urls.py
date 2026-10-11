from django.urls import path

from . import views

app_name = "npcs"

urlpatterns = [
    path("", views.generator, name="generator"),
    path("generate/", views.generate, name="generate"),
    path("draft/<str:action>/<str:field>/", views.draft_action, name="draft_action"),
    path("save/", views.save, name="save"),
    path("tables/", views.tables, name="tables"),
    path("tables/<int:pk>/delete/", views.trait_delete, name="trait_delete"),
]
