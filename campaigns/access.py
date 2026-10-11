"""Role and object-level access rules, shared by the web views and the REST API.

Every rule about "who may see or change what" lives here so the two front ends
cannot drift apart.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Campaign, Character, GameSession, Membership

DM = Membership.Role.DM
PLAYER = Membership.Role.PLAYER


def role_in(user, campaign):
    """Return the user's role in the campaign, or None when not a member."""
    if not user.is_authenticated:
        return None
    return (
        Membership.objects.filter(user=user, campaign=campaign)
        .values_list("role", flat=True)
        .first()
    )


def is_dm(user, campaign):
    return role_in(user, campaign) == DM


def campaigns_for(user):
    return Campaign.objects.filter(memberships__user=user).distinct()


def dm_campaigns_for(user):
    return Campaign.objects.filter(memberships__user=user, memberships__role=DM).distinct()


def visible_characters(user, campaign=None):
    """DMs see every character in their campaigns; players only their own PCs."""
    qs = Character.objects.filter(
        Q(campaign__in=dm_campaigns_for(user))
        | Q(campaign__in=campaigns_for(user), owner=user, is_npc=False)
    )
    return qs.filter(campaign=campaign) if campaign else qs


def can_edit_character(user, character):
    if is_dm(user, character.campaign):
        return True
    return (
        not character.is_npc
        and character.owner_id == user.id
        and role_in(user, character.campaign) == PLAYER
    )


def visible_sessions(user, campaign):
    qs = GameSession.objects.filter(campaign=campaign)
    role = role_in(user, campaign)
    if role == DM:
        return qs
    if role == PLAYER:
        return qs.filter(is_visible_to_players=True)
    return qs.none()


def campaign_view(dm_only=False):
    """Decorator for web views under /campaigns/<campaign_id>/.

    Non-members get a 404 (the campaign's existence is not leaked); members who
    lack the DM role get a 403 on DM-only views. The view receives the campaign
    and `request.is_dm` is set for templates and branching.
    """

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, campaign_id, *args, **kwargs):
            campaign = get_object_or_404(Campaign, pk=campaign_id)
            role = role_in(request.user, campaign)
            if role is None:
                raise Http404
            request.is_dm = role == DM
            if dm_only and not request.is_dm:
                raise PermissionDenied
            return view(request, campaign, *args, **kwargs)

        return wrapper

    return decorator
