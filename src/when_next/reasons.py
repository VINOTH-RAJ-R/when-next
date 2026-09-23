"""Turning the decision trace into a sentence a non-engineer can read.

The register to aim for is an operations handover note, not a log line:

    inside Tuesday window, no change
    created 21:47, after Friday close; next opening Monday 10:00
    retry +2d landed on an excluded date; next opening Monday 10:00
    retry attempt 4 exceeds max_attempts 3; no further attempt scheduled

This is the only module in the package that contains English.
"""

from __future__ import annotations

from datetime import time

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

__all__ = ["render"]

_MAX_SKIPS_NAMED = 2


def render(decisions: list[Decision]) -> str:
    """Render a decision trace as a single reason string."""
    if not decisions:
        return "no decisions recorded"
    clauses = [
        clause for clause in (_clause(d) for d in _collapse(decisions)) if clause
    ]
    return "; ".join(clauses) if clauses else "no decisions recorded"


def _collapse(decisions: list[Decision]) -> list[Decision]:
    """Summarise a long run of skipped days rather than listing each one.

    A retry that lands on a holiday followed by a weekend produces three
    consecutive skips, and naming all three is still readable. A policy with
    only a Monday window produces six, and naming all six is not.
    """
    collapsed: list[Decision] = []
    run: list[Decision] = []

    def flush() -> None:
        if not run:
            return
        if len(run) <= _MAX_SKIPS_NAMED:
            collapsed.extend(run)
        else:
            collapsed.append(_SkippedRun(len(run)))
        run.clear()

    for decision in decisions:
        if isinstance(decision, (NoWindowForDay, ExcludedDate)):
            run.append(decision)
            continue
        flush()
        collapsed.append(decision)
    flush()
    return collapsed


class _SkippedRun(Decision):
    """Several consecutive skipped days, reported as a count."""

    __slots__ = ("count",)

    def __init__(self, count: int) -> None:
        self.count = count


def _clause(decision: Decision) -> str | None:
    if isinstance(decision, InsideWindow):
        return f"inside {decision.day} window, no change"

    if isinstance(decision, BeforeOpen):
        return (
            f"created {_hhmm(decision.arrival)}, "
            f"before {decision.day} opening {_hhmm(decision.opens)}"
        )

    if isinstance(decision, OutsideWindow):
        return f"created {_hhmm(decision.arrival)}, after {decision.day} close"

    if isinstance(decision, NoWindowForDay):
        return f"no window defined for {decision.day}, skipped"

    if isinstance(decision, ExcludedDate):
        return f"{decision.on.isoformat()} is an excluded date, skipped"

    if isinstance(decision, _SkippedRun):
        return f"{decision.count} non-working days skipped"

    if isinstance(decision, Opened):
        return f"next opening {decision.day} {_hhmm(decision.at)}"

    if isinstance(decision, RetryApplied):
        return f"retry +{decision.after} (attempt {decision.attempt})"

    if isinstance(decision, AttemptsExhausted):
        return (
            f"retry attempt {decision.attempt} exceeds "
            f"max_attempts {decision.max_attempts}; no further attempt scheduled"
        )

    if isinstance(decision, Queued):
        return "queued in arrival order"

    if isinstance(decision, Dropped):
        return (
            f"created {_hhmm(decision.arrival)}, outside {decision.day} window; "
            f"overflow policy is drop, not rescheduled"
        )

    if isinstance(decision, NoWindowsDefined):
        return "policy defines no windows; nothing can ever be scheduled"

    if isinstance(decision, HorizonExceeded):
        return f"no valid slot within the {decision.days}-day horizon"

    raise TypeError(f"no reason text defined for {type(decision).__name__}")


def _hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"
