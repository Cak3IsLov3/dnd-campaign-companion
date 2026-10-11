import copy

from django.db.models import Q

from campaigns.access import campaigns_for, dm_campaigns_for, is_dm

from .models import LootRoll, LootTable
from .services import DEFAULT_WEIGHTS, RARITIES


def weights_for(campaign):
    """The campaign's rarity weights, falling back to the defaults."""
    table = LootTable.objects.filter(campaign=campaign).first()
    weights = dict(DEFAULT_WEIGHTS)
    if table:
        weights.update({r: int(table.weights.get(r, 0)) for r in RARITIES})
    return weights


def player_view(result):
    """Strip everything from a loot result that the DM has not revealed."""
    result = copy.deepcopy(result)
    result["items"] = [item for item in result["items"] if item.get("visible")]
    if not result.get("coins_visible"):
        result["coins"] = {}
    return result


def result_for(user, roll):
    return roll.result if is_dm(user, roll.campaign) else player_view(roll.result)


def has_visible_loot(result):
    return bool(result.get("coins_visible") or any(i.get("visible") for i in result["items"]))


def visible_rolls(user, campaign=None):
    """Rolls the user may see. Players only get rolls with something revealed."""
    qs = LootRoll.objects.filter(
        Q(campaign__in=dm_campaigns_for(user)) | Q(campaign__in=campaigns_for(user))
    )
    if campaign:
        qs = qs.filter(campaign=campaign)
    dm_campaign_ids = set(dm_campaigns_for(user).values_list("id", flat=True))
    keep = [
        roll.pk
        for roll in qs
        if roll.campaign_id in dm_campaign_ids or has_visible_loot(roll.result)
    ]
    return qs.filter(pk__in=keep)
