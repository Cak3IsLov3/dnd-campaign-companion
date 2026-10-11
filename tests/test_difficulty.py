"""Difficulty calculation, checked against the worked examples in the DMG / SRD."""

import pytest

from encounters.services.difficulty import (
    calculate_difficulty,
    encounter_multiplier,
    party_thresholds,
)


def test_party_thresholds_dmg_example():
    # DMG: three 3rd-level characters and one 2nd-level character.
    assert party_thresholds([3, 3, 3, 2]) == {
        "Easy": 275,
        "Medium": 550,
        "Hard": 825,
        "Deadly": 1400,
    }


def test_dmg_example_bugbear_and_three_hobgoblins_is_hard():
    # DMG: one bugbear (200 XP) and three hobgoblins (100 XP each) total 500 XP;
    # four monsters double that to 1,000 adjusted XP, which is Hard for this party.
    result = calculate_difficulty([3, 3, 3, 2], [200, 100, 100, 100])
    assert result.total_xp == 500
    assert result.multiplier == 2
    assert result.adjusted_xp == 1000
    assert result.difficulty == "Hard"


@pytest.mark.parametrize(
    "count, expected",
    [(1, 1), (2, 1.5), (3, 2), (6, 2), (7, 2.5), (10, 2.5), (11, 3), (14, 3), (15, 4), (40, 4)],
)
def test_multiplier_by_number_of_monsters(count, expected):
    assert encounter_multiplier(count, party_size=4) == expected


def test_small_party_uses_next_higher_multiplier():
    assert encounter_multiplier(1, party_size=2) == 1.5
    assert encounter_multiplier(15, party_size=2) == 5


def test_large_party_uses_next_lower_multiplier():
    assert encounter_multiplier(1, party_size=6) == 0.5
    assert encounter_multiplier(4, party_size=6) == 1.5


@pytest.mark.parametrize(
    "monster_xps, expected",
    [
        ([50], "Trivial"),  # 50 < 100
        ([100], "Easy"),  # 100..199
        ([200], "Medium"),  # exactly the medium threshold
        ([200, 50], "Hard"),  # 250 x 1.5 = 375 >= 300
        ([200, 200], "Deadly"),  # 400 x 1.5 = 600 >= 400
    ],
)
def test_difficulty_bands_for_four_level_one_characters(monster_xps, expected):
    # Four 1st-level characters: Easy 100, Medium 200, Hard 300, Deadly 400.
    assert calculate_difficulty([1, 1, 1, 1], monster_xps).difficulty == expected


def test_no_party_or_no_monsters_is_trivial():
    assert calculate_difficulty([], [200]).difficulty == "Trivial"
    assert calculate_difficulty([5, 5, 5, 5], []).difficulty == "Trivial"


def test_levels_outside_the_table_are_clamped():
    assert party_thresholds([25]) == party_thresholds([20])
    assert party_thresholds([0]) == party_thresholds([1])
