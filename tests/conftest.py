import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from campaigns.models import Character
from campaigns.services import create_campaign, join_campaign

User = get_user_model()


@pytest.fixture
def dm(db):
    return User.objects.create_user("dm", password="pw")


@pytest.fixture
def player(db):
    return User.objects.create_user("player", password="pw")


@pytest.fixture
def other_player(db):
    return User.objects.create_user("other", password="pw")


@pytest.fixture
def outsider(db):
    return User.objects.create_user("outsider", password="pw")


@pytest.fixture
def campaign(dm, player, other_player):
    campaign = create_campaign(dm, "Lost Mine")
    join_campaign(player, campaign.invite_code)
    join_campaign(other_player, campaign.invite_code)
    return campaign


@pytest.fixture
def pc(campaign, player):
    return Character.objects.create(campaign=campaign, owner=player, name="Tharivol", level=3)


@pytest.fixture
def other_pc(campaign, other_player):
    return Character.objects.create(campaign=campaign, owner=other_player, name="Brakka", level=3)


@pytest.fixture
def npc(campaign):
    return Character.objects.create(campaign=campaign, name="Sildar", is_npc=True)


@pytest.fixture
def as_user(client):
    """Log the Django test client in as the given user."""

    def login(user):
        client.force_login(user)
        return client

    return login


@pytest.fixture
def api():
    """An API client authenticated as the given user."""

    def make(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return make
