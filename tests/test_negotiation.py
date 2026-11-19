"""Content negotiation: CSV-рендерер, 415 і кастомний заголовок табло."""


def test_scoreboard_default_is_json(api):
    response = api.get("/api/v1/scoreboard/")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/json")
    assert isinstance(response.json(), list)


def test_scoreboard_csv_via_format_param(api):
    response = api.get("/api/v1/scoreboard/?format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv"), (
        "?format=csv вибирає рендерер за його атрибутом format."
    )
    first_line = response.text.splitlines()[0]
    assert first_line.startswith("home_name,away_name"), (
        "Перший рядок CSV — шапка з назвами колонок."
    )


def test_scoreboard_csv_via_accept_header(api):
    response = api.get("/api/v1/scoreboard/", headers={"Accept": "text/csv"})
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv"), (
        "Той самий рендерер вибирається заголовком Accept — це і є "
        "content negotiation: Accept питає формат, Content-Type його оголошує."
    )


def test_csv_has_one_row_per_live_match(api):
    rows = api.get("/api/v1/scoreboard/?format=csv").text.strip().splitlines()
    live = api.get("/api/v1/scoreboard/").json()
    assert len(rows) == len(live) + 1, "Рядків даних стільки ж, скільки матчів, плюс шапка."


def test_unacceptable_accept_gives_406(api):
    response = api.get("/api/v1/scoreboard/", headers={"Accept": "application/xml"})
    assert response.status_code == 406, (
        "Клієнт просить формат, якого сервер не вміє віддавати — це 406 "
        "Not Acceptable, і відповідає за нього Accept, а не Content-Type."
    )


def test_unsupported_content_type_gives_415(api, tournament, team_ids):
    response = api.post(
        "/api/v1/matches/",
        data=b"<match></match>",
        headers={"Content-Type": "application/xml"},
    )
    assert response.status_code == 415, (
        "415 означає «не вмію читати цей формат тіла» — і до валідації "
        "справа навіть не доходить, тому це не 400."
    )


def test_scoreboard_sends_x_live_count(api):
    response = api.get("/api/v1/scoreboard/")
    assert "X-Live-Count" in response.headers, (
        "Табло віддає кількість живих матчів окремим заголовком — "
        "саме його потім доведеться відкривати через CORS_EXPOSE_HEADERS."
    )
    assert int(response.headers["X-Live-Count"]) == len(response.json())
