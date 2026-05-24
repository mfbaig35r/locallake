# SPDX-License-Identifier: Apache-2.0
"""Cron parsing + due-time logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from locallake_core.cron import (
    InvalidCronError,
    is_due,
    next_fire,
    validate,
)


@pytest.mark.parametrize(
    "expr",
    ["* * * * *", "0 * * * *", "0 0 * * *", "*/15 * * * *", "0 9 * * 1-5"],
)
def test_validate_accepts_canonical(expr: str) -> None:
    assert validate(expr) == expr


@pytest.mark.parametrize(
    "expr",
    ["", "garbage", "61 * * * *", "* * * * 8", "* *"],
)
def test_validate_rejects_invalid(expr: str) -> None:
    with pytest.raises(InvalidCronError):
        validate(expr)


def test_next_fire_advances_from_anchor() -> None:
    anchor = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)
    nxt = next_fire("0 * * * *", anchor)
    assert nxt == datetime(2026, 5, 24, 10, 0, tzinfo=UTC)


def test_is_due_new_schedule_at_slot_boundary() -> None:
    now = datetime(2026, 5, 24, 10, 0, 15, tzinfo=UTC)
    # Hourly cron at :00 — current moment is 10:00:15, last_run_at None.
    assert is_due("0 * * * *", None, now) is True


def test_is_due_new_schedule_off_slot() -> None:
    now = datetime(2026, 5, 24, 10, 30, 0, tzinfo=UTC)
    # Hourly cron, but we're 30 minutes past the most recent slot.
    assert is_due("0 * * * *", None, now) is False


def test_is_due_skips_when_just_ran() -> None:
    now = datetime(2026, 5, 24, 10, 0, 30, tzinfo=UTC)
    last = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    assert is_due("0 * * * *", last, now) is False


def test_is_due_fires_at_next_slot() -> None:
    now = datetime(2026, 5, 24, 11, 0, 30, tzinfo=UTC)
    last = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    assert is_due("0 * * * *", last, now) is True


def test_is_due_does_not_backfire_multiple_missed_slots() -> None:
    """Worker offline for 5 hours; schedule fires once on wake, not five times."""
    last = datetime(2026, 5, 24, 5, 0, 0, tzinfo=UTC)
    now = last + timedelta(hours=5, minutes=30)
    # First call: due.
    assert is_due("0 * * * *", last, now) is True
    # After enqueueing, the scheduler bumps last_run_at to "now". Next tick
    # one minute later should not fire again.
    bumped = now
    later = now + timedelta(minutes=1)
    assert is_due("0 * * * *", bumped, later) is False
