from django.core.management.base import BaseCommand, CommandError

from srd import client


class Command(BaseCommand):
    help = "Cache the SRD monster list and all magic item details."

    def handle(self, *args, **options):
        try:
            monsters = len(client.get(client.MONSTERS).get("results", []))
            items = client.sync_magic_items()
        except client.SRDError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(f"{monsters} monsters listed, {items} new magic items cached.")
        )
