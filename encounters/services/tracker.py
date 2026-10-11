"""Initiative tracker rules: loading combatants, turn order, HP and conditions."""

from django.db import transaction

from ..models import Combatant, Encounter

CONDITIONS = [
    "blinded",
    "charmed",
    "deafened",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
]


@transaction.atomic
def start_combat(encounter):
    """Load the encounter's monsters and the party as combatants and go active.

    Safe to call again: combatants are only created the first time.
    """
    if not encounter.combatants.exists():
        for monster in encounter.monsters.all():
            for number in range(1, monster.count + 1):
                name = f"{monster.name} {number}" if monster.count > 1 else monster.name
                Combatant.objects.create(
                    encounter=encounter, name=name, hp=monster.hp, max_hp=monster.hp, ac=monster.ac
                )
        for character in encounter.campaign.characters.filter(is_npc=False):
            add_character(encounter, character)
    encounter.status = Encounter.Status.ACTIVE
    encounter.round = 1
    encounter.save(update_fields=["status", "round"])
    return encounter


def add_character(encounter, character, initiative=0):
    return Combatant.objects.create(
        encounter=encounter,
        character=character,
        name=character.name,
        initiative=initiative,
        hp=character.max_hp,
        max_hp=character.max_hp,
        ac=character.ac,
    )


@transaction.atomic
def next_turn(encounter):
    """Pass the turn to the next combatant in initiative order.

    Wrapping past the end of the order starts a new round. Returns the
    combatant whose turn it now is, or None when the encounter is empty.
    """
    order = list(encounter.combatants.all())
    if not order:
        return None
    current = next((i for i, c in enumerate(order) if c.is_active_turn), None)
    if current is None:
        upcoming = 0
    else:
        upcoming = (current + 1) % len(order)
        if upcoming == 0:
            encounter.round += 1
            encounter.save(update_fields=["round"])
    encounter.combatants.update(is_active_turn=False)
    active = order[upcoming]
    active.is_active_turn = True
    active.save(update_fields=["is_active_turn"])
    return active


def change_hp(combatant, delta):
    """Heal (positive) or damage (negative), clamped to 0..max_hp."""
    combatant.hp = max(0, min(combatant.max_hp, combatant.hp + delta))
    combatant.save(update_fields=["hp"])
    return combatant


def toggle_condition(combatant, condition):
    if condition not in CONDITIONS:
        return combatant
    if condition in combatant.conditions:
        combatant.conditions.remove(condition)
    else:
        combatant.conditions.append(condition)
    combatant.save(update_fields=["conditions"])
    return combatant


def end_combat(encounter):
    encounter.combatants.update(is_active_turn=False)
    encounter.status = Encounter.Status.DONE
    encounter.save(update_fields=["status"])
    return encounter
