from rest_framework import serializers

from campaigns.access import is_dm, role_in
from campaigns.models import Campaign, Character
from encounters.models import Combatant, Encounter, EncounterMonster
from loot.models import LootRoll
from loot.selectors import result_for
from vault.models import Hook, HookLink


class CampaignSerializer(serializers.ModelSerializer):
    dm = serializers.StringRelatedField()
    role = serializers.SerializerMethodField()
    invite_code = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = ["id", "name", "description", "dm", "role", "invite_code", "created_at"]

    def get_role(self, campaign) -> str:
        return role_in(self.context["request"].user, campaign)

    def get_invite_code(self, campaign) -> str | None:
        # Only the DM hands out invites.
        return campaign.invite_code if is_dm(self.context["request"].user, campaign) else None


class JoinSerializer(serializers.Serializer):
    invite_code = serializers.CharField()


class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = [
            "id", "campaign", "owner", "name", "race", "char_class", "level", "max_hp", "ac",
            "is_npc", "location", "faction", "notes",
        ]  # fmt: skip

    def validate(self, attrs):
        user = self.context["request"].user
        campaign = attrs.get("campaign") or self.instance.campaign
        if self.instance and campaign != self.instance.campaign:
            raise serializers.ValidationError("A character cannot move to another campaign.")
        role = role_in(user, campaign)
        if role is None:
            raise serializers.ValidationError("You are not a member of this campaign.")
        if not is_dm(user, campaign):
            # Players manage only their own player character.
            if attrs.get("is_npc") or attrs.get("owner") not in (None, user):
                raise serializers.ValidationError("Players can only manage their own character.")
            attrs["owner"] = user
            attrs["is_npc"] = False
        return attrs


class NpcSerializer(CharacterSerializer):
    class Meta(CharacterSerializer.Meta):
        read_only_fields = ["owner", "is_npc"]


class GenerateNpcSerializer(serializers.Serializer):
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    seed = serializers.CharField(required=False, allow_blank=True)
    save = serializers.BooleanField(default=False)
    location = serializers.CharField(required=False, allow_blank=True, default="")
    faction = serializers.CharField(required=False, allow_blank=True, default="")


class EncounterMonsterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncounterMonster
        fields = ["id", "monster_index", "name", "count", "cr", "xp", "hp", "ac"]


class CombatantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combatant
        fields = ["id", "name", "initiative", "hp", "max_hp", "ac", "conditions", "is_active_turn"]


class EncounterSerializer(serializers.ModelSerializer):
    monsters = serializers.SerializerMethodField()
    combatants = CombatantSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = ["id", "campaign", "name", "status", "round", "monsters", "combatants"]
        read_only_fields = ["round"]

    def get_monsters(self, encounter) -> list:
        # The monster roster is prep material: DM only.
        if not is_dm(self.context["request"].user, encounter.campaign):
            return []
        return EncounterMonsterSerializer(encounter.monsters.all(), many=True).data


class AddMonsterSerializer(serializers.Serializer):
    index = serializers.CharField(help_text='SRD monster index, e.g. "goblin".')
    count = serializers.IntegerField(min_value=1, default=1)


class DifficultySerializer(serializers.Serializer):
    difficulty = serializers.CharField()
    total_xp = serializers.IntegerField()
    adjusted_xp = serializers.IntegerField()
    multiplier = serializers.FloatField()
    thresholds = serializers.DictField(child=serializers.IntegerField())


class LootRollSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField()

    class Meta:
        model = LootRoll
        fields = ["id", "campaign", "encounter", "session", "seed", "result", "created_at"]

    def get_result(self, roll) -> dict:
        return result_for(self.context["request"].user, roll)


class GenerateLootSerializer(serializers.Serializer):
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    encounter = serializers.PrimaryKeyRelatedField(
        queryset=Encounter.objects.all(), required=False, allow_null=True
    )
    cr = serializers.FloatField(min_value=0, required=False)
    seed = serializers.CharField(required=False, allow_blank=True)


class HookLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = HookLink
        fields = ["id", "npc", "session", "encounter", "date_used"]
        extra_kwargs = {"date_used": {"required": False}}


class HookSerializer(serializers.ModelSerializer):
    character = serializers.PrimaryKeyRelatedField(
        source="backstory.character", queryset=Character.objects.filter(is_npc=False)
    )
    links = HookLinkSerializer(many=True, read_only=True)
    is_used = serializers.SerializerMethodField()

    class Meta:
        model = Hook
        fields = ["id", "character", "title", "type", "description", "links", "is_used"]

    def get_is_used(self, hook) -> bool:
        return hook.links.exists()

    def validate_character(self, character):
        if character.owner != self.context["request"].user:
            raise serializers.ValidationError("You can only add hooks to your own character.")
        return character
