import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from campaigns.models import Campaign, Character, GameSession
from campaigns.services import create_campaign, join_campaign
from encounters.models import Encounter, EncounterMonster
from vault.models import Hook
from vault.services import backstory_for

DEMO_PASSWORD = "demo-pass-123"
CAMPAIGN_NAME = "Lost Mine of Phandelver (demo)"


class Command(BaseCommand):
    help = "Create a demo campaign with a DM (demo_dm) and two players (demo_ana, demo_ben)."

    def handle(self, *args, **options):
        User = get_user_model()
        users = {}
        for name in ["demo_dm", "demo_ana", "demo_ben"]:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[name] = user
        if Campaign.objects.filter(name=CAMPAIGN_NAME).exists():
            self.stdout.write("Demo campaign already exists.")
            return

        campaign = create_campaign(
            users["demo_dm"], CAMPAIGN_NAME, "A classic starter adventure on the Sword Coast."
        )
        join_campaign(users["demo_ana"], campaign.invite_code)
        join_campaign(users["demo_ben"], campaign.invite_code)

        def character(**fields):
            return Character.objects.create(campaign=campaign, **fields)

        lia = character(owner=users["demo_ana"], name="Lia Amastacia", race="Elf",
                        char_class="Wizard", level=3, max_hp=18, ac=12)  # fmt: skip
        borin = character(owner=users["demo_ben"], name="Borin Ironfist", race="Dwarf",
                          char_class="Fighter", level=3, max_hp=31, ac=18)  # fmt: skip
        character(name="Sildar Hallwinter", race="Human", char_class="Retired soldier",
                  is_npc=True, location="Phandalin", faction="Lords' Alliance")  # fmt: skip

        GameSession.objects.create(
            campaign=campaign, number=1, date=datetime.date(2026, 9, 27),
            notes="The party escorted a wagon and was ambushed by goblins on the Triboar Trail.",
            is_visible_to_players=True,
        )  # fmt: skip
        GameSession.objects.create(
            campaign=campaign, number=2, date=datetime.date(2026, 10, 4),
            notes="DM prep: Glasstaff is really Iarno Albrek. Do not reveal yet.",
        )  # fmt: skip

        ambush = Encounter.objects.create(campaign=campaign, name="Goblin ambush")
        EncounterMonster.objects.create(encounter=ambush, monster_index="goblin", name="Goblin",
                                        count=4, cr=0.25, xp=50, hp=7, ac=15)  # fmt: skip

        backstory = backstory_for(lia)
        backstory.text = "Lia left the academy in disgrace after a forbidden experiment."
        backstory.save()
        Hook.objects.create(backstory=backstory, title="Master Elowen", type="person",
                            description="The mentor who covered for her.")  # fmt: skip
        Hook.objects.create(backstory=backstory, title="The sealed laboratory", type="place",
                            description="Still locked beneath the academy.")  # fmt: skip
        Hook.objects.create(backstory=backstory_for(borin), title="The fall of Clan Ironfist",
                            type="event", description="Orcs took the hold twenty years ago.")  # fmt: skip

        self.stdout.write(self.style.SUCCESS(f"Created '{CAMPAIGN_NAME}'. Log in as demo_dm."))
