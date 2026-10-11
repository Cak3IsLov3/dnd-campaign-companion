"""Client for the D&D 5e SRD API with a database-backed cache.

Lookup order: fresh cache -> HTTP -> stale cache. A network failure only
surfaces as `SRDError` when there is nothing cached at all, so the app keeps
working with previously fetched data while the API is down.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .models import CachedSRDEntry

MONSTERS = "monsters"
MAGIC_ITEMS = "magic-items"


class SRDError(Exception):
    """The SRD API could not be reached and no cached copy exists."""


def _fetch(endpoint, index=""):
    url = f"{settings.SRD_API_BASE_URL}/{endpoint}"
    if index:
        url = f"{url}/{index}"
    try:
        response = requests.get(url, timeout=settings.SRD_API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SRDError(f"Could not fetch {endpoint}/{index} from the SRD API: {exc}") from exc


def _store(endpoint, index, data):
    CachedSRDEntry.objects.update_or_create(
        endpoint=endpoint, index=index, defaults={"data": data, "fetched_at": timezone.now()}
    )


def get(endpoint, index=""):
    """Return the JSON for a list (`index=""`) or detail resource."""
    entry = CachedSRDEntry.objects.filter(endpoint=endpoint, index=index).first()
    ttl = timedelta(seconds=settings.SRD_CACHE_TTL)
    if entry and timezone.now() - entry.fetched_at < ttl:
        return entry.data
    try:
        data = _fetch(endpoint, index)
    except SRDError:
        if entry:
            return entry.data  # stale beats nothing
        raise
    _store(endpoint, index, data)
    return data


def search_monsters(query, limit=20):
    """Case-insensitive name search over the (cached) monster list."""
    query = query.strip().lower()
    if not query:
        return []
    results = get(MONSTERS).get("results", [])
    return [m for m in results if query in m["name"].lower()][:limit]


def get_monster(index):
    return get(MONSTERS, index)


def monster_summary(index):
    """The fields of a monster the encounter builder and tracker need."""
    data = get_monster(index)
    armor = data.get("armor_class") or []
    ac = armor[0].get("value", 10) if isinstance(armor, list) and armor else 10
    return {
        "index": data["index"],
        "name": data["name"],
        "cr": data.get("challenge_rating", 0),
        "xp": data.get("xp", 0),
        "hp": data.get("hit_points", 1),
        "ac": ac,
    }


def sync_magic_items(max_workers=8):
    """Fetch details for every magic item that is not cached yet.

    The list endpoint has no rarity, and the loot generator weights on rarity,
    so it needs the detail records. Returns the number of newly cached items.
    """
    indexes = [item["index"] for item in get(MAGIC_ITEMS).get("results", [])]
    cached = set(
        CachedSRDEntry.objects.filter(endpoint=MAGIC_ITEMS)
        .exclude(index="")
        .values_list("index", flat=True)
    )
    missing = [index for index in indexes if index not in cached]

    def fetch(index):
        try:
            return index, _fetch(MAGIC_ITEMS, index)
        except SRDError:
            return index, None

    # HTTP in worker threads, database writes on the calling thread.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fetched = list(pool.map(fetch, missing))
    if missing and not any(data for _, data in fetched):
        raise SRDError("Could not fetch any magic items from the SRD API.")
    count = 0
    for index, data in fetched:
        if data:
            _store(MAGIC_ITEMS, index, data)
            count += 1
    return count


def magic_item_pool():
    """Cached magic items grouped by lower-cased rarity: {rarity: [{index, name}]}."""
    pool = {}
    entries = CachedSRDEntry.objects.filter(endpoint=MAGIC_ITEMS).exclude(index="")
    for entry in entries.order_by("index"):
        rarity = (entry.data.get("rarity") or {}).get("name", "").lower()
        if rarity:
            pool.setdefault(rarity, []).append(
                {"index": entry.data["index"], "name": entry.data["name"]}
            )
    return pool
