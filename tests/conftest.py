from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from when_next import Policy, Window

IST = ZoneInfo("Asia/Kolkata")
NYC = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

WEEKDAY = Window("10:00", "19:00")
SATURDAY = Window("10:00", "14:00")


def ist(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=IST)


def office_policy(**overrides) -> Policy:
    """The standard five-and-a-half day week, with fields overridable."""
    base = {
        "windows": {
            "mon": WEEKDAY,
            "tue": WEEKDAY,
            "wed": WEEKDAY,
            "thu": WEEKDAY,
            "fri": WEEKDAY,
            "sat": SATURDAY,
        },
        "tz": "Asia/Kolkata",
    }
    base.update(overrides)
    return Policy(**base)


@pytest.fixture
def office() -> Policy:
    """A five-and-a-half day Indian office week. No Sunday window at all."""
    return Policy(
        windows={
            "mon": WEEKDAY,
            "tue": WEEKDAY,
            "wed": WEEKDAY,
            "thu": WEEKDAY,
            "fri": WEEKDAY,
            "sat": SATURDAY,
        },
        tz="Asia/Kolkata",
    )
