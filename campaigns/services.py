from django.db import transaction

from .models import Campaign, Membership


class InvalidInviteCode(Exception):
    pass


@transaction.atomic
def create_campaign(user, name, description=""):
    """Create a campaign and make its creator the DM."""
    campaign = Campaign.objects.create(name=name, description=description, dm=user)
    Membership.objects.create(user=user, campaign=campaign, role=Membership.Role.DM)
    return campaign


def join_campaign(user, invite_code):
    """Add the user as a player via an invite code. Joining twice is a no-op."""
    campaign = Campaign.objects.filter(invite_code=invite_code.strip()).first()
    if campaign is None:
        raise InvalidInviteCode("No campaign matches that invite code.")
    Membership.objects.get_or_create(
        user=user, campaign=campaign, defaults={"role": Membership.Role.PLAYER}
    )
    return campaign


def party_levels(campaign):
    """Levels of the player characters, used for difficulty and loot scaling."""
    return list(campaign.characters.filter(is_npc=False).values_list("level", flat=True))
