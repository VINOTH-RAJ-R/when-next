from __future__ import annotations

import pytest

from tests.conftest import WEEKDAY, office_policy
from when_next import Policy, Retry, Window


class TestPolicyValidation:
    @pytest.mark.parametrize("bad", ["9:00", "25:00", "10:60", "1000", "", "ten"])
    def test_malformed_window_times_are_rejected(self, bad: str):
        with pytest.raises(ValueError, match="HH:MM"):
            Window(bad, "19:00")

    def test_a_zero_length_window_is_rejected(self):
        with pytest.raises(ValueError, match="zero-length"):
            Window("10:00", "10:00")

    def test_an_unknown_weekday_key_is_rejected(self):
        with pytest.raises(ValueError, match="unknown weekday"):
            Policy(windows={"monday": WEEKDAY})

    def test_an_unknown_overflow_mode_is_rejected(self):
        with pytest.raises(ValueError, match="overflow must be"):
            Policy(windows={"mon": WEEKDAY}, overflow="hold")

    @pytest.mark.parametrize("bad", ["2", "2w", "d", "", "2 d"])
    def test_malformed_retry_durations_are_rejected(self, bad: str):
        with pytest.raises(ValueError, match="d, h or m"):
            Retry(after=bad, max_attempts=3)

    def test_a_non_positive_max_attempts_is_rejected(self):
        with pytest.raises(ValueError, match="at least 1"):
            Retry(after="2d", max_attempts=0)

    def test_a_window_passed_as_a_tuple_is_rejected(self):
        with pytest.raises(ValueError, match="must be a Window"):
            Policy(windows={"mon": ("10:00", "19:00")})

    def test_a_policy_is_hashable_and_comparable(self):
        assert office_policy() == office_policy()
