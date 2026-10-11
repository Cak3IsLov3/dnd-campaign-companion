from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="list"),
    path("campaigns/new/", views.campaign_create, name="create"),
    path("campaigns/join/", views.campaign_join, name="join"),
    path("campaigns/<int:campaign_id>/", views.campaign_detail, name="detail"),
    path("campaigns/<int:campaign_id>/characters/new/", views.character_create, name="character_create"),
    path("campaigns/<int:campaign_id>/characters/<int:pk>/edit/", views.character_edit, name="character_edit"),
    path("campaigns/<int:campaign_id>/characters/<int:pk>/delete/", views.character_delete, name="character_delete"),
    path("campaigns/<int:campaign_id>/sessions/new/", views.session_create, name="session_create"),
    path("campaigns/<int:campaign_id>/sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("campaigns/<int:campaign_id>/sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("campaigns/<int:campaign_id>/sessions/<int:pk>/visibility/", views.session_toggle_visibility, name="session_visibility"),
]  # fmt: skip
