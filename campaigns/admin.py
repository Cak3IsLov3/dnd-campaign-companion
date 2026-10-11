from django.contrib import admin

from . import models

admin.site.register(models.Campaign)
admin.site.register(models.Membership)
admin.site.register(models.Character)
admin.site.register(models.GameSession)
