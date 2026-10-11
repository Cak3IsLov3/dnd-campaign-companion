"""SRD client: every HTTP call is mocked; the tests exercise the cache."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests
from django.utils import timezone

from srd import client
from srd.models import CachedSRDEntry

pytestmark = pytest.mark.django_db

GOBLIN = {
    "index": "goblin",
    "name": "Goblin",
    "challenge_rating": 0.25,
    "xp": 50,
    "hit_points": 7,
    "armor_class": [{"type": "armor", "value": 15}],
}
MONSTER_LIST = {
    "count": 3,
    "results": [
        {"index": "goblin", "name": "Goblin"},
        {"index": "hobgoblin", "name": "Hobgoblin"},
        {"index": "owlbear", "name": "Owlbear"},
    ],
}


def response(data):
    return Mock(json=Mock(return_value=data), raise_for_status=Mock())


@pytest.fixture
def http():
    with patch("srd.client.requests.get") as get:
        yield get


def test_first_call_fetches_and_stores(http):
    http.return_value = response(GOBLIN)

    assert client.get_monster("goblin") == GOBLIN
    http.assert_called_once()
    assert http.call_args.args[0].endswith("/monsters/goblin")
    assert CachedSRDEntry.objects.get(endpoint="monsters", index="goblin").data == GOBLIN


def test_second_call_is_served_from_the_cache(http):
    http.return_value = response(GOBLIN)

    client.get_monster("goblin")
    client.get_monster("goblin")

    assert http.call_count == 1


def test_expired_entry_is_refetched(http, settings):
    http.return_value = response(GOBLIN)
    client.get_monster("goblin")
    CachedSRDEntry.objects.update(
        fetched_at=timezone.now() - timedelta(seconds=settings.SRD_CACHE_TTL + 1)
    )
    http.return_value = response({**GOBLIN, "hit_points": 9})

    assert client.get_monster("goblin")["hit_points"] == 9
    assert http.call_count == 2


def test_stale_cache_is_used_when_the_api_is_down(http, settings):
    http.return_value = response(GOBLIN)
    client.get_monster("goblin")
    CachedSRDEntry.objects.update(
        fetched_at=timezone.now() - timedelta(seconds=settings.SRD_CACHE_TTL + 1)
    )
    http.side_effect = requests.ConnectionError("down")

    assert client.get_monster("goblin") == GOBLIN


def test_error_without_cache_raises_srd_error(http):
    http.side_effect = requests.Timeout("slow")

    with pytest.raises(client.SRDError):
        client.get_monster("goblin")
    assert not CachedSRDEntry.objects.exists()


def test_http_error_status_raises_srd_error(http):
    http.return_value = Mock(raise_for_status=Mock(side_effect=requests.HTTPError("404")))

    with pytest.raises(client.SRDError):
        client.get_monster("nope")


def test_search_filters_the_cached_list(http):
    http.return_value = response(MONSTER_LIST)

    assert [m["index"] for m in client.search_monsters("GOB")] == ["goblin", "hobgoblin"]
    assert client.search_monsters("owl")[0]["name"] == "Owlbear"
    assert client.search_monsters("  ") == []
    assert http.call_count == 1  # one list fetch serves every search


def test_monster_summary(http):
    http.return_value = response(GOBLIN)

    assert client.monster_summary("goblin") == {
        "index": "goblin", "name": "Goblin", "cr": 0.25, "xp": 50, "hp": 7, "ac": 15,
    }  # fmt: skip


def test_sync_magic_items_fetches_only_missing_details_and_builds_the_pool(http):
    items = {
        "bag-of-holding": {"index": "bag-of-holding", "name": "Bag of Holding", "rarity": {"name": "Uncommon"}},
        "vorpal-sword": {"index": "vorpal-sword", "name": "Vorpal Sword", "rarity": {"name": "Legendary"}},
    }  # fmt: skip
    listing = {"results": [{"index": i, "name": d["name"]} for i, d in items.items()]}

    def fake_get(url, timeout):
        index = url.rsplit("/", 1)[-1]
        return response(items.get(index, listing))

    http.side_effect = fake_get

    assert client.sync_magic_items(max_workers=1) == 2
    assert client.magic_item_pool() == {
        "uncommon": [{"index": "bag-of-holding", "name": "Bag of Holding"}],
        "legendary": [{"index": "vorpal-sword", "name": "Vorpal Sword"}],
    }
    calls = http.call_count
    assert client.sync_magic_items(max_workers=1) == 0
    assert http.call_count == calls  # nothing left to fetch
