# SPDX-License-Identifier: Apache-2.0
"""Cron expression validation + next-fire calculation.

LocalLake uses the classic 5-field POSIX cron syntax via `croniter`. All
fire times are computed in UTC; per-schedule timezones are a v2 concern.

The scheduler loop in ``locallake_worker.scheduler`` calls
``is_due(expression, last_run_at, now)`` once per minute per active row to
decide whether to enqueue.
"""

from __future__ import annotations

from datetime import UTC, datetime

from croniter import CroniterBadCronError, croniter


class InvalidCronError(ValueError):
    """The cron expression failed parsing."""


def validate(expression: str) -> str:
    """Return the expression unchanged if it parses, else raise."""
    try:
        croniter(expression)
    except (CroniterBadCronError, ValueError) as exc:
        raise InvalidCronError(f"invalid cron expression: {expression!r}") from exc
    return expression


def next_fire(expression: str, after: datetime | None = None) -> datetime:
    """Return the next datetime (UTC, tz-aware) at which ``expression`` fires."""
    base = (after or datetime.now(UTC)).astimezone(UTC)
    it = croniter(expression, base)
    nxt: datetime = it.get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=UTC)
    return nxt


def is_due(
    expression: str,
    last_run_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    """Should this schedule fire at ``now``?

    Catch-up policy: fire at most once per wake cycle. If the worker was
    down for an hour and the schedule should have fired six times, we
    enqueue exactly one run — the most recent missed slot — and advance
    ``last_run_at``. The remaining missed slots are dropped intentionally;
    bulk catch-up is footgun behavior for analytics jobs.
    """
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    # Anchor the lookback at last_run_at (or one cron tick before "now" if
    # the schedule has never fired) and walk forward to find the next slot.
    anchor = (last_run_at or moment).astimezone(UTC) if last_run_at else None
    if anchor is None:
        # New schedule: fire only if "now" is itself a slot. Compute the
        # most recent slot at-or-before now; if it's within the current
        # minute, fire.
        prev: datetime = croniter(expression, moment).get_prev(datetime)
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=UTC)
        return (moment - prev).total_seconds() < 60
    nxt = next_fire(expression, anchor)
    return nxt <= moment
