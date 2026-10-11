"""Encounter difficulty following the 5e DMG / SRD rules.

Pure functions over plain numbers: no models, no I/O.

1. Sum each character's XP thresholds for their level -> party thresholds.
2. Sum the monsters' XP and multiply by a factor based on how many there are
   (shifted one step for small or large parties) -> adjusted XP.
3. The difficulty is the highest threshold the adjusted XP reaches.
"""

from dataclasses import dataclass

DIFFICULTIES = ["Easy", "Medium", "Hard", "Deadly"]
TRIVIAL = "Trivial"

# Character level -> (easy, medium, hard, deadly) XP thresholds.
XP_THRESHOLDS = {
    1: (25, 50, 75, 100),
    2: (50, 100, 150, 200),
    3: (75, 150, 225, 400),
    4: (125, 250, 375, 500),
    5: (250, 500, 750, 1100),
    6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700),
    8: (450, 900, 1400, 2100),
    9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800),
    11: (800, 1600, 2400, 3600),
    12: (1000, 2000, 3000, 4500),
    13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700),
    15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200),
    17: (2000, 3900, 5900, 8800),
    18: (2100, 4200, 6300, 9500),
    19: (2400, 4900, 7300, 10900),
    20: (2800, 5700, 8500, 12700),
}

# The multiplier ladder. Party size moves the result one step along it.
MULTIPLIERS = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5]


@dataclass(frozen=True)
class DifficultyResult:
    difficulty: str
    total_xp: int
    adjusted_xp: int
    multiplier: float
    thresholds: dict  # {"Easy": int, "Medium": int, "Hard": int, "Deadly": int}


def party_thresholds(levels):
    """Sum the per-level thresholds for a party given as a list of levels."""
    totals = [0, 0, 0, 0]
    for level in levels:
        row = XP_THRESHOLDS[max(1, min(20, level))]
        totals = [total + xp for total, xp in zip(totals, row, strict=True)]
    return dict(zip(DIFFICULTIES, totals, strict=True))


def encounter_multiplier(monster_count, party_size=4):
    if monster_count <= 0:
        return 1
    if monster_count == 1:
        step = 1
    elif monster_count == 2:
        step = 2
    elif monster_count <= 6:
        step = 3
    elif monster_count <= 10:
        step = 4
    elif monster_count <= 14:
        step = 5
    else:
        step = 6
    if 0 < party_size < 3:
        step += 1
    elif party_size >= 6:
        step -= 1
    return MULTIPLIERS[step]


def calculate_difficulty(party_levels, monster_xps):
    """Rate an encounter.

    `party_levels` is a list of character levels; `monster_xps` holds one XP
    value per individual monster (three goblins -> [50, 50, 50]).
    """
    thresholds = party_thresholds(party_levels)
    total_xp = sum(monster_xps)
    multiplier = encounter_multiplier(len(monster_xps), len(party_levels))
    adjusted_xp = int(total_xp * multiplier)
    difficulty = TRIVIAL
    if party_levels:
        for name in DIFFICULTIES:
            if adjusted_xp >= thresholds[name]:
                difficulty = name
    return DifficultyResult(difficulty, total_xp, adjusted_xp, multiplier, thresholds)
