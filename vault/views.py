from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from campaigns.access import campaign_view
from campaigns.models import Character

from . import services
from .models import Backstory, Hook


class BackstoryForm(forms.ModelForm):
    class Meta:
        model = Backstory
        fields = ["text", "is_visible_to_dm"]
        labels = {
            "is_visible_to_dm": "Let the DM read the full backstory (hooks are always shared)"
        }
        widgets = {"text": forms.Textarea(attrs={"rows": 12})}


class HookForm(forms.ModelForm):
    class Meta:
        model = Hook
        fields = ["title", "type", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


@campaign_view()
def home(request, campaign):
    """DM: every player's hooks and what is still unused. Player: their own characters."""
    if not request.is_dm:
        characters = campaign.characters.filter(owner=request.user, is_npc=False)
        return render(request, "vault/home.html", {"campaign": campaign, "characters": characters})
    entries = []
    for character in campaign.characters.filter(is_npc=False).select_related("owner"):
        backstory = services.backstory_for(character)
        hooks = backstory.hooks.prefetch_related("links__npc", "links__session", "links__encounter")
        entries.append(
            {
                "character": character,
                "text": backstory.text if services.can_read_text(request.user, backstory) else None,
                "hooks": hooks,
                "unused": sum(1 for hook in hooks if not hook.links.all()),
            }
        )
    context = {
        "campaign": campaign,
        "entries": entries,
        "unused_hooks": services.unused_hooks(campaign),
        "npcs": campaign.characters.filter(is_npc=True),
        "sessions": campaign.sessions.all(),
        "encounters": campaign.encounters.all(),
    }
    return render(request, "vault/home.html", context)


def _own_backstory(request, campaign, character_id):
    """Only the owning player edits a backstory - not even the DM."""
    character = get_object_or_404(Character, pk=character_id, campaign=campaign, is_npc=False)
    if character.owner_id != request.user.id:
        raise PermissionDenied
    return services.backstory_for(character)


@campaign_view()
def backstory_edit(request, campaign, character_id):
    backstory = _own_backstory(request, campaign, character_id)
    form = BackstoryForm(request.POST or None, instance=backstory)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Backstory saved.")
        return redirect("vault:backstory", campaign.pk, character_id)
    context = {
        "campaign": campaign,
        "backstory": backstory,
        "form": form,
        "hook_form": HookForm(),
        "hooks": backstory.hooks.all(),
    }
    return render(request, "vault/backstory.html", context)


@campaign_view()
@require_POST
def hook_add(request, campaign, character_id):
    backstory = _own_backstory(request, campaign, character_id)
    form = HookForm(request.POST)
    if form.is_valid():
        hook = form.save(commit=False)
        hook.backstory = backstory
        hook.save()
    else:
        messages.error(request, "A hook needs at least a title.")
    return redirect("vault:backstory", campaign.pk, character_id)


@campaign_view()
@require_POST
def hook_delete(request, campaign, character_id, pk):
    backstory = _own_backstory(request, campaign, character_id)
    get_object_or_404(Hook, pk=pk, backstory=backstory).delete()
    return redirect("vault:backstory", campaign.pk, character_id)


@campaign_view(dm_only=True)
@require_POST
def hook_link(request, campaign, pk):
    """Link a hook to an NPC, session or encounter. Target is posted as "kind:id"."""
    hook = get_object_or_404(services.campaign_hooks(campaign), pk=pk)
    kind, _, target_id = request.POST.get("target", "").partition(":")
    sources = {
        "npc": campaign.characters.filter(is_npc=True),
        "session": campaign.sessions.all(),
        "encounter": campaign.encounters.all(),
    }
    target = sources[kind].filter(pk=target_id or None).first() if kind in sources else None
    try:
        if target is None:
            raise ValidationError("Choose something to link the hook to.")
        services.link_hook(hook, **{kind: target})
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("vault:home", campaign.pk)
