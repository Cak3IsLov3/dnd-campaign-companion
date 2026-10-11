from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("campaigns", views.CampaignViewSet, basename="campaign")
router.register("characters", views.CharacterViewSet, basename="character")
router.register("npcs", views.NpcViewSet, basename="npc")
router.register("encounters", views.EncounterViewSet, basename="encounter")
router.register("loot-rolls", views.LootRollViewSet, basename="lootroll")
router.register("hooks", views.HookViewSet, basename="hook")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api-token"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("", include(router.urls)),
]
