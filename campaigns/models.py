import secrets

from django.conf import settings
from django.db import models


def generate_invite_code():
    return secrets.token_urlsafe(6)


class Campaign(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    dm = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dm_campaigns"
    )
    invite_code = models.CharField(max_length=16, unique=True, default=generate_invite_code)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        DM = "DM", "Dungeon Master"
        PLAYER = "PLAYER", "Player"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PLAYER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "campaign"], name="unique_membership")
        ]

    def __str__(self):
        return f"{self.user} in {self.campaign} ({self.role})"


class Character(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="characters")
    # NPCs have no owner; player characters belong to the player who plays them.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="characters",
    )
    name = models.CharField(max_length=120)
    race = models.CharField(max_length=60, blank=True)
    char_class = models.CharField("class / occupation", max_length=60, blank=True)
    level = models.PositiveSmallIntegerField(default=1)
    max_hp = models.PositiveIntegerField(default=10)
    ac = models.PositiveSmallIntegerField(default=10)
    is_npc = models.BooleanField(default=False)
    location = models.CharField(max_length=120, blank=True)
    faction = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["is_npc", "name"]

    def __str__(self):
        return self.name


class GameSession(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="sessions")
    number = models.PositiveIntegerField()
    date = models.DateField()
    notes = models.TextField(blank=True)
    is_visible_to_players = models.BooleanField(default=False)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "number"], name="unique_session_number")
        ]

    def __str__(self):
        return f"Session {self.number}"
