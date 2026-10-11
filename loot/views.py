from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from campaigns.access import campaign_view
from campaigns.services import party_levels
from encounters.selectors import total_cr
from srd import client

from . import services
from .models import LootRoll, LootTable
from .selectors import weights_for


def _draft_key(campaign):
    return f"loot_draft_{campaign.pk}"


def _float(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _default_cr(campaign):
    levels = party_levels(campaign)
    return round(sum(levels) / len(levels), 1) if levels else 1


@campaign_view(dm_only=True)
def generator(request, campaign):
    pool = client.magic_item_pool()
    context = {
        "campaign": campaign,
        "draft": request.session.get(_draft_key(campaign)),
        "rolls": campaign.loot_rolls.select_related("encounter", "session"),
        "encounters": campaign.encounters.all(),
        "sessions": campaign.sessions.all(),
        "weights": weights_for(campaign),
        "pool_size": sum(len(items) for items in pool.values()),
        "default_cr": _default_cr(campaign),
    }
    return render(request, "loot/generator.html", context)


@campaign_view(dm_only=True)
@require_POST
def roll(request, campaign):
    """HTMX: roll new loot into the draft, keeping any locked items."""
    encounter = campaign.encounters.filter(pk=request.POST.get("encounter") or None).first()
    cr = _float(request.POST.get("cr"))
    if cr is None:
        # No explicit CR: use the encounter's total CR, else the average party level.
        cr = total_cr(encounter) if encounter else _default_cr(campaign)
    draft = services.generate_loot(
        cr, client.magic_item_pool(), weights_for(campaign), request.POST.get("seed", "").strip()
    )
    previous = request.session.get(_draft_key(campaign)) or {"items": []}
    locked = [item for item in previous["items"] if item["locked"]]
    taken = {item["index"] for item in locked}
    fresh = [item for item in draft["items"] if item["index"] not in taken]
    draft["items"] = (locked + fresh)[: max(services.MAX_ITEMS, len(locked))]
    draft["encounter_id"] = encounter.pk if encounter else None
    request.session[_draft_key(campaign)] = draft
    return render(request, "loot/_draft.html", {"campaign": campaign, "draft": draft})


@campaign_view(dm_only=True)
@require_POST
def draft_action(request, campaign, action, slot):
    """HTMX: re-roll or (un)lock a single item of the draft."""
    draft = request.session.get(_draft_key(campaign))
    if draft and 0 <= slot < len(draft["items"]):
        if action == "reroll":
            services.reroll_item(draft, slot, client.magic_item_pool(), weights_for(campaign))
        elif action == "lock":
            services.toggle_lock(draft, slot)
        request.session[_draft_key(campaign)] = draft
    return render(request, "loot/_draft.html", {"campaign": campaign, "draft": draft})


@campaign_view(dm_only=True)
@require_POST
def save(request, campaign):
    draft = request.session.pop(_draft_key(campaign), None)
    if draft:
        result = {k: draft[k] for k in ["seed", "cr", "coins", "coins_visible", "items"]}
        LootRoll.objects.create(
            campaign=campaign,
            encounter=campaign.encounters.filter(pk=draft.get("encounter_id")).first(),
            session=campaign.sessions.filter(pk=request.POST.get("session") or None).first(),
            seed=draft["seed"],
            result=result,
        )
        messages.success(request, "Loot roll saved.")
    return redirect("loot:generator", campaign.pk)


@campaign_view(dm_only=True)
@require_POST
def roll_visibility(request, campaign, pk, target):
    """HTMX: reveal or hide the coins ("coins") or one item (its slot number)."""
    loot_roll = get_object_or_404(LootRoll, pk=pk, campaign=campaign)
    result = loot_roll.result
    if target == "coins":
        result["coins_visible"] = not result.get("coins_visible")
    elif target.isdigit() and int(target) < len(result["items"]):
        item = result["items"][int(target)]
        item["visible"] = not item.get("visible")
    loot_roll.save(update_fields=["result"])
    context = {
        "campaign": campaign,
        "roll": loot_roll,
        "result": result,
        "is_dm": True,
        "show_delete": request.POST.get("manage") == "1",
    }
    return render(request, "loot/_roll.html", context)


@campaign_view(dm_only=True)
@require_POST
def roll_delete(request, campaign, pk):
    get_object_or_404(LootRoll, pk=pk, campaign=campaign).delete()
    return redirect("loot:generator", campaign.pk)


@campaign_view(dm_only=True)
@require_POST
def weights(request, campaign):
    """Save the campaign's own rarity weights."""
    new = {}
    for rarity in services.RARITIES:
        value = _float(request.POST.get(rarity))
        new[rarity] = int(value) if value is not None else services.DEFAULT_WEIGHTS[rarity]
    LootTable.objects.update_or_create(
        campaign=campaign, defaults={"name": f"{campaign.name} loot", "weights": new}
    )
    messages.success(request, "Rarity weights updated.")
    return redirect("loot:generator", campaign.pk)


@campaign_view(dm_only=True)
@require_POST
def sync(request, campaign):
    """Download the SRD magic items into the cache."""
    try:
        count = client.sync_magic_items()
    except client.SRDError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Cached {count} new magic items from the SRD.")
    return redirect("loot:generator", campaign.pk)
