from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from campaigns.access import campaign_view

from . import services
from .models import NpcTraitTable


def _draft_key(campaign):
    return f"npc_draft_{campaign.pk}"


def _draft_context(campaign, npc):
    fields = [
        {"name": f, "value": npc[f], "locked": f in npc["locked"]} for f in services.FIELDS
    ] if npc else []  # fmt: skip
    return {"campaign": campaign, "npc": npc, "fields": fields}


@campaign_view(dm_only=True)
def generator(request, campaign):
    npc = request.session.get(_draft_key(campaign))
    return render(request, "npcs/generator.html", _draft_context(campaign, npc))


@campaign_view(dm_only=True)
@require_POST
def generate(request, campaign):
    """HTMX: roll a new NPC, carrying over any locked fields."""
    tables = services.tables_for(campaign)
    npc = services.generate_npc(tables, request.POST.get("seed", "").strip())
    previous = request.session.get(_draft_key(campaign))
    if previous:
        for field in previous["locked"]:
            npc[field] = previous[field]
        npc["locked"] = previous["locked"]
    request.session[_draft_key(campaign)] = npc
    return render(request, "npcs/_draft.html", _draft_context(campaign, npc))


@campaign_view(dm_only=True)
@require_POST
def draft_action(request, campaign, action, field):
    """HTMX: re-roll or (un)lock one field of the draft NPC."""
    npc = request.session.get(_draft_key(campaign))
    if npc:
        if action == "reroll":
            services.reroll_field(npc, field, services.tables_for(campaign))
        elif action == "lock":
            services.toggle_lock(npc, field)
        request.session[_draft_key(campaign)] = npc
    return render(request, "npcs/_draft.html", _draft_context(campaign, npc))


@campaign_view(dm_only=True)
@require_POST
def save(request, campaign):
    npc = request.session.pop(_draft_key(campaign), None)
    if npc:
        character = services.save_as_character(
            npc,
            campaign,
            location=request.POST.get("location", "").strip(),
            faction=request.POST.get("faction", "").strip(),
        )
        messages.success(request, f"{character.name} saved as an NPC.")
    return redirect("campaigns:detail", campaign.pk)


class TraitForm(forms.ModelForm):
    class Meta:
        model = NpcTraitTable
        fields = ["category", "race", "value", "weight"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("category") == "name" and not cleaned.get("race"):
            self.add_error("race", "Names need a race.")
        elif cleaned.get("category") != "name":
            cleaned["race"] = ""
        return cleaned


@campaign_view(dm_only=True)
def tables(request, campaign):
    """List the effective tables and add or override rows for this campaign."""
    form = TraitForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        NpcTraitTable.objects.update_or_create(
            campaign=campaign,
            category=data["category"],
            race=data["race"],
            value=data["value"],
            defaults={"weight": data["weight"]},
        )
        return redirect("npcs:tables", campaign.pk)
    own = {
        (row.category, row.race, row.value): row
        for row in NpcTraitTable.objects.filter(campaign=campaign)
    }
    rows = [
        {"category": category, "race": race, "value": value, "weight": weight,
         "own": own.get((category, race, value))}
        for category, entries in services.tables_for(campaign).items()
        for value, weight, race in entries
    ]  # fmt: skip
    return render(request, "npcs/tables.html", {"campaign": campaign, "form": form, "rows": rows})


@campaign_view(dm_only=True)
@require_POST
def trait_delete(request, campaign, pk):
    """Remove a campaign row; an overridden default falls back to its own weight."""
    get_object_or_404(NpcTraitTable, pk=pk, campaign=campaign).delete()
    return redirect("npcs:tables", campaign.pk)
