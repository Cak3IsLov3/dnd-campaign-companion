from django.urls import path

from . import views

app_name = "encounters"

urlpatterns = [
    path("new/", views.encounter_create, name="create"),
    path("<int:pk>/", views.encounter_detail, name="detail"),
    path("<int:pk>/delete/", views.encounter_delete, name="delete"),
    path("<int:pk>/monsters/search/", views.monster_search, name="monster_search"),
    path("<int:pk>/monsters/add/", views.monster_add, name="monster_add"),
    path("<int:pk>/monsters/<int:monster_id>/", views.monster_update, name="monster_update"),
    path("<int:pk>/tracker/", views.tracker_page, name="tracker"),
    path("<int:pk>/tracker/panel/", views.tracker_panel, name="tracker_panel"),
    path("<int:pk>/tracker/<str:action>/", views.tracker_action, name="tracker_action"),
]
