import pytest
from django.urls import reverse

from encounters.models import Combatant, Encounter, EncounterMonster
from encounters.selectors import encounter_difficulty
from encounters.services import tracker

pytestmark = pytest.mark.django_db


@pytest.fixture
def encounter(campaign, pc, other_pc):
    encounter = Encounter.objects.create(campaign=campaign, name="Goblin ambush")
    EncounterMonster.objects.create(
        encounter=encounter,
        monster_index="goblin",
        name="Goblin",
        count=2,
        cr=0.25,
        xp=50,
        hp=7,
        ac=15,
    )
    return encounter


def names(encounter):
    return [c.name for c in encounter.combatants.all()]


def test_encounter_difficulty_uses_the_party_and_monster_counts(encounter):
    # Two level 3 PCs (Easy 150, Medium 300); 2 goblins = 100 XP x 1.5, x2 for a small party.
    result = encounter_difficulty(encounter)
    assert (result.total_xp, result.multiplier, result.adjusted_xp) == (100, 2, 200)
    assert result.difficulty == "Easy"


def test_start_combat_loads_monsters_and_party_once(encounter, pc, other_pc):
    tracker.start_combat(encounter)
    tracker.start_combat(encounter)

    assert sorted(names(encounter)) == sorted(["Goblin 1", "Goblin 2", pc.name, other_pc.name])
    goblin = encounter.combatants.get(name="Goblin 1")
    assert (goblin.hp, goblin.max_hp, goblin.ac) == (7, 7, 15)
    assert encounter.status == Encounter.Status.ACTIVE


def test_combatants_sort_by_initiative_descending(encounter):
    for name, initiative in [("Slow", 3), ("Fast", 19), ("Middle", 11)]:
        Combatant.objects.create(encounter=encounter, name=name, initiative=initiative)
    assert names(encounter) == ["Fast", "Middle", "Slow"]


def test_next_turn_walks_the_order_and_counts_rounds(encounter):
    for name, initiative in [("A", 20), ("B", 10)]:
        Combatant.objects.create(encounter=encounter, name=name, initiative=initiative)

    assert tracker.next_turn(encounter).name == "A"
    assert tracker.next_turn(encounter).name == "B"
    assert encounter.round == 1
    assert tracker.next_turn(encounter).name == "A"
    encounter.refresh_from_db()
    assert encounter.round == 2
    assert encounter.combatants.filter(is_active_turn=True).count() == 1


def test_next_turn_on_an_empty_encounter_does_nothing(encounter):
    assert tracker.next_turn(encounter) is None


def test_hp_is_clamped_between_zero_and_max(encounter):
    combatant = Combatant.objects.create(encounter=encounter, name="A", hp=10, max_hp=10)
    assert tracker.change_hp(combatant, -4).hp == 6
    assert tracker.change_hp(combatant, 100).hp == 10
    assert tracker.change_hp(combatant, -100).hp == 0


def test_conditions_toggle_on_and_off(encounter):
    combatant = Combatant.objects.create(encounter=encounter, name="A")
    tracker.toggle_condition(combatant, "prone")
    tracker.toggle_condition(combatant, "poisoned")
    tracker.toggle_condition(combatant, "prone")
    tracker.toggle_condition(combatant, "not-a-condition")
    combatant.refresh_from_db()
    assert combatant.conditions == ["poisoned"]


# --- HTMX endpoints --------------------------------------------------------


def action_url(encounter, action):
    return reverse("encounters:tracker_action", args=[encounter.campaign_id, encounter.pk, action])


def test_dm_drives_the_tracker_over_htmx(as_user, dm, encounter):
    client = as_user(dm)
    assert client.post(action_url(encounter, "start")).status_code == 200
    goblin = encounter.combatants.get(name="Goblin 1")

    client.post(action_url(encounter, "initiative"), {"combatant": goblin.pk, "initiative": 18})
    client.post(
        action_url(encounter, "hp"), {"combatant": goblin.pk, "amount": 5, "mode": "damage"}
    )
    client.post(action_url(encounter, "condition"), {"combatant": goblin.pk, "condition": "prone"})
    response = client.post(action_url(encounter, "next"))

    goblin.refresh_from_db()
    assert (goblin.initiative, goblin.hp, goblin.conditions) == (18, 2, ["prone"])
    assert goblin.is_active_turn  # highest initiative goes first
    assert "Next turn" in response.content.decode()


def test_players_get_a_read_only_tracker(as_user, player, encounter):
    tracker.start_combat(encounter)
    goblin = encounter.combatants.get(name="Goblin 1")
    client = as_user(player)

    html = client.get(
        reverse("encounters:tracker", args=[encounter.campaign_id, encounter.pk])
    ).content.decode()
    assert "Goblin 1" in html
    assert "Next turn" not in html and "Damage" not in html
    panel = reverse("encounters:tracker_panel", args=[encounter.campaign_id, encounter.pk])
    assert client.get(panel).status_code == 200

    for action, data in [
        ("next", {}),
        ("hp", {"combatant": goblin.pk, "amount": 5, "mode": "damage"}),
        ("condition", {"combatant": goblin.pk, "condition": "prone"}),
        ("remove", {"combatant": goblin.pk}),
    ]:
        assert client.post(action_url(encounter, action), data).status_code == 403
    goblin.refresh_from_db()
    assert (goblin.hp, goblin.conditions, goblin.is_active_turn) == (7, [], False)
