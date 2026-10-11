"""NPC generation from weighted tables.

`generate_npc` and `reroll_field` are pure: they take the tables as plain data
({category: [(value, weight, race)]}) and a seed. `tables_for` is the only
function that touches the database.
"""

import random
import secrets

FIELDS = ["race", "name", "occupation", "trait", "secret", "motivation"]
RACE_FREE = ["occupation", "trait", "secret", "motivation"]


def new_seed():
    return secrets.token_hex(4)


def _rng(seed, *parts):
    return random.Random(":".join(str(part) for part in (seed, *parts)))


def tables_for(campaign=None):
    """Effective tables for a campaign: defaults, overridden by campaign rows."""
    from .models import NpcTraitTable

    rows = {}
    defaults = NpcTraitTable.objects.filter(campaign__isnull=True)
    own = NpcTraitTable.objects.filter(campaign=campaign) if campaign else []
    for row in [*defaults, *own]:  # campaign rows last so they win
        rows[(row.category, row.race, row.value)] = row.weight
    tables = {}
    for (category, race, value), weight in sorted(rows.items()):
        tables.setdefault(category, []).append((value, weight, race))
    return tables


def _pick(rows, rng):
    rows = [(value, weight) for value, weight in rows if weight > 0]
    if not rows:
        return ""
    return rng.choices([value for value, _ in rows], weights=[weight for _, weight in rows])[0]


def _roll(field, npc, tables, rng):
    if field == "race":
        # A race is available when it has at least one usable name.
        races = sorted({race for _, weight, race in tables.get("name", []) if race and weight > 0})
        return rng.choice(races) if races else ""
    if field == "name":
        rows = [(v, w) for v, w, race in tables.get("name", []) if race == npc.get("race", "")]
        return _pick(rows, rng)
    return _pick([(v, w) for v, w, _ in tables.get(field, [])], rng)


def generate_npc(tables, seed=None):
    """Roll a complete NPC. The same tables and seed always give the same NPC."""
    seed = str(seed) if seed not in (None, "") else new_seed()
    npc = {"seed": seed, "locked": [], "rerolls": {}}
    for field in FIELDS:  # race first: the name depends on it
        npc[field] = _roll(field, npc, tables, _rng(seed, field))
    return npc


def reroll_field(npc, field, tables):
    """Re-roll one unlocked field. Re-rolling the race also re-rolls an unlocked name."""
    if field not in FIELDS or field in npc["locked"]:
        return npc
    fields = [field]
    if field == "race" and "name" not in npc["locked"]:
        fields.append("name")
    for name in fields:
        count = npc["rerolls"].get(name, 0) + 1
        npc["rerolls"][name] = count
        npc[name] = _roll(name, npc, tables, _rng(npc["seed"], name, count))
    return npc


def toggle_lock(npc, field):
    if field in FIELDS:
        if field in npc["locked"]:
            npc["locked"].remove(field)
        else:
            npc["locked"].append(field)
    return npc


def save_as_character(npc, campaign, location="", faction=""):
    """Persist a generated NPC as a Character with is_npc=True."""
    from campaigns.models import Character

    notes = "\n".join(
        f"{label}: {npc[key]}"
        for key, label in [("trait", "Trait"), ("secret", "Secret"), ("motivation", "Motivation")]
        if npc.get(key)
    )
    return Character.objects.create(
        campaign=campaign,
        name=npc["name"] or "Unnamed NPC",
        race=npc["race"],
        char_class=npc["occupation"],
        is_npc=True,
        location=location,
        faction=faction,
        notes=notes,
    )
