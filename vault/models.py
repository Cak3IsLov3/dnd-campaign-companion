from django.db import models

from campaigns.models import Character, GameSession
from encounters.models import Encounter


class Backstory(models.Model):
    character = models.OneToOneField(Character, on_delete=models.CASCADE, related_name="backstory")
    text = models.TextField(blank=True)
    # The player decides whether the DM reads the full text or only the hooks.
    is_visible_to_dm = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "backstories"

    def __str__(self):
        return f"Backstory of {self.character}"


class Hook(models.Model):
    class Type(models.TextChoices):
        PERSON = "person", "Person"
        PLACE = "place", "Place"
        EVENT = "event", "Event"

    backstory = models.ForeignKey(Backstory, on_delete=models.CASCADE, related_name="hooks")
    title = models.CharField(max_length=120)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.PERSON)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class HookLink(models.Model):
    """Records that the DM used a hook, tied to an NPC, a session or an encounter."""

    hook = models.ForeignKey(Hook, on_delete=models.CASCADE, related_name="links")
    npc = models.ForeignKey(
        Character, on_delete=models.CASCADE, null=True, blank=True, related_name="hook_links"
    )
    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, null=True, blank=True, related_name="hook_links"
    )
    encounter = models.ForeignKey(
        Encounter, on_delete=models.CASCADE, null=True, blank=True, related_name="hook_links"
    )
    date_used = models.DateField()

    class Meta:
        ordering = ["-date_used"]

    @property
    def target(self):
        return self.npc or self.session or self.encounter

    def __str__(self):
        return f"{self.hook} -> {self.target}"
