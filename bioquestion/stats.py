"""Persist quiz history and build personal score trend charts."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bioquestion.schemas import GradingReport, QuizMode

HISTORY_PATH = Path("output") / "stats" / "score_history.jsonl"
TREND_DAYS = 10
MIN_SUBMISSIONS_PER_BUCKET = 3
LEADERBOARD_API_HOST = "127.0.0.1"
LEADERBOARD_API_PORT = 8765


class ScoreRecord(BaseModel):
    """One graded normal-mode submission."""

    timestamp: str
    date: str
    score: float
    max_score: float
    percentage: float
    mode: str = QuizMode.NORMAL.value
    source_label: str = ""
    user_name: str = ""


def leaderboard_api_url() -> str:
    return f"http://{LEADERBOARD_API_HOST}:{LEADERBOARD_API_PORT}/api/leaderboard"


def append_score_record(
    report: GradingReport,
    *,
    source_label: str = "",
    user_name: str = "",
    path: Path = HISTORY_PATH,
) -> None:
    """Append a normal-mode graded submission to local history."""
    if not report.scoring_enabled or report.quiz_mode != QuizMode.NORMAL:
        return

    now = datetime.now()
    record = ScoreRecord(
        timestamp=now.isoformat(timespec="seconds"),
        date=now.date().isoformat(),
        score=report.total_score,
        max_score=report.max_score,
        percentage=report.percentage,
        mode=QuizMode.NORMAL.value,
        source_label=source_label,
        user_name=user_name.strip(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")


def load_score_records(path: Path = HISTORY_PATH) -> list[ScoreRecord]:
    if not path.exists():
        return []

    records: list[ScoreRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(ScoreRecord.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError):
            continue
    return records


def _parse_record_date(record: ScoreRecord) -> date | None:
    try:
        return date.fromisoformat(record.date)
    except ValueError:
        try:
            return datetime.fromisoformat(record.timestamp).date()
        except ValueError:
            return None


def build_recent_score_trend(
    records: list[ScoreRecord],
    *,
    end_date: date | None = None,
    num_days: int = TREND_DAYS,
) -> list[dict[str, Any]]:
    """Build bar-chart buckets from the last calendar days.

    Days with ≤3 submissions are merged forward until the bucket has >3
    submissions or the window ends.
    """
    end = end_date or date.today()
    start = end - timedelta(days=num_days - 1)
    window_days = [start + timedelta(days=i) for i in range(num_days)]

    daily_scores: dict[date, list[float]] = defaultdict(list)
    for record in records:
        if record.mode != QuizMode.NORMAL.value:
            continue
        record_date = _parse_record_date(record)
        if record_date is None or record_date < start or record_date > end:
            continue
        daily_scores[record_date].append(record.percentage)

    buckets: list[dict[str, Any]] = []
    index = 0
    while index < num_days:
        pool: list[float] = list(daily_scores.get(window_days[index], []))
        bucket_start = window_days[index]
        bucket_end = bucket_start
        cursor = index

        while len(pool) <= MIN_SUBMISSIONS_PER_BUCKET and cursor < num_days - 1:
            cursor += 1
            bucket_end = window_days[cursor]
            pool.extend(daily_scores.get(bucket_end, []))

        label = bucket_start.strftime("%m-%d")
        if bucket_end != bucket_start:
            label = f"{bucket_start.strftime('%m-%d')}–{bucket_end.strftime('%m-%d')}"

        buckets.append(
            {
                "label": label,
                "average_score": round(sum(pool) / len(pool), 1) if pool else None,
                "submission_count": len(pool),
                "start_date": bucket_start.isoformat(),
                "end_date": bucket_end.isoformat(),
            }
        )
        index = cursor + 1

    return buckets


def personal_stats_summary(records: list[ScoreRecord]) -> dict[str, Any]:
    normal = [r for r in records if r.mode == QuizMode.NORMAL.value]
    if not normal:
        return {
            "total_submissions": 0,
            "average_score": None,
            "best_score": None,
            "recent_7_day_average": None,
        }

    percentages = [r.percentage for r in normal]
    cutoff = date.today() - timedelta(days=6)
    recent = [
        r.percentage
        for r in normal
        if (d := _parse_record_date(r)) is not None and d >= cutoff
    ]
    return {
        "total_submissions": len(normal),
        "average_score": round(sum(percentages) / len(percentages), 1),
        "best_score": round(max(percentages), 1),
        "recent_7_day_average": round(sum(recent) / len(recent), 1) if recent else None,
    }
