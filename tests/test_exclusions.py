from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import WEEKDAY, ist, office_policy
from when_next import Policy, when_next
from when_next.engine import HORIZON_DAYS


class TestExclusions:
    def test_arrival_on_an_excluded_date_moves_to_the_next_valid_day(self):
        policy = office_policy(exclude=["2026-11-09"])  # a Monday
        plan = when_next(ist(2026, 11, 9, 11, 0), policy)
        assert plan.at == ist(2026, 11, 10, 10, 0)

    def test_consecutive_exclusions_are_all_skipped(self):
        policy = office_policy(exclude=["2026-11-09", "2026-11-10", "2026-11-11"])
        plan = when_next(ist(2026, 11, 9, 11, 0), policy)
        assert plan.at == ist(2026, 11, 12, 10, 0)

    def test_a_holiday_immediately_followed_by_a_weekend_skips_the_whole_block(self):
        # Friday 6 Nov is a holiday; Saturday 7th works, Sunday 8th does not.
        # Removing Saturday too makes the block Fri/Sat/Sun.
        policy = office_policy(exclude=["2026-11-06", "2026-11-07"])
        plan = when_next(ist(2026, 11, 5, 21, 0), policy)  # Thursday evening
        assert plan.at == ist(2026, 11, 9, 10, 0)  # the following Monday

    def test_exclusions_accept_date_objects_as_well_as_strings(self):
        policy = office_policy(exclude=[date(2026, 11, 9)])
        plan = when_next(ist(2026, 11, 9, 11, 0), policy)
        assert plan.at == ist(2026, 11, 10, 10, 0)

    def test_a_malformed_exclusion_is_rejected_at_construction(self):
        with pytest.raises(ValueError, match="ISO dates"):
            office_policy(exclude=["08-11-2026"])

    def test_excluding_every_day_within_the_horizon_returns_invalid(self):
        policy = Policy(
            windows={"mon": WEEKDAY},
            exclude=[
                (
                    date(2026, 11, 2) + __import__("datetime").timedelta(days=7 * n)
                ).isoformat()
                for n in range(HORIZON_DAYS // 7 + 2)
            ],
            tz="Asia/Kolkata",
        )
        plan = when_next(ist(2026, 11, 2, 9, 0), policy)
        assert plan.valid is False
        assert str(HORIZON_DAYS) in plan.reason
