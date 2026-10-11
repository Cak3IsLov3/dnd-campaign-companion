from collections import Counter

import pytest

from campaigns.models import Character
from npcs import services
from npcs.models import NpcTraitTable

TABLES = {
    "name": [
        ("Aelar", 1, "Elf"), ("Lia", 1, "Elf"), ("Thamior", 1, "Elf"),
        ("Borin", 1, "Dwarf"), ("Helga", 1, "Dwarf"), ("Durgan", 1, "Dwarf"),
    ],
    "occupation": [("Smith", 1, ""), ("Baker", 1, ""), ("Guard", 1, ""), ("Scribe", 1, "")],
    "trait": [("Grumpy", 1, ""), ("Cheerful", 1, ""), ("Shy", 1, "")],
    "secret": [("Is a spy", 1, ""), ("Owes money", 1, ""), ("Is cursed", 1, "")],
    "motivation": [("Gold", 1, ""), ("Revenge", 1, ""), ("Family", 1, "")],
}  # fmt: skip
NAMES_BY_RACE = {
    "Elf": {"Aelar", "Lia", "Thamior"},
    "Dwarf": {"Borin", "Helga", "Durgan"},
}


def test_same_seed_gives_same_npc():
    assert services.generate_npc(TABLES, seed="x") == services.generate_npc(TABLES, seed="x")


def test_different_seeds_give_different_npcs():
    npcs = {str(services.generate_npc(TABLES, seed=seed)) for seed in range(20)}
    assert len(npcs) > 1


def test_every_field_is_filled():
    npc = services.generate_npc(TABLES, seed="x")
    assert all(npc[field] for field in services.FIELDS)


def test_name_matches_race():
    for seed in range(100):
        npc = services.generate_npc(TABLES, seed=seed)
        assert npc["name"] in NAMES_BY_RACE[npc["race"]]


def test_weights_shift_the_distribution():
    tables = {**TABLES, "occupation": [("Smith", 95, ""), ("Baker", 5, "")]}
    counts = Counter(services.generate_npc(tables, seed=s)["occupation"] for s in range(400))
    assert counts["Smith"] > counts["Baker"] * 5


def test_zero_weight_rows_are_never_picked():
    tables = {**TABLES, "trait": [("Grumpy", 0, ""), ("Cheerful", 1, "")]}
    assert {services.generate_npc(tables, seed=s)["trait"] for s in range(100)} == {"Cheerful"}


def test_reroll_changes_one_field_and_is_reproducible():
    npc = services.generate_npc(TABLES, seed="x")
    twin = services.generate_npc(TABLES, seed="x")
    before = dict(npc)

    # Re-roll until the value changes; a single re-roll may land on the same row.
    for _ in range(20):
        services.reroll_field(npc, "secret", TABLES)
        services.reroll_field(twin, "secret", TABLES)
        if npc["secret"] != before["secret"]:
            break

    assert npc["secret"] != before["secret"]
    assert npc == twin
    for field in ["race", "name", "occupation", "trait", "motivation"]:
        assert npc[field] == before[field]


def test_locked_field_is_not_rerolled():
    npc = services.generate_npc(TABLES, seed="x")
    services.toggle_lock(npc, "occupation")
    before = npc["occupation"]
    for _ in range(20):
        services.reroll_field(npc, "occupation", TABLES)
    assert npc["occupation"] == before


def test_rerolling_race_also_rerolls_an_unlocked_name():
    npc = services.generate_npc(TABLES, seed="x")
    for _ in range(20):
        services.reroll_field(npc, "race", TABLES)
        assert npc["name"] in NAMES_BY_RACE[npc["race"]]


@pytest.mark.django_db
def test_default_tables_are_seeded_and_produce_a_full_npc():
    npc = services.generate_npc(services.tables_for(), seed="seeded")
    assert all(npc[field] for field in services.FIELDS)


@pytest.mark.django_db
def test_campaign_rows_extend_and_override_the_defaults(campaign):
    default = NpcTraitTable.objects.filter(category="occupation", campaign=None).first()
    NpcTraitTable.objects.create(
        campaign=campaign, category="occupation", value=default.value, weight=0
    )
    NpcTraitTable.objects.create(
        campaign=campaign, category="occupation", value="Dragon tamer", weight=7
    )

    occupations = {
        value: weight for value, weight, _ in services.tables_for(campaign)["occupation"]
    }
    assert occupations[default.value] == 0
    assert occupations["Dragon tamer"] == 7
    # Other campaigns still see the untouched default.
    assert (
        dict((v, w) for v, w, _ in services.tables_for()["occupation"])[default.value]
        == default.weight
    )


@pytest.mark.django_db
def test_save_as_character_creates_an_npc(campaign):
    npc = services.generate_npc(TABLES, seed="x")
    character = services.save_as_character(npc, campaign, location="Phandalin", faction="Zhentarim")

    assert Character.objects.get(pk=character.pk).is_npc
    assert character.owner is None
    assert (character.name, character.race, character.char_class) == (
        npc["name"], npc["race"], npc["occupation"],
    )  # fmt: skip
    assert character.location == "Phandalin"
    assert npc["secret"] in character.notes
