from django.contrib import admin

from . import models

admin.site.register(models.Backstory)
admin.site.register(models.Hook)
admin.site.register(models.HookLink)
