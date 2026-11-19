from django.db.models import Q
from django_filters import rest_framework as filters

from .models import Match


class MatchFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Match.Status.choices)
    tournament = filters.NumberFilter(field_name="tournament")
    team = filters.NumberFilter(method="filter_by_team")

    class Meta:
        model = Match
        fields = ["status", "tournament", "team"]

    def filter_by_team(self, queryset, name, value):
        """Фільтр по команді: OR по home і away."""
        if value is None:
            return queryset
        return queryset.filter(Q(home_id=value) | Q(away_id=value))
