"""Business scheduling rules as a value, with a reason you can hand to someone.

It computes a time and explains it. It never runs anything.
"""

from __future__ import annotations

from .policy import Plan, Policy, Retry, Window

__all__ = [
    "Plan",
    "Policy",
    "Retry",
    "Window",
]

__version__ = "0.1.0.dev0"
