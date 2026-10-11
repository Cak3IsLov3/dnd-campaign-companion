from django import forms
from django.contrib.auth import get_user_model

from .models import Campaign, Character, GameSession, Membership


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "description"]


class JoinForm(forms.Form):
    invite_code = forms.CharField(max_length=16)


class CharacterForm(forms.ModelForm):
    """Character form. Only the DM may assign an owner or create NPCs."""

    class Meta:
        model = Character
        fields = [
            "name", "race", "char_class", "level", "max_hp", "ac",
            "owner", "is_npc", "location", "faction", "notes",
        ]  # fmt: skip

    def __init__(self, *args, campaign, is_dm, **kwargs):
        super().__init__(*args, **kwargs)
        if is_dm:
            self.fields["owner"].queryset = get_user_model().objects.filter(
                memberships__campaign=campaign, memberships__role=Membership.Role.PLAYER
            )
        else:
            for name in ["owner", "is_npc", "location", "faction"]:
                del self.fields[name]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_npc"):
            cleaned["owner"] = None
        return cleaned


class GameSessionForm(forms.ModelForm):
    class Meta:
        model = GameSession
        fields = ["number", "date", "notes", "is_visible_to_players"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, campaign, **kwargs):
        super().__init__(*args, **kwargs)
        self.campaign = campaign

    def clean_number(self):
        number = self.cleaned_data["number"]
        clash = GameSession.objects.filter(campaign=self.campaign, number=number)
        if clash.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This campaign already has a session with that number.")
        return number
