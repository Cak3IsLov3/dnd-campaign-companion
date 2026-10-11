import datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from campaigns.models import GameSession
from encounters.models import Encounter
from vault import services
from vault.models import Hook

pytestmark = pytest.mark.django_db

SECRET_TEXT = "I burned down the family mill."


@pytest.fixture
def backstory(pc):
    backstory = services.backstory_for(pc)
    backstory.text = SECRET_TEXT
    backstory.save()
    return backstory


@pytest.fixture
def hook(backstory):
    return Hook.objects.create(backstory=backstory, title="Old mentor Varric", type="person")


@pytest.fixture
def other_hook(other_pc):
    return Hook.objects.create(
        backstory=services.backstory_for(other_pc), title="The sunken temple", type="place"
    )


# --- Who reads the backstory ----------------------------------------------


def test_dm_cannot_read_an_unshared_backstory_but_sees_its_hooks(
    as_user, campaign, dm, backstory, hook
):
    assert not services.can_read_text(dm, backstory)

    html = as_user(dm).get(reverse("vault:home", args=[campaign.pk])).content.decode()
    assert SECRET_TEXT not in html
    assert hook.title in html


def test_dm_reads_the_backstory_once_the_player_shares_it(as_user, campaign, dm, backstory):
    backstory.is_visible_to_dm = True
    backstory.save()

    assert services.can_read_text(dm, backstory)
    html = as_user(dm).get(reverse("vault:home", args=[campaign.pk])).content.decode()
    assert SECRET_TEXT in html


def test_player_reads_and_edits_their_own_backstory(as_user, campaign, player, pc, backstory):
    client = as_user(player)
    url = reverse("vault:backstory", args=[campaign.pk, pc.pk])

    assert SECRET_TEXT in client.get(url).content.decode()
    client.post(url, {"text": "A new past.", "is_visible_to_dm": "on"})
    backstory.refresh_from_db()
    assert backstory.text == "A new past."
    assert backstory.is_visible_to_dm


def test_nobody_else_can_open_a_backstory(as_user, campaign, dm, other_player, pc, backstory):
    url = reverse("vault:backstory", args=[campaign.pk, pc.pk])
    backstory.is_visible_to_dm = True  # sharing grants the DM read access, never edit access
    backstory.save()

    for user in (other_player, dm):
        client = as_user(user)
        assert client.get(url).status_code == 403
        assert client.post(url, {"text": "defaced"}).status_code == 403
    backstory.refresh_from_db()
    assert backstory.text == SECRET_TEXT


def test_player_vault_lists_only_their_own_characters(
    as_user, campaign, player, pc, other_pc, other_hook
):
    html = as_user(player).get(reverse("vault:home", args=[campaign.pk])).content.decode()
    assert pc.name in html
    assert other_pc.name not in html
    assert other_hook.title not in html


def test_player_adds_hooks_only_to_their_own_character(as_user, campaign, player, pc, other_pc):
    client = as_user(player)
    data = {"title": "The lighthouse", "type": "place", "description": ""}

    client.post(reverse("vault:hook_add", args=[campaign.pk, pc.pk]), data)
    assert Hook.objects.filter(backstory__character=pc, title="The lighthouse").exists()

    response = client.post(reverse("vault:hook_add", args=[campaign.pk, other_pc.pk]), data)
    assert response.status_code == 403
    assert not Hook.objects.filter(backstory__character=other_pc).exists()


# --- Linking hooks and the unused filter ----------------------------------


def test_unused_hooks_shrinks_as_hooks_get_linked(campaign, npc, hook, other_hook):
    assert set(services.unused_hooks(campaign)) == {hook, other_hook}

    services.link_hook(hook, npc=npc)
    assert list(services.unused_hooks(campaign)) == [other_hook]

    session = GameSession.objects.create(
        campaign=campaign, number=1, date=datetime.date(2026, 1, 1)
    )
    services.link_hook(other_hook, session=session)
    assert not services.unused_hooks(campaign).exists()


def test_linking_a_hook_twice_does_not_duplicate_it_in_any_list(campaign, npc, hook, other_hook):
    encounter = Encounter.objects.create(campaign=campaign, name="Ambush")
    services.link_hook(hook, npc=npc)
    services.link_hook(hook, encounter=encounter)

    assert hook.links.count() == 2
    assert list(services.unused_hooks(campaign)) == [other_hook]


def test_removing_the_last_link_makes_a_hook_unused_again(campaign, npc, hook):
    link = services.link_hook(hook, npc=npc)
    link.delete()
    assert list(services.unused_hooks(campaign)) == [hook]


def test_a_link_needs_exactly_one_target_from_the_same_campaign(campaign, dm, npc, pc, hook):
    from campaigns.models import Character
    from campaigns.services import create_campaign

    with pytest.raises(ValidationError):
        services.link_hook(hook)
    with pytest.raises(ValidationError):
        services.link_hook(
            hook, npc=npc, encounter=Encounter.objects.create(campaign=campaign, name="x")
        )
    with pytest.raises(ValidationError):
        services.link_hook(hook, npc=pc)  # a player character is not an NPC
    foreign_npc = Character.objects.create(
        campaign=create_campaign(dm, "Other"), name="Z", is_npc=True
    )
    with pytest.raises(ValidationError):
        services.link_hook(hook, npc=foreign_npc)
    assert not hook.links.exists()


def test_only_the_dm_links_hooks_in_the_web_app(as_user, campaign, dm, player, npc, hook):
    url = reverse("vault:hook_link", args=[campaign.pk, hook.pk])
    data = {"target": f"npc:{npc.pk}"}

    assert as_user(player).post(url, data).status_code == 403
    assert not hook.links.exists()

    as_user(dm).post(url, data)
    assert hook.links.get().npc == npc
