from __future__ import annotations

import pytest

from tests.conftest import ist, office_policy
from when_next import Retry, when_next


class TestRetry:
    def test_attempt_zero_is_the_plain_resolution(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        arrival = ist(2026, 11, 3, 14, 0)
        assert when_next(arrival, policy, attempt=0).at == arrival

    def test_one_attempt_adds_one_delay(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        plan = when_next(ist(2026, 11, 3, 14, 0), policy, attempt=1)
        assert plan.at == ist(2026, 11, 5, 14, 0)

    def test_attempts_count_from_the_original_arrival(self):
        # attempt=2 means two delays from `at`, not two from the last attempt.
        # Tue 3rd 14:00 + 2 x 2d lands at Sat 7th 14:00, which is exactly the
        # Saturday closing time and therefore outside the half-open window, so
        # it walks past Sunday to Monday.
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        plan = when_next(ist(2026, 11, 3, 14, 0), policy, attempt=2)
        assert plan.at == ist(2026, 11, 9, 10, 0)

    def test_two_attempts_differ_from_one_by_exactly_one_delay(self):
        policy = office_policy(retry=Retry(after="1h", max_attempts=3))
        arrival = ist(2026, 11, 3, 11, 0)  # comfortably mid-window
        first = when_next(arrival, policy, attempt=1)
        second = when_next(arrival, policy, attempt=2)
        assert second.at - first.at == __import__("datetime").timedelta(hours=1)

    def test_a_retry_landing_outside_a_window_shifts_forward(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        # Fri 6th 21:00 + 2d = Sun 8th 21:00, which has no window at all.
        plan = when_next(ist(2026, 11, 6, 21, 0), policy, attempt=1)
        assert plan.at == ist(2026, 11, 9, 10, 0)

    def test_a_retry_landing_on_a_holiday_before_a_weekend_skips_the_block(self):
        policy = office_policy(
            exclude=["2026-11-06", "2026-11-07"],
            retry=Retry(after="1d", max_attempts=3),
        )
        # Thu 5th + 1d = Fri 6th, excluded; Sat 7th excluded; Sun 8th no window.
        plan = when_next(ist(2026, 11, 5, 11, 0), policy, attempt=1)
        assert plan.at == ist(2026, 11, 9, 10, 0)

    def test_a_retry_never_fires_earlier_than_the_arrival(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        arrival = ist(2026, 11, 3, 14, 0)
        for attempt in range(1, 4):
            assert when_next(arrival, policy, attempt=attempt).at > arrival

    def test_exhausted_attempts_return_invalid_with_an_explanation(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        plan = when_next(ist(2026, 11, 3, 14, 0), policy, attempt=4)
        assert plan.valid is False
        assert plan.at is None
        assert "max_attempts 3" in plan.reason

    def test_the_final_permitted_attempt_still_resolves(self):
        policy = office_policy(retry=Retry(after="2d", max_attempts=3))
        assert when_next(ist(2026, 11, 3, 14, 0), policy, attempt=3).valid is True

    def test_requesting_a_retry_with_no_retry_policy_is_an_error(self):
        with pytest.raises(ValueError, match="no retry"):
            when_next(ist(2026, 11, 3, 14, 0), office_policy(), attempt=1)

    @pytest.mark.parametrize(
        ("after", "expected"),
        [
            ("2d", __import__("datetime").timedelta(days=2)),
            ("36h", __import__("datetime").timedelta(hours=36)),
            ("90m", __import__("datetime").timedelta(minutes=90)),
        ],
    )
    def test_duration_strings_parse_to_the_right_delay(self, after, expected):
        assert Retry(after=after, max_attempts=2).delay == expected

    def test_a_minute_delay_that_stays_in_window_is_applied_exactly(self):
        policy = office_policy(retry=Retry(after="90m", max_attempts=2))
        plan = when_next(ist(2026, 11, 3, 14, 0), policy, attempt=1)
        assert plan.at == ist(2026, 11, 3, 15, 30)

    def test_an_hour_delay_that_leaves_the_window_resolves_forward(self):
        # Tue 14:00 + 36h is Thu 02:00, before the Thursday window opens.
        policy = office_policy(retry=Retry(after="36h", max_attempts=2))
        plan = when_next(ist(2026, 11, 3, 14, 0), policy, attempt=1)
        assert plan.at == ist(2026, 11, 5, 10, 0)
