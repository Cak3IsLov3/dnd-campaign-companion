"""Random loot generation.

Pure functions: no database or HTTP access. Callers pass in the magic item
pool ({rarity: [{index, name}]}) and the rarity weights, and every roll is
driven by a seed so the same seed always yields the same loot.
"""

import random
import secrets

RARITIES = ["common", "uncommon", "rare", "very rare", "legendary"]
DEFAULT_WEIGHTS = {"common": 40, "uncommon": 35, "rare": 18, "very rare": 6, "legendary": 1}
MAX_ITEMS = 3

# (highest CR in range, {coin: (dice, sides, multiplier)})
COIN_SCALE = [
    (4, {"cp": (6, 6, 10), "sp": (3, 6, 10), "gp": (2, 6, 5)}),
    (10, {"cp": (2, 6, 100), "sp": (2, 6, 100), "gp": (6, 6, 10)}),
    (16, {"cp": (0, 6, 0), "sp": (4, 6, 100), "gp": (4, 6, 100)}),
    (None, {"cp": (0, 6, 0), "sp": (0, 6, 0), "gp": (12, 6, 500)}),
]


def new_seed():
    return secrets.token_hex(4)


def _rng(seed, *parts):
    # Seeding with a string is stable across processes and Python versions.
    return random.Random(":".join(str(part) for part in (seed, *parts)))


def roll_coins(cr, rng):
    dice = next(dice for max_cr, dice in COIN_SCALE if max_cr is None or cr <= max_cr)
    return {
        coin: sum(rng.randint(1, sides) for _ in range(count)) * multiplier
        for coin, (count, sides, multiplier) in dice.items()
    }


def roll_item(pool, weights, rng, exclude=()):
    """Pick a rarity by weight, then an item of that rarity uniformly.

    Rarities with no weight or no remaining items are skipped. Returns None
    when nothing can be rolled.
    """
    candidates = {}
    for rarity, weight in weights.items():
        items = [item for item in pool.get(rarity, []) if item["index"] not in exclude]
        if weight > 0 and items:
            candidates[rarity] = (weight, items)
    if not candidates:
        return None
    rarities = sorted(candidates)
    rarity = rng.choices(rarities, weights=[candidates[r][0] for r in rarities])[0]
    item = rng.choice(candidates[rarity][1])
    return {
        "index": item["index"],
        "name": item["name"],
        "rarity": rarity,
        "locked": False,
        "visible": False,
        "rerolls": 0,
    }


def generate_loot(cr, pool, weights=None, seed=None):
    """Roll coins and 0-3 magic items for the given CR (or average party level)."""
    weights = weights or DEFAULT_WEIGHTS
    seed = str(seed) if seed not in (None, "") else new_seed()
    rng = _rng(seed)
    coins = roll_coins(cr, rng)
    items = []
    for _ in range(rng.randint(0, MAX_ITEMS)):
        item = roll_item(pool, weights, rng, exclude={i["index"] for i in items})
        if item:
            items.append(item)
    return {"seed": seed, "cr": cr, "coins": coins, "coins_visible": False, "items": items}


def reroll_item(result, slot, pool, weights=None):
    """Replace the item in `slot` unless it is locked. Returns the result.

    The replacement is seeded from the roll's seed, the slot and how often that
    slot was re-rolled, so re-rolls are reproducible too.
    """
    weights = weights or DEFAULT_WEIGHTS
    items = result["items"]
    current = items[slot]
    if current["locked"]:
        return result
    rerolls = current["rerolls"] + 1
    rng = _rng(result["seed"], slot, rerolls)
    replacement = roll_item(pool, weights, rng, exclude={i["index"] for i in items})
    if replacement:
        replacement["rerolls"] = rerolls
        items[slot] = replacement
    return result


def toggle_lock(result, slot):
    item = result["items"][slot]
    item["locked"] = not item["locked"]
    return result
