"""The behaviour table from the README, one test per row."""

from __future__ import annotations

import pytest

from tests.conftest import IST, WEEKDAY, ist
from when_next import Policy, Window, when_next

# November 2026: 2nd is a Monday, 7th a Saturday, 8th a Sunday.


class TestArrivalInsideAWindow:
    def test_returns_the_arrival_time_unchanged(self, office):
        arrival = ist(2026, 11, 3, 14, 0)
        plan = when_next(arrival, office)
        assert plan.at == arrival
        assert plan.valid is True
        assert plan.queued is False

    def test_exactly_at_opening_is_inside(self, office):
        arrival = ist(2026, 11, 3, 10, 0)
        assert when_next(arrival, office).at == arrival

    def test_one_minute_before_closing_is_inside(self, office):
        arrival = ist(2026, 11, 3, 18, 59)
        assert when_next(arrival, office).at == arrival

    def test_exactly_at_closing_is_outside(self, office):
        # A half-open interval. 19:00 to 19:00 would otherwise be zero-length
        # work, and a closing time that is also an opening time is ambiguous.
        arrival = ist(2026, 11, 3, 19, 0)
        plan = when_next(arrival, office)
        assert plan.at == ist(2026, 11, 4, 10, 0)


class TestArrivalBeforeOpening:
    def test_returns_the_same_day_opening(self, office):
        plan = when_next(ist(2026, 11, 3, 8, 30), office)
        assert plan.at == ist(2026, 11, 3, 10, 0)
        assert plan.queued is True

    def test_midnight_returns_the_same_day_opening(self, office):
        plan = when_next(ist(2026, 11, 3, 0, 0), office)
        assert plan.at == ist(2026, 11, 3, 10, 0)


class TestArrivalAfterClosing:
    def test_returns_the_next_day_opening(self, office):
        plan = when_next(ist(2026, 11, 3, 21, 47), office)
        assert plan.at == ist(2026, 11, 4, 10, 0)

    def test_friday_evening_skips_to_saturday(self, office):
        plan = when_next(ist(2026, 11, 6, 21, 47), office)
        assert plan.at == ist(2026, 11, 7, 10, 0)

    def test_saturday_afternoon_skips_sunday_to_monday(self, office):
        # Saturday closes at 14:00 and Sunday has no window at all.
        plan = when_next(ist(2026, 11, 7, 16, 0), office)
        assert plan.at == ist(2026, 11, 9, 10, 0)


class TestDaysWithNoWindow:
    def test_a_weekday_with_no_window_is_skipped_entirely(self, office):
        plan = when_next(ist(2026, 11, 8, 11, 0), office)  # a Sunday
        assert plan.at == ist(2026, 11, 9, 10, 0)

    def test_a_policy_with_only_one_window_still_resolves(self):
        policy = Policy(windows={"wed": WEEKDAY}, tz="Asia/Kolkata")
        plan = when_next(ist(2026, 11, 5, 11, 0), policy)  # a Thursday
        assert plan.at == ist(2026, 11, 11, 10, 0)  # the following Wednesday

    def test_a_policy_with_no_windows_at_all_is_invalid_not_a_loop(self):
        policy = Policy(windows={}, tz="Asia/Kolkata")
        plan = when_next(ist(2026, 11, 3, 11, 0), policy)
        assert plan.valid is False
        assert plan.at is None
        assert "no windows" in plan.reason


class TestMidnightCrossingWindows:
    """A window that closes before it opens belongs to the day it opens on."""

    @pytest.fixture
    def night_shift(self) -> Policy:
        return Policy(
            windows={"mon": Window("22:00", "02:00")},
            tz="Asia/Kolkata",
        )

    def test_late_evening_on_the_opening_day_is_inside(self, night_shift):
        arrival = ist(2026, 11, 2, 23, 30)  # Monday
        assert when_next(arrival, night_shift).at == arrival

    def test_after_midnight_is_inside_the_previous_days_window(self, night_shift):
        # The case a weekday-keyed lookup gets exactly backwards: 01:00 Tuesday
        # belongs to Monday's window, and Tuesday has no window of its own.
        arrival = ist(2026, 11, 3, 1, 0)
        plan = when_next(arrival, night_shift)
        assert plan.at == arrival
        assert "Monday" in plan.reason

    def test_exactly_at_the_closing_hour_is_outside(self, night_shift):
        plan = when_next(ist(2026, 11, 3, 2, 0), night_shift)
        assert plan.at == ist(2026, 11, 9, 22, 0)  # the next Monday opening

    def test_mid_morning_after_the_shift_waits_a_week(self, night_shift):
        plan = when_next(ist(2026, 11, 3, 9, 0), night_shift)
        assert plan.at == ist(2026, 11, 9, 22, 0)

    def test_an_excluded_opening_day_removes_the_whole_shift(self):
        policy = Policy(
            windows={"mon": Window("22:00", "02:00")},
            exclude=["2026-11-02"],
            tz="Asia/Kolkata",
        )
        # 01:00 Tuesday would have been inside Monday's window, but Monday
        # was excluded, so the shift never began.
        plan = when_next(ist(2026, 11, 3, 1, 0), policy)
        assert plan.at == ist(2026, 11, 9, 22, 0)


class TestNaiveDatetimes:
    def test_a_naive_datetime_is_rejected(self, office):
        from datetime import datetime

        with pytest.raises(ValueError, match="timezone-aware"):
            when_next(datetime(2026, 11, 3, 14, 0), office)

    def test_an_aware_datetime_in_another_zone_is_converted(self, office):
        from datetime import datetime, timezone

        # 06:00 UTC is 11:30 IST, inside the Tuesday window.
        arrival = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
        plan = when_next(arrival, office)
        assert plan.at == arrival
        assert plan.at.astimezone(IST).hour == 11
