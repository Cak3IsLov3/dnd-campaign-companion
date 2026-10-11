"""Backstory Vault rules: who reads what, and which hooks are still unused."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from campaigns.access import dm_campaigns_for, is_dm

from .models import Backstory, Hook, HookLink


def backstory_for(character):
    backstory, _ = Backstory.objects.get_or_create(character=character)
    return backstory


def can_read_text(user, backstory):
    """The owner always reads their backstory; the DM only when it is shared."""
    character = backstory.character
    if character.owner_id == user.id:
        return True
    return backstory.is_visible_to_dm and is_dm(user, character.campaign)


def visible_hooks(user):
    """Players see hooks on their own characters; DMs see all hooks in their campaigns."""
    own = Hook.objects.filter(backstory__character__owner=user)
    dm = Hook.objects.filter(backstory__character__campaign__in=dm_campaigns_for(user))
    return (own | dm).distinct()


def campaign_hooks(campaign):
    return Hook.objects.filter(
        backstory__character__campaign=campaign, backstory__character__is_npc=False
    ).select_related("backstory__character__owner")


def unused_hooks(campaign):
    return campaign_hooks(campaign).filter(links__isnull=True)


def link_hook(hook, npc=None, session=None, encounter=None, date_used=None):
    """Link a hook to exactly one NPC, session or encounter of the same campaign."""
    targets = [t for t in (npc, session, encounter) if t is not None]
    if len(targets) != 1:
        raise ValidationError("Link a hook to exactly one NPC, session or encounter.")
    target = targets[0]
    if target.campaign_id != hook.backstory.character.campaign_id:
        raise ValidationError("The link target belongs to a different campaign.")
    if npc is not None and not npc.is_npc:
        raise ValidationError("Hooks can only be linked to NPCs, not player characters.")
    return HookLink.objects.create(
        hook=hook,
        npc=npc,
        session=session,
        encounter=encounter,
        date_used=date_used or timezone.localdate(),
    )
