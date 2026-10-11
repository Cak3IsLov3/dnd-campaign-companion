"""Role-based access in the web app: what players can and cannot see or change."""

import datetime

import pytest
from django.urls import reverse

from campaigns.models import Campaign, Character, GameSession, Membership
from campaigns.services import InvalidInviteCode, join_campaign
from encounters.models import Encounter
from loot.models import LootRoll

pytestmark = pytest.mark.django_db


@pytest.fixture
def hidden_session(campaign):
    return GameSession.objects.create(
        campaign=campaign, number=1, date=datetime.date(2026, 1, 1), notes="The butler did it."
    )


@pytest.fixture
def public_session(campaign):
    return GameSession.objects.create(
        campaign=campaign,
        number=2,
        date=datetime.date(2026, 1, 8),
        notes="You met in a tavern.",
        is_visible_to_players=True,
    )


# --- Accounts, campaigns, invite codes -------------------------------------


def test_register_logs_in_and_redirects(client):
    response = client.post(
        reverse("register"),
        {
            "username": "newbie",
            "password1": "s3cret-pass-phrase",
            "password2": "s3cret-pass-phrase",
        },
    )
    assert response.status_code == 302
    assert client.get(reverse("campaigns:list")).status_code == 200


def test_anonymous_users_are_sent_to_login(client, campaign):
    response = client.get(reverse("campaigns:detail", args=[campaign.pk]))
    assert response.status_code == 302
    assert reverse("login") in response.url


def test_creating_a_campaign_makes_you_dm_with_an_invite_code(as_user, dm):
    as_user(dm).post(reverse("campaigns:create"), {"name": "Curse of Strahd"})
    campaign = Campaign.objects.get(name="Curse of Strahd")
    assert campaign.invite_code
    assert Membership.objects.get(campaign=campaign, user=dm).role == Membership.Role.DM


def test_joining_with_an_invite_code_makes_you_a_player(as_user, campaign, outsider):
    as_user(outsider).post(reverse("campaigns:join"), {"invite_code": campaign.invite_code})
    assert Membership.objects.get(campaign=campaign, user=outsider).role == Membership.Role.PLAYER


def test_joining_twice_keeps_one_membership_and_the_dm_stays_dm(campaign, dm, player):
    join_campaign(player, campaign.invite_code)
    join_campaign(dm, campaign.invite_code)
    assert Membership.objects.filter(campaign=campaign, user=player).count() == 1
    assert Membership.objects.get(campaign=campaign, user=dm).role == Membership.Role.DM


def test_invalid_invite_code_is_rejected(outsider):
    with pytest.raises(InvalidInviteCode):
        join_campaign(outsider, "nope")


def test_non_member_gets_404(as_user, campaign, outsider):
    assert as_user(outsider).get(reverse("campaigns:detail", args=[campaign.pk])).status_code == 404


def test_only_the_dm_sees_the_invite_code(as_user, campaign, dm, player):
    url = reverse("campaigns:detail", args=[campaign.pk])
    assert campaign.invite_code in as_user(dm).get(url).content.decode()
    assert campaign.invite_code not in as_user(player).get(url).content.decode()


# --- Characters ------------------------------------------------------------


def test_player_sees_only_their_own_character(as_user, campaign, player, pc, other_pc, npc):
    html = as_user(player).get(reverse("campaigns:detail", args=[campaign.pk])).content.decode()
    assert pc.name in html
    assert other_pc.name not in html
    assert npc.name not in html


def test_dm_sees_all_characters(as_user, campaign, dm, pc, other_pc, npc):
    html = as_user(dm).get(reverse("campaigns:detail", args=[campaign.pk])).content.decode()
    assert all(name in html for name in [pc.name, other_pc.name, npc.name])


def test_player_can_edit_own_character_but_not_others(as_user, campaign, player, pc, other_pc, npc):
    client = as_user(player)
    data = {"name": "Renamed", "level": 4, "max_hp": 20, "ac": 14}

    assert (
        client.post(
            reverse("campaigns:character_edit", args=[campaign.pk, pc.pk]), data
        ).status_code
        == 302
    )
    pc.refresh_from_db()
    assert pc.name == "Renamed"

    for target in (other_pc, npc):
        url = reverse("campaigns:character_edit", args=[campaign.pk, target.pk])
        assert client.post(url, data).status_code == 403
        url = reverse("campaigns:character_delete", args=[campaign.pk, target.pk])
        assert client.post(url).status_code == 403
    assert Character.objects.filter(pk__in=[other_pc.pk, npc.pk]).count() == 2


