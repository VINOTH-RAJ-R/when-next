"""The resolution walk.

Computes a time and explains it. It never executes anything, never sleeps,
never persists, and never calls back. That restraint is the design: a scheduler
that also decides *when* is two responsibilities welded together, and the
deciding half is the one that needs to be inspectable, testable and readable by
someone who is not a developer.
"""

from __future__ import annotations

from datetime import date, timedelta
from datetime import datetime as _datetime
from zoneinfo import ZoneInfo

from .calendar import active_intervals, interval_opening_on
from .decisions import (
    AttemptsExhausted,
    BeforeOpen,
    Decision,
    Dropped,
    ExcludedDate,
    HorizonExceeded,
    InsideWindow,
    NoWindowForDay,
    NoWindowsDefined,
    Opened,
    OutsideWindow,
    Queued,
    RetryApplied,
)
from .policy import Plan, Policy
from .reasons import render

__all__ = ["HORIZON_DAYS", "when_next"]

HORIZON_DAYS = 400
"""How far forward the walk will look before giving up.

Long enough to clear any plausible run of exclusions, short enough that a
policy which can never be satisfied fails in milliseconds rather than looping.
"""

_DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def when_next(at: _datetime, policy: Policy, *, attempt: int = 0) -> Plan:
    """Resolve the next valid execution time for something arriving at ``at``.

    ``at`` must be timezone-aware. A naive datetime is rejected rather than
    assumed to be UTC or local, because both assumptions are wrong somewhere and
    the failure is silent in production.

    ``attempt`` counts retries from the *original* arrival: ``attempt=2`` adds
    two retry delays to ``at``. Keeping the function pure in its arguments means
    the same inputs always produce the same plan, which is what makes it
    testable and what lets a caller recompute a schedule from stored data rather
    than from remembered state.
    """
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError(
            "when_next requires a timezone-aware datetime; "
            "a naive one would have to be guessed as UTC or as local time, "
            "and both guesses are wrong somewhere"
        )

    zone = ZoneInfo(policy.tz)
    decisions: list[Decision] = []

    if not policy.has_any_window:
        decisions.append(NoWindowsDefined())
        return Plan(None, render(decisions), attempt=attempt, valid=False)

    moment = at.astimezone(zone)

    if attempt > 0:
        if policy.retry is None:
            raise ValueError(
                f"attempt={attempt} was requested but the policy defines no retry"
            )
        if attempt > policy.retry.max_attempts:
            decisions.append(AttemptsExhausted(attempt, policy.retry.max_attempts))
            return Plan(None, render(decisions), attempt=attempt, valid=False)
        moment = moment + policy.retry.delay * attempt
        decisions.append(RetryApplied(policy.retry.after, attempt))

    for interval in active_intervals(policy, moment.date(), zone):
        if interval.contains(moment):
            decisions.append(InsideWindow(_day_name(interval.opens_on)))
            return Plan(moment, render(decisions), attempt=attempt, valid=True)

    if policy.overflow == "drop":
        decisions.append(Dropped(_day_name(moment.date()), moment.time()))
        return Plan(None, render(decisions), attempt=attempt, valid=False)

    return _walk_forward(moment, policy, zone, decisions, attempt)


def _walk_forward(
    moment: _datetime,
    policy: Policy,
    zone: ZoneInfo,
    decisions: list[Decision],
    attempt: int,
) -> Plan:
    """Advance day by day to the first opening at or after ``moment``."""
    for offset in range(HORIZON_DAYS):
        day = moment.date() + timedelta(days=offset)

        if day in policy.exclude:
            decisions.append(ExcludedDate(day))
            continue

        interval = interval_opening_on(policy, day, zone)
        if interval is None:
            decisions.append(NoWindowForDay(_day_name(day)))
            continue

        if interval.start >= moment:
            if offset == 0:
                decisions.append(
                    BeforeOpen(_day_name(day), moment.time(), interval.start.time())
                )
            decisions.append(Opened(_day_name(day), interval.start.time()))
            if policy.overflow == "queue_fifo":
                decisions.append(Queued())
            return Plan(
                interval.start,
                render(decisions),
                attempt=attempt,
                valid=True,
                queued=True,
            )

        # The window opened earlier today and has already closed, or we would
        # have matched it as an active interval before the walk began.
        decisions.append(OutsideWindow(_day_name(day), moment.time()))

    decisions.append(HorizonExceeded(HORIZON_DAYS))
    return Plan(None, render(decisions), attempt=attempt, valid=False)


def _day_name(day: date) -> str:
    return _DAY_NAMES[day.weekday()]
