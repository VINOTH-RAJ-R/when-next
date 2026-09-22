"""The structured trace the engine emits as it resolves.

Reason strings are part of this library's public contract — they are tested for
exact text, and an operations lead is expected to read them. A contract
assembled by string concatenation scattered across a resolution loop is one that
changes by accident.

So the engine never writes English. It appends typed records describing the
decisions it actually took, and :mod:`when_next.reasons` is the only module that
turns records into words. Rewording touches one file. Adding a language touches
one file. The engine is tested on the decisions it made, which is what it is
actually responsible for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

__all__ = [
    "AttemptsExhausted",
    "BeforeOpen",
    "Decision",
    "Dropped",
    "ExcludedDate",
    "HorizonExceeded",
    "InsideWindow",
    "NoWindowForDay",
    "NoWindowsDefined",
    "Opened",
    "OutsideWindow",
    "Queued",
    "RetryApplied",
]


class Decision:
    """Base class for every record the engine can emit.

    Exists so a trace can be typed as ``list[Decision]`` and so the renderer's
    completeness test can enumerate subclasses. The renderer dispatches on
    concrete type and raises on anything it does not recognise, which together
    with that test makes an unrendered record a build failure rather than a
    production one.
    """

    __slots__ = ()


@dataclass(frozen=True)
class InsideWindow(Decision):
    """The arrival was already within an open window."""

    day: str


@dataclass(frozen=True)
class BeforeOpen(Decision):
    """The arrival was on a day with a window, but before it opened."""

    day: str
    arrival: time
    opens: time


@dataclass(frozen=True)
class OutsideWindow(Decision):
    """The arrival was after the day's window had closed."""

    day: str
    arrival: time


@dataclass(frozen=True)
class NoWindowForDay(Decision):
    """A candidate day has no window defined at all."""

    day: str


@dataclass(frozen=True)
class ExcludedDate(Decision):
    """A candidate day appears in the caller-supplied exclusion list."""

    on: date


@dataclass(frozen=True)
class Opened(Decision):
    """A slot was found, at the opening of this day's window."""

    day: str
    at: time


@dataclass(frozen=True)
class RetryApplied(Decision):
    """A retry delay was added before resolution began."""

    after: str
    attempt: int


@dataclass(frozen=True)
class AttemptsExhausted(Decision):
    """The requested attempt is beyond what the retry policy allows."""

    attempt: int
    max_attempts: int


@dataclass(frozen=True)
class Dropped(Decision):
    """An out-of-window arrival under ``overflow="drop"``."""

    day: str
    arrival: time


@dataclass(frozen=True)
class Queued(Decision):
    """Recorded under ``overflow="queue_fifo"``.

    ``next_open`` and ``queue_fifo`` resolve to the same instant, because a
    pure function handed a single timestamp cannot order a queue it does not
    own. The difference is what the caller is told: this record, and
    ``Plan.queued``.
    """


@dataclass(frozen=True)
class NoWindowsDefined(Decision):
    """The policy defines no windows on any day."""


@dataclass(frozen=True)
class HorizonExceeded(Decision):
    """The forward walk reached its limit without finding a slot."""

    days: int
