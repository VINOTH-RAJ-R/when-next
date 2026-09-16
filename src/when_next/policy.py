"""The value types: what a scheduling rule looks like when it is data.

The argument this library makes is that scheduling rules are business rules, and
business rules belong in an explicit layer rather than scattered through a
codebase as conditionals. That argument only holds if the layer is genuinely
inspectable, so everything here is a frozen dataclass that validates on
construction and can be printed, compared, serialised and reviewed by someone
who does not read Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

__all__ = ["WEEKDAYS", "Plan", "Policy", "Retry", "Window"]

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DURATION = re.compile(r"^(\d+)([dhm])$")
_DURATION_UNITS = {"d": "days", "h": "hours", "m": "minutes"}

OVERFLOW_MODES = ("next_open", "queue_fifo", "drop")


@dataclass(frozen=True)
class Window:
    """An opening period on a single weekday, in wall-clock local time.

    A ``close`` earlier than ``open`` means the window crosses midnight: the
    window belongs to the day it opens on, and its closing time falls on the
    following calendar date. ``Window("22:00", "02:00")`` therefore covers
    01:00 on Tuesday as part of *Monday's* window.
    """

    open: str
    close: str

    def __post_init__(self) -> None:
        for label, value in (("open", self.open), ("close", self.close)):
            if not isinstance(value, str) or not _TIME.match(value):
                raise ValueError(
                    f"Window {label} must be 'HH:MM' in 24-hour time, got {value!r}"
                )
        if self.open == self.close:
            raise ValueError(
                f"Window open and close are both {self.open!r}; "
                "a zero-length window can never be satisfied"
            )

    @property
    def opens_at(self) -> time:
        return _parse_time(self.open)

    @property
    def closes_at(self) -> time:
        return _parse_time(self.close)

    @property
    def crosses_midnight(self) -> bool:
        return self.closes_at <= self.opens_at


@dataclass(frozen=True)
class Retry:
    """How long to wait before a further attempt, and how many are allowed.

    ``after`` accepts ``"2d"``, ``"36h"`` or ``"90m"``. Deliberately not a
    ``timedelta``: the policy is meant to survive a round trip through JSON so
    it can live in a config file rather than in code.
    """

    after: str
    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.after, str) or not _DURATION.match(self.after):
            raise ValueError(
                f"Retry after must be a count followed by d, h or m, "
                f"such as '2d' or '90m', got {self.after!r}"
            )
        if not isinstance(self.max_attempts, int) or isinstance(
            self.max_attempts, bool
        ):
            raise ValueError(
                f"Retry max_attempts must be an integer, got {self.max_attempts!r}"
            )
        if self.max_attempts < 1:
            raise ValueError(
                f"Retry max_attempts must be at least 1, got {self.max_attempts}"
            )

    @property
    def delay(self) -> timedelta:
        match = _DURATION.match(self.after)
        assert match is not None  # guaranteed by __post_init__
        amount, unit = int(match.group(1)), match.group(2)
        return timedelta(**{_DURATION_UNITS[unit]: amount})


@dataclass(frozen=True)
class Policy:
    """A complete set of scheduling rules, as one inspectable value.

    ``exclude`` is supplied by the caller and never bundled. An Indian business
    calendar is not a US one, and a library that ships either is wrong for
    everybody else while looking authoritative.
    """

    windows: dict[str, Window]
    exclude: frozenset[date] = field(default_factory=frozenset)
    overflow: str = "next_open"
    retry: Retry | None = None
    tz: str = "UTC"

    def __init__(
        self,
        windows: dict[str, Window],
        exclude: list[str] | list[date] | None = None,
        overflow: str = "next_open",
        retry: Retry | None = None,
        tz: str = "UTC",
    ) -> None:
        unknown = set(windows) - set(WEEKDAYS)
        if unknown:
            raise ValueError(
                f"unknown weekday key(s) {sorted(unknown)}; "
                f"expected any of {list(WEEKDAYS)}"
            )
        for day, window in windows.items():
            if not isinstance(window, Window):
                raise ValueError(
                    f"windows[{day!r}] must be a Window, got {type(window).__name__}"
                )
        if overflow not in OVERFLOW_MODES:
            raise ValueError(
                f"overflow must be one of {list(OVERFLOW_MODES)}, got {overflow!r}"
            )
        if retry is not None and not isinstance(retry, Retry):
            raise ValueError(
                f"retry must be a Retry or None, got {type(retry).__name__}"
            )

        object.__setattr__(self, "windows", dict(windows))
        object.__setattr__(self, "exclude", _parse_exclusions(exclude or []))
        object.__setattr__(self, "overflow", overflow)
        object.__setattr__(self, "retry", retry)
        object.__setattr__(self, "tz", tz)

    def window_for(self, day: date) -> Window | None:
        return self.windows.get(WEEKDAYS[day.weekday()])

    @property
    def has_any_window(self) -> bool:
        return bool(self.windows)


@dataclass(frozen=True)
class Plan:
    """The answer: when, why, and whether there is an answer at all.

    ``reason`` is part of the public contract, not a debug string. It exists so
    an operations lead can be shown why something ran when it ran without a
    developer translating.
    """

    at: datetime | None
    reason: str
    attempt: int = 0
    valid: bool = True
    queued: bool = False
    """True when the item was displaced from its arrival time rather than
    being naturally in-window. Ordering among displaced items belongs to the
    caller; this library does not own a queue."""

    def __bool__(self) -> bool:
        return self.valid


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _parse_exclusions(values: list[str] | list[date]) -> frozenset[date]:
    parsed: set[date] = set()
    for value in values:
        if isinstance(value, datetime):
            parsed.add(value.date())
        elif isinstance(value, date):
            parsed.add(value)
        elif isinstance(value, str):
            try:
                parsed.add(date.fromisoformat(value))
            except ValueError as exc:
                raise ValueError(
                    f"exclude entries must be ISO dates like '2026-11-08', "
                    f"got {value!r}"
                ) from exc
        else:
            raise ValueError(
                f"exclude entries must be ISO date strings or date objects, "
                f"got {type(value).__name__}"
            )
    return frozenset(parsed)
