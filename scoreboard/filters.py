from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Match

def filter_by_team(qs,name, value):
    """Фільтр по команді: OR по home і away."""
    return qs.filter(Q(home=value) | Q(away=value))

class MatchFilter(filters.FilterSet):
    team = filters.NumberFilter(field_name="price", method=filter_by_team)
    status = filters.ChoiceFilter(choices=Match.Status.choices)

    class Meta:
        model = Match
        fields = ['team', 'status']