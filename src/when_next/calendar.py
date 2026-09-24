"""Turning weekday-keyed windows into concrete instants.

The engine never compares weekday names or wall-clock strings. It asks this
module for real ``(start, end)`` datetime pairs and then asks plain interval
questions, because two things go wrong when you reason in weekdays:

**Midnight-crossing windows belong to the day they open on.** With
``Window("22:00", "02:00")`` defined for Monday, a timestamp at 01:00 on
*Tuesday* is inside Monday's window. Code that looks up Tuesday's window and
finds nothing will push that timestamp forward, which is exactly backwards. So
every candidate day materialises the window opening on it *and* the one opening
the day before.

**Daylight saving makes wall-clock times lie.** A window opening at 02:30 names
a time that does not exist on a spring-forward date, and one at 01:30 names two
distinct instants on a fall-back date. ``datetime`` will construct both without
complaint.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

from .policy import Policy, Window

__all__ = ["Interval", "active_intervals", "interval_opening_on", "localise"]

_MINUTES_IN_A_DAY = 24 * 60


class Interval(NamedTuple):
    """A concrete opening period, and the date whose window produced it."""

    start: datetime
    end: datetime
    opens_on: date

    def contains(self, moment: datetime) -> bool:
        """Half-open containment, compared in **wall-clock** terms.

        All three datetimes carry the policy's own ``ZoneInfo``, and Python
        subtracts and orders two aware datetimes sharing a ``tzinfo`` object by
        their naive fields, ignoring the offset. That is the behaviour this
        library wants and it is asserted here rather than left to chance: a
        business that opens "10:00 to 19:00" means the clock on the wall, so on
        a fall-back night both occurrences of a repeated hour are inside the
        window, and on a spring-forward morning the hour the clocks skipped is
        simply not available.

        Comparing by absolute instant instead would make a window one hour
        shorter or longer twice a year without anyone having changed the policy.
        """
        return self.start <= moment < self.end

    @property
    def real_duration(self) -> timedelta:
        """Elapsed time, which differs from the wall-clock span across a DST
        transition. Converting to UTC first is what makes the difference
        visible; subtracting the two local datetimes would not."""
        return self.end.astimezone(timezone.utc) - self.start.astimezone(timezone.utc)


def localise(naive: datetime, zone) -> datetime:
    """Attach ``zone`` to a naive wall-clock time, resolving DST explicitly.

    Two rules, both deliberate and both tested:

    * A wall-clock time that does not exist, because the clocks sprang forward
      over it, moves **forward** to the first minute that does exist.
    * A wall-clock time that occurs twice, because the clocks fell back over it,
      resolves to the **first** occurrence, so a window opens earlier rather
      than later.

    The second rule is just ``fold=0``, which is Python's default; it is stated
    here because relying on a default for a correctness property is how the rule
    gets lost in a later edit.
    """
    candidate = naive
    for _ in range(_MINUTES_IN_A_DAY):
        aware = candidate.replace(tzinfo=zone, fold=0)
        round_tripped = aware.astimezone(timezone.utc).astimezone(zone)
        if round_tripped.replace(tzinfo=None, fold=0) == candidate:
            return aware
        candidate += timedelta(minutes=1)
    raise ValueError(f"no valid local time found near {naive} in {zone}")


def interval_opening_on(policy: Policy, day: date, zone) -> Interval | None:
    """The opening period for the window that starts on ``day``, if any.

    Returns None when the day has no window or appears in the exclusion list.
    An excluded opening day removes the whole window, including the part of a
    midnight-crossing window that falls on the following date: the business was
    shut when the shift would have begun.
    """
    if day in policy.exclude:
        return None
    window = policy.window_for(day)
    if window is None:
        return None
    return _materialise(window, day, zone)


def active_intervals(policy: Policy, day: date, zone) -> list[Interval]:
    """Every opening period that could cover a moment on ``day``.

    That is the window opening on ``day`` and the one opening the day before,
    since the latter may still be running past midnight.
    """
    candidates = (
        interval_opening_on(policy, day - timedelta(days=1), zone),
        interval_opening_on(policy, day, zone),
    )
    return [interval for interval in candidates if interval is not None]


def _materialise(window: Window, day: date, zone) -> Interval:
    start = localise(datetime.combine(day, window.opens_at), zone)
    closes_on = day + timedelta(days=1) if window.crosses_midnight else day
    end = localise(datetime.combine(closes_on, window.closes_at), zone)
    return Interval(start=start, end=end, opens_on=day)
