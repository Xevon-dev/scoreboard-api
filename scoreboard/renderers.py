import csv
import io

from rest_framework.renderers import BaseRenderer


class ScoreboardCSVRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    header = ["home_name", "away_name", "home_goals", "away_goals", "starts_at"]

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return ""

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(self.header)
        for match in data:
            score = match.get("score") or {}
            writer.writerow(
                [
                    match["home_name"],
                    match["away_name"],
                    score.get("home", 0),
                    score.get("away", 0),
                    match["starts_at"],
                ]
            )
        return output.getvalue()
