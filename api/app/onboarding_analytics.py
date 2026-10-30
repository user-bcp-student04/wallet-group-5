import statistics
from datetime import datetime
from typing import Any

from app.onboarding_repositories import EventRepository
from app.onboarding_service import ACTIVE, EVENT_CLOSED, EVENT_STARTED


TARGET_MEDIAN_SECONDS = 180
MONTH_LENGTH = 7
SPEND_SOURCE_PENDING = "SOURCE_PENDING"

# Frontera analítica acordada: de `onboarding.started` a `onboarding.closed` con la wallet activa.
BOUNDARY = {"start": EVENT_STARTED, "end": EVENT_CLOSED, "outcome": ACTIVE}


def summarize(events: EventRepository) -> dict[str, Any]:
    started: dict[str, str] = {}
    closed: dict[str, str] = {}
    for row in events.list_lifecycle((EVENT_STARTED, EVENT_CLOSED)):
        if row["event"] == EVENT_STARTED:
            started[row["onboarding_id"]] = row["occurred_at"]
        elif row["outcome"] == ACTIVE:
            closed[row["onboarding_id"]] = row["occurred_at"]

    months: dict[str, dict[str, Any]] = {}
    for moment in started.values():
        _month(months, moment)["started"] += 1
    for onboarding_id, closed_at in closed.items():
        bucket = _month(months, closed_at)
        bucket["newActiveUsers"] += 1
        if onboarding_id in started:
            elapsed = datetime.fromisoformat(closed_at) - datetime.fromisoformat(started[onboarding_id])
            bucket["durations"].append(elapsed.total_seconds())

    return {
        "boundary": BOUNDARY,
        "targetMedianSeconds": TARGET_MEDIAN_SECONDS,
        "months": [_report(month, months[month]) for month in sorted(months)],
        # El gasto de adquisición no tiene fuente ni reglas de atribución acordadas: no se calcula CAC.
        "acquisitionSpend": {"status": SPEND_SOURCE_PENDING},
        "cac": None,
    }


def _month(months: dict[str, dict[str, Any]], moment: str) -> dict[str, Any]:
    return months.setdefault(
        moment[:MONTH_LENGTH], {"started": 0, "newActiveUsers": 0, "durations": []}
    )


def _report(month: str, bucket: dict[str, Any]) -> dict[str, Any]:
    durations = bucket["durations"]
    median = round(statistics.median(durations), 3) if durations else None
    return {
        "month": month,
        "started": bucket["started"],
        "newActiveUsers": bucket["newActiveUsers"],
        "medianSeconds": median,
        "withinTarget": None if median is None else median <= TARGET_MEDIAN_SECONDS,
    }
