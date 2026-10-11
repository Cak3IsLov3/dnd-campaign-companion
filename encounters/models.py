from django.db import models

from campaigns.models import Campaign, Character


class Encounter(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        DONE = "done", "Done"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="encounters")
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    round = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class EncounterMonster(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="monsters")
    monster_index = models.CharField(max_length=120)  # SRD index, e.g. "goblin"
    name = models.CharField(max_length=120)
    count = models.PositiveSmallIntegerField(default=1)
    cr = models.DecimalField(max_digits=5, decimal_places=3, default=0)
    xp = models.PositiveIntegerField(default=0)  # per monster
    hp = models.PositiveIntegerField(default=1)
    ac = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.count}x {self.name}"

    @property
    def cr_display(self):
        """CR without trailing zeros: 0.25, 1, 10."""
        return f"{self.cr.normalize():f}"


class Combatant(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="combatants")
    character = models.ForeignKey(
        Character, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    name = models.CharField(max_length=120)
    initiative = models.IntegerField(default=0)
    hp = models.IntegerField(default=1)
    max_hp = models.PositiveIntegerField(default=1)
    ac = models.PositiveSmallIntegerField(default=10)
    conditions = models.JSONField(default=list, blank=True)
    is_active_turn = models.BooleanField(default=False)

    class Meta:
        # Highest initiative first; id keeps ties stable.
        ordering = ["-initiative", "id"]

    def __str__(self):
        return self.name
