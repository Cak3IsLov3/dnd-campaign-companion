from django.urls import path

from . import views

app_name = "vault"

urlpatterns = [
    path("", views.home, name="home"),
    path("characters/<int:character_id>/", views.backstory_edit, name="backstory"),
    path("characters/<int:character_id>/hooks/", views.hook_add, name="hook_add"),
    path("characters/<int:character_id>/hooks/<int:pk>/delete/", views.hook_delete, name="hook_delete"),
    path("hooks/<int:pk>/link/", views.hook_link, name="hook_link"),
]  # fmt: skip
