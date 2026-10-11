from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from encounters.selectors import visible_encounters
from loot.selectors import result_for, visible_rolls

from . import access, services
from .forms import CampaignForm, CharacterForm, GameSessionForm, JoinForm
from .models import Character, GameSession


@login_required
def campaign_list(request):
    memberships = request.user.memberships.select_related("campaign")
    return render(
        request, "campaigns/list.html", {"memberships": memberships, "join_form": JoinForm()}
    )


@login_required
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        campaign = services.create_campaign(request.user, **form.cleaned_data)
        return redirect("campaigns:detail", campaign.pk)
    return render(request, "form.html", {"form": form, "title": "New campaign"})


@login_required
@require_POST
def campaign_join(request):
    form = JoinForm(request.POST)
    if form.is_valid():
        try:
            campaign = services.join_campaign(request.user, form.cleaned_data["invite_code"])
        except services.InvalidInviteCode as exc:
            messages.error(request, str(exc))
        else:
            return redirect("campaigns:detail", campaign.pk)
    return redirect("campaigns:list")


@access.campaign_view()
def campaign_detail(request, campaign):
    characters = access.visible_characters(request.user, campaign)
    context = {
        "campaign": campaign,
        "pcs": characters.filter(is_npc=False).select_related("owner"),
        "npcs": characters.filter(is_npc=True),
        "sessions": access.visible_sessions(request.user, campaign),
        "encounters": visible_encounters(request.user, campaign),
        "members": campaign.memberships.select_related("user"),
    }
    return render(request, "campaigns/detail.html", context)


# --- Characters -----------------------------------------------------------


@access.campaign_view()
def character_create(request, campaign):
    initial = {"is_npc": request.GET.get("npc") == "1"}
    form = CharacterForm(
        request.POST or None, campaign=campaign, is_dm=request.is_dm, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        character = form.save(commit=False)
        character.campaign = campaign
        if not request.is_dm:
            character.owner = request.user
            character.is_npc = False
        character.save()
        return redirect("campaigns:detail", campaign.pk)
    return render(
        request, "form.html", {"form": form, "title": "New character", "campaign": campaign}
    )


def _editable_character(request, campaign, pk):
    character = get_object_or_404(Character, pk=pk, campaign=campaign)
    if not access.can_edit_character(request.user, character):
        raise PermissionDenied
    return character


@access.campaign_view()
def character_edit(request, campaign, pk):
    character = _editable_character(request, campaign, pk)
    form = CharacterForm(
        request.POST or None, instance=character, campaign=campaign, is_dm=request.is_dm
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("campaigns:detail", campaign.pk)
    context = {"form": form, "title": f"Edit {character.name}", "campaign": campaign}
    return render(request, "form.html", context)


@access.campaign_view()
@require_POST
def character_delete(request, campaign, pk):
    _editable_character(request, campaign, pk).delete()
    return redirect("campaigns:detail", campaign.pk)


# --- Session log ----------------------------------------------------------


@access.campaign_view(dm_only=True)
def session_create(request, campaign):
    last = campaign.sessions.first()
    initial = {"number": last.number + 1 if last else 1, "date": timezone.localdate()}
    form = GameSessionForm(request.POST or None, campaign=campaign, initial=initial)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.campaign = campaign
        session.save()
        return redirect("campaigns:session_detail", campaign.pk, session.pk)
    return render(
        request, "form.html", {"form": form, "title": "New session", "campaign": campaign}
    )


@access.campaign_view()
def session_detail(request, campaign, pk):
    # visible_sessions hides unpublished sessions from players (404, not 403).
    session = get_object_or_404(access.visible_sessions(request.user, campaign), pk=pk)
    rolls = visible_rolls(request.user, campaign).filter(session=session)
    loot = [(roll, result_for(request.user, roll)) for roll in rolls]
    context = {"campaign": campaign, "session": session, "loot": loot}
    return render(request, "campaigns/session_detail.html", context)


@access.campaign_view(dm_only=True)
def session_edit(request, campaign, pk):
    session = get_object_or_404(GameSession, pk=pk, campaign=campaign)
    form = GameSessionForm(request.POST or None, instance=session, campaign=campaign)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("campaigns:session_detail", campaign.pk, session.pk)
    context = {"form": form, "title": f"Edit session {session.number}", "campaign": campaign}
    return render(request, "form.html", context)


@access.campaign_view(dm_only=True)
@require_POST
def session_toggle_visibility(request, campaign, pk):
    """HTMX: flip whether players can read this session's notes."""
    session = get_object_or_404(GameSession, pk=pk, campaign=campaign)
    session.is_visible_to_players = not session.is_visible_to_players
    session.save(update_fields=["is_visible_to_players"])
    context = {"campaign": campaign, "session": session}
    return render(request, "campaigns/_visibility.html", context)
