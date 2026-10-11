"""REST API: token auth and the same permission rules as the web app."""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from campaigns.models import Character
from encounters.models import Encounter
from loot.models import LootRoll
from vault.models import Hook
from vault.services import backstory_for

pytestmark = pytest.mark.django_db

POOL = {"common": [{"index": "potion", "name": "Potion of Healing"}]}


def ids(response):
    return {row["id"] for row in response.json()}


# --- Authentication --------------------------------------------------------


def test_anonymous_requests_are_rejected():
    assert APIClient().get("/api/campaigns/").status_code == 401


def test_token_authentication(player, campaign):
    client = APIClient()
    token = client.post("/api/auth/token/", {"username": "player", "password": "pw"}).json()[
        "token"
    ]
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

    response = client.get("/api/campaigns/")
    assert response.status_code == 200
    assert ids(response) == {campaign.pk}


def test_openapi_schema_and_docs_are_served(client):
    assert client.get("/api/schema/").status_code == 200
    assert client.get("/api/docs/").status_code == 200


# --- Campaigns -------------------------------------------------------------


def test_campaigns_are_limited_to_members_and_only_the_dm_gets_the_invite_code(
    api, campaign, dm, player, outsider
):
    assert (
        api(dm).get(f"/api/campaigns/{campaign.pk}/").json()["invite_code"] == campaign.invite_code
    )
    as_player = api(player).get(f"/api/campaigns/{campaign.pk}/").json()
    assert as_player["role"] == "PLAYER" and as_player["invite_code"] is None
    assert api(outsider).get(f"/api/campaigns/{campaign.pk}/").status_code == 404
    assert api(outsider).get("/api/campaigns/").json() == []


def test_create_and_join_campaign(api, dm, outsider):
    created = api(dm).post("/api/campaigns/", {"name": "Via API"})
    assert created.status_code == 201 and created.json()["role"] == "DM"

    joined = api(outsider).post(
        "/api/campaigns/join/", {"invite_code": created.json()["invite_code"]}
    )
    assert joined.json()["role"] == "PLAYER"
    assert api(outsider).post("/api/campaigns/join/", {"invite_code": "nope"}).status_code == 400


def test_player_cannot_change_or_delete_a_campaign(api, campaign, player):
    assert (
        api(player).patch(f"/api/campaigns/{campaign.pk}/", {"name": "Mine now"}).status_code == 403
    )
    assert api(player).delete(f"/api/campaigns/{campaign.pk}/").status_code == 403


# --- Characters and NPCs ---------------------------------------------------


def test_character_visibility(api, campaign, dm, player, pc, other_pc, npc):
    assert ids(api(player).get("/api/characters/")) == {pc.pk}
    assert ids(api(dm).get(f"/api/characters/?campaign={campaign.pk}")) == {
        pc.pk,
        other_pc.pk,
        npc.pk,
    }
    assert api(player).get(f"/api/characters/{other_pc.pk}/").status_code == 404
    assert api(player).patch(f"/api/characters/{npc.pk}/", {"name": "x"}).status_code == 404


def test_player_manages_only_their_own_character(api, campaign, player, other_player, outsider, pc):
    client = api(player)
    assert client.patch(f"/api/characters/{pc.pk}/", {"level": 4}).status_code == 200

    base = {"campaign": campaign.pk, "name": "Alt"}
    assert client.post("/api/characters/", {**base, "is_npc": True}).status_code == 400
    assert client.post("/api/characters/", {**base, "owner": other_player.pk}).status_code == 400
    created = client.post("/api/characters/", base)
    assert created.status_code == 201 and created.json()["owner"] == player.pk
    assert api(outsider).post("/api/characters/", base).status_code == 400


def test_npcs_are_dm_only(api, campaign, dm, player, npc):
    assert ids(api(dm).get("/api/npcs/")) == {npc.pk}
    assert api(player).get("/api/npcs/").json() == []
    assert api(player).post("/api/npcs/", {"campaign": campaign.pk, "name": "x"}).status_code == 403

    created = api(dm).post("/api/npcs/", {"campaign": campaign.pk, "name": "Glasstaff"})
    assert created.status_code == 201 and created.json()["is_npc"] is True


def test_npc_generator_is_seeded_and_dm_only(api, campaign, dm, player):
    body = {"campaign": campaign.pk, "seed": "abc"}
    first = api(dm).post("/api/npcs/generate/", body)
    second = api(dm).post("/api/npcs/generate/", body)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["name"]
    assert not Character.objects.filter(is_npc=True).exists()

    saved = api(dm).post("/api/npcs/generate/", {**body, "save": True, "faction": "Redbrands"})
    assert saved.status_code == 201
    assert saved.json()["name"] == first.json()["name"]
    assert saved.json()["faction"] == "Redbrands"

    assert api(player).post("/api/npcs/generate/", body).status_code == 403


# --- Encounters ------------------------------------------------------------


def test_encounters_planned_ones_are_hidden_from_players(api, campaign, dm, player):
    planned = Encounter.objects.create(campaign=campaign, name="Secret boss")
    active = Encounter.objects.create(campaign=campaign, name="Brawl", status="active")

    assert ids(api(dm).get("/api/encounters/")) == {planned.pk, active.pk}
    assert ids(api(player).get("/api/encounters/")) == {active.pk}
    assert (
        api(player).post("/api/encounters/", {"campaign": campaign.pk, "name": "x"}).status_code
        == 403
    )
    assert api(player).patch(f"/api/encounters/{active.pk}/", {"name": "x"}).status_code == 403
    assert api(player).delete(f"/api/encounters/{active.pk}/").status_code == 403
    assert api(player).get(f"/api/encounters/{active.pk}/difficulty/").status_code == 403


