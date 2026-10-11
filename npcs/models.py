from django.db import models

from campaigns.models import Campaign


class NpcTraitTable(models.Model):
    """One weighted row of an NPC generator table.

    Rows without a campaign are the shared defaults. A campaign row with the
    same category, race and value overrides the default's weight (0 disables it).
    """

    class Category(models.TextChoices):
        NAME = "name", "Name"
        OCCUPATION = "occupation", "Occupation"
        TRAIT = "trait", "Trait"
        SECRET = "secret", "Secret"
        MOTIVATION = "motivation", "Motivation"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, null=True, blank=True, related_name="npc_traits"
    )
    category = models.CharField(max_length=12, choices=Category.choices)
    race = models.CharField(max_length=60, blank=True, help_text="Required for names.")
    value = models.CharField(max_length=200)
    weight = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["category", "race", "value"]
        verbose_name = "NPC trait"

    def __str__(self):
        return f"{self.category}: {self.value}"
