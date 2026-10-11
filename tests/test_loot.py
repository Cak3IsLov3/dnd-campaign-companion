from collections import Counter

from loot import services
from loot.selectors import player_view

POOL = {
    "common": [{"index": f"c{i}", "name": f"Common {i}"} for i in range(5)],
    "uncommon": [{"index": f"u{i}", "name": f"Uncommon {i}"} for i in range(5)],
    "rare": [{"index": f"r{i}", "name": f"Rare {i}"} for i in range(5)],
    "legendary": [{"index": "l0", "name": "Legendary 0"}],
}


def test_same_seed_gives_same_loot():
    first = services.generate_loot(5, POOL, seed="abc")
    second = services.generate_loot(5, POOL, seed="abc")
    assert first == second
    assert first["seed"] == "abc"


def test_different_seeds_give_different_loot():
    results = {str(services.generate_loot(5, POOL, seed=seed)) for seed in range(20)}
    assert len(results) > 1


def test_a_seed_is_generated_and_reusable_when_none_is_given():
    first = services.generate_loot(5, POOL)
    assert first["seed"]
    assert services.generate_loot(5, POOL, seed=first["seed"]) == first


def test_rolls_between_zero_and_three_unique_items():
    for seed in range(200):
        items = services.generate_loot(3, POOL, seed=seed)["items"]
        assert 0 <= len(items) <= 3
        assert len({item["index"] for item in items}) == len(items)


def test_coins_scale_with_cr():
    def average_gp(cr):
        return sum(services.generate_loot(cr, {}, seed=s)["coins"]["gp"] for s in range(100)) / 100

    assert average_gp(2) < average_gp(8) < average_gp(14) < average_gp(20)


def test_weights_shift_the_rarity_distribution():
    def rarity_counts(weights):
        counts = Counter()
        for seed in range(500):
            for item in services.generate_loot(5, POOL, weights, seed=seed)["items"]:
                counts[item["rarity"]] += 1
        return counts

    mostly_common = rarity_counts({"common": 90, "rare": 10})
    mostly_rare = rarity_counts({"common": 10, "rare": 90})
    assert mostly_common["common"] > mostly_common["rare"] * 3
    assert mostly_rare["rare"] > mostly_rare["common"] * 3


def test_zero_weight_rarity_is_never_rolled():
    weights = {"common": 1, "uncommon": 0, "rare": 0, "legendary": 0}
    for seed in range(100):
        items = services.generate_loot(5, POOL, weights, seed=seed)["items"]
        assert all(item["rarity"] == "common" for item in items)


def test_empty_pool_gives_coins_only():
    result = services.generate_loot(5, {}, seed="abc")
    assert result["items"] == []
    assert result["coins"]["gp"] > 0


def _roll_with_items(minimum=2):
    for seed in range(100):
        result = services.generate_loot(5, POOL, seed=seed)
        if len(result["items"]) >= minimum:
            return result
    raise AssertionError("no seed produced enough items")


def test_reroll_replaces_only_that_slot_and_is_reproducible():
    result = _roll_with_items()
    before = [item["index"] for item in result["items"]]
    twin = services.generate_loot(5, POOL, seed=result["seed"])

    services.reroll_item(result, 0, POOL)
    services.reroll_item(twin, 0, POOL)

    after = [item["index"] for item in result["items"]]
    assert after[0] != before[0]
    assert after[1:] == before[1:]
    assert result == twin


def test_locked_item_survives_a_reroll():
    result = _roll_with_items()
    services.toggle_lock(result, 0)
    locked = dict(result["items"][0])
    services.reroll_item(result, 0, POOL)
    assert result["items"][0] == locked


def test_player_view_only_contains_revealed_loot():
    result = _roll_with_items()
    assert player_view(result) == {**result, "items": [], "coins": {}}

    result["items"][0]["visible"] = True
    result["coins_visible"] = True
    view = player_view(result)
    assert [item["index"] for item in view["items"]] == [result["items"][0]["index"]]
    assert view["coins"] == result["coins"]