def test_add_monster_and_difficulty(api, campaign, dm, pc, other_pc):
    encounter = Encounter.objects.create(campaign=campaign, name="Ambush")
    summary = {"index": "goblin", "name": "Goblin", "cr": 0.25, "xp": 50, "hp": 7, "ac": 15}
    with patch("api.views.client.monster_summary", return_value=summary):
        response = api(dm).post(
            f"/api/encounters/{encounter.pk}/monsters/", {"index": "goblin", "count": 2}
        )
    assert response.status_code == 201
    assert response.json()["monsters"][0]["count"] == 2

    difficulty = api(dm).get(f"/api/encounters/{encounter.pk}/difficulty/").json()
    assert difficulty["adjusted_xp"] == 200
    assert difficulty["difficulty"] == "Easy"


# --- Loot ------------------------------------------------------------------


def test_loot_generation_is_seeded_and_dm_only(api, campaign, dm, player):
    body = {"campaign": campaign.pk, "cr": 5, "seed": "abc"}
    with patch("api.views.client.magic_item_pool", return_value=POOL):
        first = api(dm).post("/api/loot-rolls/generate/", body)
        second = api(dm).post("/api/loot-rolls/generate/", body)
        assert api(player).post("/api/loot-rolls/generate/", body).status_code == 403

    assert first.status_code == 201
    assert first.json()["result"] == second.json()["result"]
    assert LootRoll.objects.count() == 2


def test_players_only_see_revealed_loot(api, campaign, dm, player):
    item = {
        "index": "potion",
        "name": "Potion of Healing",
        "rarity": "common",
        "locked": False,
        "rerolls": 0,
    }
    hidden = LootRoll.objects.create(
        campaign=campaign, seed="a",
        result={"seed": "a", "cr": 1, "coins": {"gp": 5}, "coins_visible": False, "items": [{**item, "visible": False}]},
    )  # fmt: skip
    partial = LootRoll.objects.create(
        campaign=campaign, seed="b",
        result={"seed": "b", "cr": 1, "coins": {"gp": 9}, "coins_visible": False,
                "items": [{**item, "visible": True}, {**item, "index": "x", "name": "Hidden Blade", "visible": False}]},
    )  # fmt: skip

    assert ids(api(dm).get("/api/loot-rolls/")) == {hidden.pk, partial.pk}
    rows = api(player).get("/api/loot-rolls/").json()
    assert [row["id"] for row in rows] == [partial.pk]
    assert [i["name"] for i in rows[0]["result"]["items"]] == ["Potion of Healing"]
    assert rows[0]["result"]["coins"] == {}
    assert api(player).get(f"/api/loot-rolls/{hidden.pk}/").status_code == 404
    assert api(player).delete(f"/api/loot-rolls/{partial.pk}/").status_code == 403


# --- Hooks -----------------------------------------------------------------


def test_hooks_owner_writes_dm_reads_and_links(
    api, campaign, dm, player, other_player, pc, other_pc, npc
):
    created = api(player).post(
        "/api/hooks/", {"character": pc.pk, "title": "Lost brother", "type": "person"}
    )
    assert created.status_code == 201
    hook_id = created.json()["id"]
    assert (
        api(player).post("/api/hooks/", {"character": other_pc.pk, "title": "x"}).status_code == 400
    )
    assert api(dm).post("/api/hooks/", {"character": pc.pk, "title": "x"}).status_code == 400

    # Another player cannot see it; the DM can read but not edit it.
    assert api(other_player).get(f"/api/hooks/{hook_id}/").status_code == 404
    assert api(dm).get(f"/api/hooks/{hook_id}/").status_code == 200
    assert api(dm).patch(f"/api/hooks/{hook_id}/", {"title": "x"}).status_code == 403
    assert api(dm).delete(f"/api/hooks/{hook_id}/").status_code == 403

    # Only the DM links; the unused filter follows.
    assert ids(api(dm).get("/api/hooks/?unused=true")) == {hook_id}
    assert api(player).post(f"/api/hooks/{hook_id}/link/", {"npc": npc.pk}).status_code == 403
    linked = api(dm).post(f"/api/hooks/{hook_id}/link/", {"npc": npc.pk})
    assert linked.status_code == 201 and linked.json()["is_used"] is True
    assert api(dm).get("/api/hooks/?unused=true").json() == []
    assert api(dm).post(f"/api/hooks/{hook_id}/link/", {}).status_code == 400


def test_hook_list_is_scoped_per_user(api, campaign, dm, player, other_player, pc, other_pc):
    mine = Hook.objects.create(backstory=backstory_for(pc), title="Mine")
    theirs = Hook.objects.create(backstory=backstory_for(other_pc), title="Theirs")

    assert ids(api(player).get("/api/hooks/")) == {mine.pk}
    assert ids(api(other_player).get("/api/hooks/")) == {theirs.pk}
    assert ids(api(dm).get(f"/api/hooks/?campaign={campaign.pk}")) == {mine.pk, theirs.pk}
