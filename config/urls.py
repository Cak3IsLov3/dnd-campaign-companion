from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/", include("api.urls")),
    path("", include("campaigns.urls")),
    path("campaigns/<int:campaign_id>/encounters/", include("encounters.urls")),
    path("campaigns/<int:campaign_id>/loot/", include("loot.urls")),
    path("campaigns/<int:campaign_id>/npcs/", include("npcs.urls")),
    path("campaigns/<int:campaign_id>/vault/", include("vault.urls")),
]
