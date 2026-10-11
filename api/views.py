"""REST API. Querysets and write checks reuse the same access rules as the web app."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from campaigns import access
from campaigns import services as campaign_services
from campaigns.models import Campaign, Character
from campaigns.services import party_levels
from encounters.models import Encounter, EncounterMonster
from encounters.selectors import encounter_difficulty, total_cr, visible_encounters
from loot import services as loot_services
from loot.models import LootRoll
from loot.selectors import visible_rolls, weights_for
from npcs import services as npc_services
from srd import client
from vault import services as vault_services
from vault.models import Hook
from vault.services import backstory_for

from . import serializers as s

CAMPAIGN_PARAM = OpenApiParameter("campaign", int, description="Filter by campaign id.")


def require_dm(user, campaign):
    if not access.is_dm(user, campaign):
        raise PermissionDenied("Only the DM of this campaign can do that.")


class CampaignFilterMixin:
    """Optional ?campaign=<id> filter for campaign-scoped resources."""

    def filter_campaign(self, queryset, field="campaign"):
        campaign_id = self.request.query_params.get("campaign")
        return queryset.filter(**{field: campaign_id}) if campaign_id else queryset


class CampaignViewSet(viewsets.ModelViewSet):
    serializer_class = s.CampaignSerializer
    queryset = Campaign.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        return access.campaigns_for(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = campaign_services.create_campaign(
            self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer):
        require_dm(self.request.user, serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        require_dm(self.request.user, instance)
        instance.delete()

    @extend_schema(request=s.JoinSerializer, responses=s.CampaignSerializer)
    @action(detail=False, methods=["post"])
    def join(self, request):
        """Join a campaign as a player with its invite code."""
        data = s.JoinSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            campaign = campaign_services.join_campaign(
                request.user, data.validated_data["invite_code"]
            )
        except campaign_services.InvalidInviteCode as exc:
            raise ValidationError({"invite_code": str(exc)}) from exc
        return Response(self.get_serializer(campaign).data)


@extend_schema_view(list=extend_schema(parameters=[CAMPAIGN_PARAM]))
class CharacterViewSet(CampaignFilterMixin, viewsets.ModelViewSet):
    """Player characters and NPCs. Players only ever see their own character."""

    serializer_class = s.CharacterSerializer
    queryset = Character.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        return self.filter_campaign(access.visible_characters(self.request.user))


@extend_schema_view(list=extend_schema(parameters=[CAMPAIGN_PARAM]))
class NpcViewSet(CampaignFilterMixin, viewsets.ModelViewSet):
    """NPCs, including the random generator. DM only."""

    serializer_class = s.NpcSerializer
    queryset = Character.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        npcs = Character.objects.filter(
            is_npc=True, campaign__in=access.dm_campaigns_for(self.request.user)
        )
        return self.filter_campaign(npcs)

    def perform_create(self, serializer):
        require_dm(self.request.user, serializer.validated_data["campaign"])
        serializer.save(is_npc=True, owner=None)

    @extend_schema(request=s.GenerateNpcSerializer, responses={200: dict, 201: s.NpcSerializer})
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Roll a random NPC. Pass a seed to reproduce it and save=true to keep it."""
        data = s.GenerateNpcSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        campaign = data.validated_data["campaign"]
        require_dm(request.user, campaign)
        npc = npc_services.generate_npc(
            npc_services.tables_for(campaign), data.validated_data.get("seed")
        )
        if not data.validated_data["save"]:
            return Response({field: npc[field] for field in ["seed", *npc_services.FIELDS]})
        character = npc_services.save_as_character(
            npc, campaign, data.validated_data["location"], data.validated_data["faction"]
        )
        return Response(self.get_serializer(character).data, status=status.HTTP_201_CREATED)