def test_player_cannot_create_an_npc_or_a_character_for_someone_else(
    as_user, campaign, player, other_player
):
    as_user(player).post(
        reverse("campaigns:character_create", args=[campaign.pk]),
        {
            "name": "Sneaky",
            "level": 1,
            "max_hp": 8,
            "ac": 12,
            "is_npc": "on",
            "owner": other_player.pk,
        },
    )
    character = Character.objects.get(name="Sneaky")
    assert character.owner == player
    assert not character.is_npc


# --- Session log -----------------------------------------------------------


def test_player_sees_only_released_sessions(
    as_user, campaign, player, hidden_session, public_session
):
    client = as_user(player)
    html = client.get(reverse("campaigns:detail", args=[campaign.pk])).content.decode()
    assert "Session 2" in html and "Session 1" not in html

    url = reverse("campaigns:session_detail", args=[campaign.pk, public_session.pk])
    assert "You met in a tavern." in client.get(url).content.decode()
    url = reverse("campaigns:session_detail", args=[campaign.pk, hidden_session.pk])
    assert client.get(url).status_code == 404


def test_visibility_toggle_is_dm_only(as_user, campaign, dm, player, hidden_session):
    url = reverse("campaigns:session_visibility", args=[campaign.pk, hidden_session.pk])

    assert as_user(player).post(url).status_code == 403
    hidden_session.refresh_from_db()
    assert not hidden_session.is_visible_to_players

    assert as_user(dm).post(url).status_code == 200
    hidden_session.refresh_from_db()
    assert hidden_session.is_visible_to_players


def test_player_cannot_create_or_edit_sessions(as_user, campaign, player, public_session):
    client = as_user(player)
    data = {"number": 9, "date": "2026-02-01", "notes": "hax"}
    assert (
        client.post(reverse("campaigns:session_create", args=[campaign.pk]), data).status_code
        == 403
    )
    url = reverse("campaigns:session_edit", args=[campaign.pk, public_session.pk])
    assert client.post(url, data).status_code == 403
    assert not GameSession.objects.filter(number=9).exists()


# --- DM-only tools ---------------------------------------------------------


@pytest.mark.parametrize("name", ["loot:generator", "npcs:generator", "npcs:tables"])
def test_dm_tools_are_forbidden_for_players(as_user, campaign, dm, player, name):
    url = reverse(name, args=[campaign.pk])
    assert as_user(player).get(url).status_code == 403
    assert as_user(dm).get(url).status_code == 200


def test_player_cannot_use_the_encounter_builder(as_user, campaign, player):
    encounter = Encounter.objects.create(campaign=campaign, name="Ambush")
    client = as_user(player)
    assert (
        client.post(reverse("encounters:create", args=[campaign.pk]), {"name": "x"}).status_code
        == 403
    )
    assert (
        client.get(reverse("encounters:detail", args=[campaign.pk, encounter.pk])).status_code
        == 403
    )
    # A planned encounter is invisible to players, tracker included.
    assert (
        client.get(reverse("encounters:tracker", args=[campaign.pk, encounter.pk])).status_code
        == 404
    )


def test_player_sees_only_revealed_loot_in_the_session_log(
    as_user, campaign, dm, player, public_session
):
    LootRoll.objects.create(
        campaign=campaign,
        session=public_session,
        seed="s",
        result={
            "seed": "s", "cr": 3, "coins": {"cp": 1, "sp": 2, "gp": 333}, "coins_visible": False,
            "items": [
                {"index": "a", "name": "Cloak of Secrets", "rarity": "rare", "locked": False, "visible": False, "rerolls": 0},
                {"index": "b", "name": "Bag of Holding", "rarity": "uncommon", "locked": False, "visible": True, "rerolls": 0},
            ],
        },
    )  # fmt: skip
    url = reverse("campaigns:session_detail", args=[campaign.pk, public_session.pk])

    player_html = as_user(player).get(url).content.decode()
    assert "Bag of Holding" in player_html
    assert "Cloak of Secrets" not in player_html
    assert "333 gp" not in player_html

    dm_html = as_user(dm).get(url).content.decode()
    assert "Cloak of Secrets" in dm_html and "333 gp" in dm_html
