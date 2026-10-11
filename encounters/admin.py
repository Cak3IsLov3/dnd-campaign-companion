from django.contrib import admin

from . import models

admin.site.register(models.Encounter)
admin.site.register(models.EncounterMonster)
admin.site.register(models.Combatant)