@extend_schema_view(list=extend_schema(parameters=[CAMPAIGN_PARAM]))
class EncounterViewSet(CampaignFilterMixin, viewsets.ModelViewSet):
    """Encounters. Players get read-only access to active and finished ones."""

    serializer_class = s.EncounterSerializer
    queryset = Encounter.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        return self.filter_campaign(visible_encounters(self.request.user))

    def perform_create(self, serializer):
        require_dm(self.request.user, serializer.validated_data["campaign"])
        serializer.save()

    def perform_update(self, serializer):
        require_dm(self.request.user, serializer.instance.campaign)
        if (
            serializer.validated_data.get("campaign", serializer.instance.campaign)
            != serializer.instance.campaign
        ):
            raise ValidationError("An encounter cannot move to another campaign.")
        serializer.save()

    def perform_destroy(self, instance):
        require_dm(self.request.user, instance.campaign)
        instance.delete()

    @extend_schema(request=s.AddMonsterSerializer, responses=s.EncounterSerializer)
    @action(detail=True, methods=["post"], url_path="monsters")
    def add_monster(self, request, pk=None):
        """Add an SRD monster to the encounter."""
        encounter = self.get_object()
        require_dm(request.user, encounter.campaign)
        data = s.AddMonsterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            summary = client.monster_summary(data.validated_data["index"])
        except client.SRDError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        monster, created = EncounterMonster.objects.get_or_create(
            encounter=encounter,
            monster_index=summary["index"],
            defaults={
                **{k: summary[k] for k in ["name", "cr", "xp", "hp", "ac"]},
                "count": data.validated_data["count"],
            },
        )
        if not created:
            monster.count += data.validated_data["count"]
            monster.save(update_fields=["count"])
        return Response(self.get_serializer(encounter).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=s.DifficultySerializer)
    @action(detail=True, methods=["get"])
    def difficulty(self, request, pk=None):
        """Difficulty of the encounter for the campaign's current party."""
        encounter = self.get_object()
        require_dm(request.user, encounter.campaign)
        return Response(s.DifficultySerializer(encounter_difficulty(encounter)).data)


@extend_schema_view(list=extend_schema(parameters=[CAMPAIGN_PARAM]))
class LootRollViewSet(
    CampaignFilterMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Saved loot rolls. Players only see the coins and items the DM revealed."""

    serializer_class = s.LootRollSerializer
    queryset = LootRoll.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        return self.filter_campaign(visible_rolls(self.request.user))

    def perform_destroy(self, instance):
        require_dm(self.request.user, instance.campaign)
        instance.delete()

    @extend_schema(request=s.GenerateLootSerializer, responses={201: s.LootRollSerializer})
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Roll loot and save it. CR defaults to the encounter's total CR or the party level."""
        data = s.GenerateLootSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        campaign = data.validated_data["campaign"]
        encounter = data.validated_data.get("encounter")
        require_dm(request.user, campaign)
        if encounter and encounter.campaign != campaign:
            raise ValidationError({"encounter": "This encounter belongs to another campaign."})
        cr = data.validated_data.get("cr")
        if cr is None:
            levels = party_levels(campaign)
            cr = total_cr(encounter) if encounter else (sum(levels) / len(levels) if levels else 1)
        result = loot_services.generate_loot(
            cr, client.magic_item_pool(), weights_for(campaign), data.validated_data.get("seed")
        )
        roll = LootRoll.objects.create(
            campaign=campaign, encounter=encounter, seed=result["seed"], result=result
        )
        return Response(self.get_serializer(roll).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            CAMPAIGN_PARAM,
            OpenApiParameter("unused", bool, description="Only hooks without links."),
        ]
    )
)
class HookViewSet(CampaignFilterMixin, viewsets.ModelViewSet):
    """Backstory hooks. Players manage their own; the DM reads and links them."""

    serializer_class = s.HookSerializer
    queryset = Hook.objects.none()  # for schema generation; see get_queryset

    def get_queryset(self):
        hooks = self.filter_campaign(
            vault_services.visible_hooks(self.request.user), "backstory__character__campaign"
        )
        if self.request.query_params.get("unused", "").lower() in ("1", "true"):
            hooks = hooks.filter(links__isnull=True)
        return hooks

    def _require_owner(self, hook):
        if hook.backstory.character.owner_id != self.request.user.id:
            raise PermissionDenied("Only the player who owns this character can change its hooks.")

    def perform_create(self, serializer):
        character = serializer.validated_data.pop("backstory")["character"]
        serializer.save(backstory=backstory_for(character))

    def perform_update(self, serializer):
        self._require_owner(serializer.instance)
        character = serializer.validated_data.pop("backstory", {}).get("character")
        if character and character != serializer.instance.backstory.character:
            raise ValidationError({"character": "A hook cannot move to another character."})
        serializer.save()

    def perform_destroy(self, instance):
        self._require_owner(instance)
        instance.delete()

    @extend_schema(request=s.HookLinkSerializer, responses={201: s.HookSerializer})
    @action(detail=True, methods=["post"])
    def link(self, request, pk=None):
        """DM only: mark the hook as used by linking it to an NPC, session or encounter."""
        hook = self.get_object()
        require_dm(request.user, hook.backstory.character.campaign)
        data = s.HookLinkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            vault_services.link_hook(hook, **data.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(self.get_serializer(hook).data, status=status.HTTP_201_CREATED)
