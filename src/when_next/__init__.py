"""Business scheduling rules as a value, with a reason you can hand to someone.

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from when_next import Policy, Window, when_next
    >>> IST = ZoneInfo("Asia/Kolkata")
    >>> policy = Policy(windows={"mon": Window("10:00", "19:00")}, tz="Asia/Kolkata")
    >>> plan = when_next(datetime(2026, 11, 2, 8, 30, tzinfo=IST), policy)
    >>> plan.reason
    'created 08:30, before Monday opening 10:00; next opening Monday 10:00'

It computes a time and explains it. It never runs anything.
"""

from __future__ import annotations

from .engine import HORIZON_DAYS, when_next
from .policy import Plan, Policy, Retry, Window

__all__ = [
    "HORIZON_DAYS",
    "Plan",
    "Policy",
    "Retry",
    "Window",
    "when_next",
]

__version__ = "0.1.0.dev0"
