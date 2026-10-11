from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from campaigns.access import campaign_view
from srd import client

from .models import Combatant, Encounter, EncounterMonster
from .selectors import encounter_difficulty, visible_encounters
from .services import tracker


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --- Encounter builder ----------------------------------------------------


@campaign_view(dm_only=True)
@require_POST
def encounter_create(request, campaign):
    name = request.POST.get("name", "").strip() or "New encounter"
    encounter = Encounter.objects.create(campaign=campaign, name=name)
    return redirect("encounters:detail", campaign.pk, encounter.pk)


def _builder_context(campaign, encounter):
    return {
        "campaign": campaign,
        "encounter": encounter,
        "monsters": encounter.monsters.all(),
        "result": encounter_difficulty(encounter),
        "party_size": campaign.characters.filter(is_npc=False).count(),
    }


@campaign_view(dm_only=True)
def encounter_detail(request, campaign, pk):
    encounter = get_object_or_404(Encounter, pk=pk, campaign=campaign)
    return render(request, "encounters/detail.html", _builder_context(campaign, encounter))


@campaign_view(dm_only=True)
@require_POST
def encounter_delete(request, campaign, pk):
    get_object_or_404(Encounter, pk=pk, campaign=campaign).delete()
    return redirect("campaigns:detail", campaign.pk)


@campaign_view(dm_only=True)
def monster_search(request, campaign, pk):
    """HTMX: search SRD monsters by name."""
    encounter = get_object_or_404(Encounter, pk=pk, campaign=campaign)
    context = {"campaign": campaign, "encounter": encounter, "results": [], "error": ""}
    try:
        context["results"] = client.search_monsters(request.GET.get("q", ""))
    except client.SRDError:
        context["error"] = "The SRD API is unreachable right now. Try again in a moment."
    return render(request, "encounters/_monster_results.html", context)


@campaign_view(dm_only=True)
@require_POST
def monster_add(request, campaign, pk):
    """HTMX: add an SRD monster (or bump its count) and re-render the builder."""
    encounter = get_object_or_404(Encounter, pk=pk, campaign=campaign)
    context = {}
    try:
        summary = client.monster_summary(request.POST.get("index", ""))
    except client.SRDError:
        context["error"] = "Could not load that monster from the SRD API."
    else:
        monster, created = EncounterMonster.objects.get_or_create(
            encounter=encounter,
            monster_index=summary["index"],
            defaults={k: summary[k] for k in ["name", "cr", "xp", "hp", "ac"]},
        )
        if not created:
            monster.count += 1
            monster.save(update_fields=["count"])
    context.update(_builder_context(campaign, encounter))
    return render(request, "encounters/_builder.html", context)


@campaign_view(dm_only=True)
@require_POST
def monster_update(request, campaign, pk, monster_id):
    """HTMX: change a monster's count; a count of 0 removes it."""
    encounter = get_object_or_404(Encounter, pk=pk, campaign=campaign)
    monster = get_object_or_404(EncounterMonster, pk=monster_id, encounter=encounter)
    count = _int(request.POST.get("count"), monster.count)
    if count <= 0:
        monster.delete()
    else:
        monster.count = count
        monster.save(update_fields=["count"])
    return render(request, "encounters/_builder.html", _builder_context(campaign, encounter))


# --- Initiative tracker ---------------------------------------------------


def _tracker_context(request, campaign, encounter):
    return {
        "campaign": campaign,
        "encounter": encounter,
        "combatants": encounter.combatants.all(),
        "conditions": tracker.CONDITIONS,
        "is_dm": request.is_dm,
        "absent_pcs": campaign.characters.filter(is_npc=False).exclude(
            pk__in=encounter.combatants.filter(character__isnull=False).values("character")
        ),
    }


def _visible_encounter(request, campaign, pk):
    return get_object_or_404(visible_encounters(request.user, campaign), pk=pk)


@campaign_view()
def tracker_page(request, campaign, pk):
    encounter = _visible_encounter(request, campaign, pk)
    return render(
        request, "encounters/tracker.html", _tracker_context(request, campaign, encounter)
    )


@campaign_view()
def tracker_panel(request, campaign, pk):
    """HTMX: the tracker table. Players poll this for a live read-only view."""
    encounter = _visible_encounter(request, campaign, pk)
    return render(
        request, "encounters/_tracker.html", _tracker_context(request, campaign, encounter)
    )


@campaign_view(dm_only=True)
@require_POST
def tracker_action(request, campaign, pk, action):
    """HTMX: every DM mutation of the tracker; responds with the updated table."""
    encounter = get_object_or_404(Encounter, pk=pk, campaign=campaign)
    post = request.POST

    def combatant():
        return get_object_or_404(Combatant, pk=post.get("combatant"), encounter=encounter)

    if action == "start":
        tracker.start_combat(encounter)
    elif action == "next":
        tracker.next_turn(encounter)
    elif action == "end":
        tracker.end_combat(encounter)
    elif action == "hp":
        amount = abs(_int(post.get("amount")))
        tracker.change_hp(combatant(), amount if post.get("mode") == "heal" else -amount)
    elif action == "initiative":
        target = combatant()
        target.initiative = _int(post.get("initiative"))
        target.save(update_fields=["initiative"])
    elif action == "condition":
        tracker.toggle_condition(combatant(), post.get("condition", ""))
    elif action == "add":
        character = campaign.characters.filter(pk=_int(post.get("character"), None)).first()
        if character:
            if not encounter.combatants.filter(character=character).exists():
                tracker.add_character(encounter, character, _int(post.get("initiative")))
        elif post.get("name", "").strip():
            hp = max(1, _int(post.get("hp"), 1))
            Combatant.objects.create(
                encounter=encounter,
                name=post["name"].strip(),
                initiative=_int(post.get("initiative")),
                hp=hp,
                max_hp=hp,
                ac=_int(post.get("ac"), 10),
            )
    elif action == "remove":
        combatant().delete()
    else:
        return HttpResponseBadRequest("Unknown tracker action.")
    return render(
        request, "encounters/_tracker.html", _tracker_context(request, campaign, encounter)
    )
