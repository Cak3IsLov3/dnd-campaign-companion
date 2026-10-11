from django.db.models import Q

from campaigns.access import campaigns_for, dm_campaigns_for
from campaigns.services import party_levels

from .models import Encounter
from .services.difficulty import calculate_difficulty


def visible_encounters(user, campaign=None):
    """DMs see all their encounters; players never see ones still being planned."""
    qs = Encounter.objects.filter(
        Q(campaign__in=dm_campaigns_for(user))
        | Q(campaign__in=campaigns_for(user), status__in=["active", "done"])
    )
    return qs.filter(campaign=campaign) if campaign else qs


def monster_xps(encounter):
    """One XP value per individual monster in the encounter."""
    xps = []
    for monster in encounter.monsters.all():
        xps.extend([monster.xp] * monster.count)
    return xps


def encounter_difficulty(encounter):
    return calculate_difficulty(party_levels(encounter.campaign), monster_xps(encounter))


def total_cr(encounter):
    return float(sum(m.cr * m.count for m in encounter.monsters.all()))
