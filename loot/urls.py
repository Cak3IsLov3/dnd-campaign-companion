from django.urls import path

from . import views

app_name = "loot"

urlpatterns = [
    path("", views.generator, name="generator"),
    path("roll/", views.roll, name="roll"),
    path("draft/<str:action>/<int:slot>/", views.draft_action, name="draft_action"),
    path("save/", views.save, name="save"),
    path("weights/", views.weights, name="weights"),
    path("sync/", views.sync, name="sync"),
    path("rolls/<int:pk>/delete/", views.roll_delete, name="roll_delete"),
    path("rolls/<int:pk>/visibility/<str:target>/", views.roll_visibility, name="roll_visibility"),
]
