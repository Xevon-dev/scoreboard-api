"""В'юхи табло: турніри (read-only), матчі (+ події через @action), табло."""
from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, renderer_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse

from .filters import MatchFilter
from .models import Event, Match, Tournament
from .pagination import StandardResultsSetPagination
from .renderers import ScoreboardCSVRenderer
from .serializers import (
    EventSerializer,
    MatchDetailSerializer,
    MatchSerializer,
    TournamentSerializer,
)


POLL_MIN_SECONDS, POLL_MAX_SECONDS = 5, 300


def poll_after_seconds(live_count):
    if live_count:
        return POLL_MIN_SECONDS

    next_start = (
        Match.objects
        .filter(status=Match.Status.SCHEDULED, starts_at__gt=timezone.now())
        .order_by("starts_at")
        .values_list("starts_at", flat=True)
        .first()
    )
    if next_start is None:
        return POLL_MAX_SECONDS

    seconds = int((next_start - timezone.now()).total_seconds())
    return max(POLL_MIN_SECONDS, min(POLL_MAX_SECONDS, seconds))


# Єдині дозволені переходи стану.
ALLOWED_TRANSITIONS = {
    (Match.Status.SCHEDULED, Match.Status.LIVE),
    (Match.Status.LIVE, Match.Status.FINISHED),
}


def conflict(detail, code):
    """409: дані правильні, але зараз так робити не можна."""
    return Response({"detail": detail, "code": code}, status=status.HTTP_409_CONFLICT)


def match_queryset():
    return (
        Match.objects
        .select_related("tournament", "home", "away")
        .annotate(
            home_goals=Count(
                "events",
                filter=Q(events__kind=Event.Kind.GOAL, events__team=F("home")),
            ),
            away_goals=Count(
                "events",
                filter=Q(events__kind=Event.Kind.GOAL, events__team=F("away")),
            ),
        )
        .order_by("starts_at", "id")
    )


class TournamentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Tournament.objects
        .annotate(matches_total=Count("matches"))
        .order_by("starts_on", "id")
    )
    serializer_class = TournamentSerializer
    lookup_field = "slug"


class MatchViewSet(viewsets.ModelViewSet):
    # serializer_class = MatchSerializer
    # Без "put": повна заміна матчу контрактом не передбачена → 405.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MatchFilter
    search_fields = ["home__name", "away__name"]
    ordering_fields = ["starts_at", "status"]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = match_queryset()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch("events", queryset=Event.objects.select_related("team"))
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MatchDetailSerializer
        return MatchSerializer

    def perform_create(self, serializer):
        # status із тіла запиту ігноруємо: новий матч завжди scheduled.
        serializer.save(status=Match.Status.SCHEDULED)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # DRF сам Location не ставить (для цього потрібне поле url) — додаємо вручну.
        response["Location"] = reverse(
            "match-detail", args=[response.data["id"]], request=request
        )
        return response

    def partial_update(self, request, *args, **kwargs):
        match = self.get_object()  # 404, якщо матчу немає
        new_status = request.data.get("status")
        # Перехід — рішення в'юхи (409), а не валідація серіалізатора (400).
        # Невідоме значення статусу сюди не потрапляє: його відсіче серіалізатор (400).
        if (
            new_status in Match.Status.values
            and new_status != match.status
            and (match.status, new_status) not in ALLOWED_TRANSITIONS
        ):
            return conflict(
                f"Перехід {match.status} → {new_status} неможливий.",
                "invalid_status_transition",
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        match = self.get_object()
        if match.status != Match.Status.SCHEDULED:
            return conflict(
                "Матч уже почався, видалити його не можна.", "match_started"
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get", "post"], url_path="events")
    def events(self, request, pk=None):
        match = self.get_object()  # 1) 404 — матчу немає

        if request.method == "GET":
            events = match.events.select_related("team")
            # Голий масив: на @action пагінації немає.
            return Response(EventSerializer(events, many=True).data)

        # POST
        if match.status != Match.Status.LIVE:  # 2) 409 — стан матчу
            return conflict(
                "Події можна додавати лише до матчу, що триває.", "match_not_live"
            )

        serializer = EventSerializer(data=request.data, context={"match": match})
        serializer.is_valid(raise_exception=True)  # 3) 400 — валідація тіла
        serializer.save(match=match)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@renderer_classes([JSONRenderer, ScoreboardCSVRenderer])
def scoreboard(request):
    """Зведений звіт: матчі, що тривають, голим масивом, за starts_at."""
    matches = match_queryset().filter(status=Match.Status.LIVE)
    data = MatchSerializer(matches, many=True).data
    response = Response(data)
    response["X-Live-Count"] = str(len(data))
    response["X-Poll-After"] = str(poll_after_seconds(len(data)))
    return response
