from django.db import models

from campaigns.models import Campaign, GameSession
from encounters.models import Encounter

from .services import DEFAULT_WEIGHTS


def default_weights():
    return dict(DEFAULT_WEIGHTS)


class LootTable(models.Model):
    """Rarity weights for magic items. One per campaign; DMs tune it to taste."""

    name = models.CharField(max_length=120, default="Default")
    campaign = models.OneToOneField(
        Campaign, on_delete=models.CASCADE, null=True, blank=True, related_name="loot_table"
    )
    weights = models.JSONField(default=default_weights)

    def __str__(self):
        return self.name


class LootRoll(models.Model):
    """A saved loot roll.

    `result` is {"cr", "coins": {cp, sp, gp}, "coins_visible": bool,
    "items": [{index, name, rarity, locked, visible, rerolls}]}.
    """

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="loot_rolls")
    encounter = models.ForeignKey(
        Encounter, on_delete=models.SET_NULL, null=True, blank=True, related_name="loot_rolls"
    )
    session = models.ForeignKey(
        GameSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="loot_rolls"
    )
    seed = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Loot roll #{self.pk}"
