from django.db import migrations

from npcs.defaults import default_rows


def load_defaults(apps, schema_editor):
    NpcTraitTable = apps.get_model("npcs", "NpcTraitTable")
    NpcTraitTable.objects.bulk_create(
        NpcTraitTable(category=category, race=race, value=value, weight=weight)
        for category, race, value, weight in default_rows()
    )


def remove_defaults(apps, schema_editor):
    apps.get_model("npcs", "NpcTraitTable").objects.filter(campaign__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("npcs", "0001_initial")]

    operations = [migrations.RunPython(load_defaults, remove_defaults)]
