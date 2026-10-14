from __future__ import annotations

from tests.conftest import ist, office_policy
from when_next import when_next


class TestOverflowModes:
    def test_drop_returns_invalid_for_an_out_of_window_arrival(self):
        policy = office_policy(overflow="drop")
        plan = when_next(ist(2026, 11, 3, 21, 47), policy)
        assert plan.valid is False
        assert plan.at is None
        assert "drop" in plan.reason

    def test_drop_still_accepts_an_in_window_arrival(self):
        policy = office_policy(overflow="drop")
        arrival = ist(2026, 11, 3, 14, 0)
        plan = when_next(arrival, policy)
        assert plan.valid is True
        assert plan.at == arrival

    def test_queue_fifo_and_next_open_resolve_to_the_same_instant(self):
        arrival = ist(2026, 11, 3, 21, 47)
        fifo = when_next(arrival, office_policy(overflow="queue_fifo"))
        nxt = when_next(arrival, office_policy(overflow="next_open"))
        assert fifo.at == nxt.at

    def test_queue_fifo_says_so_in_the_reason(self):
        plan = when_next(ist(2026, 11, 3, 21, 47), office_policy(overflow="queue_fifo"))
        assert "queued in arrival order" in plan.reason
        assert plan.queued is True

    def test_next_open_does_not_claim_a_queue(self):
        plan = when_next(ist(2026, 11, 3, 21, 47), office_policy(overflow="next_open"))
        assert "queued in arrival order" not in plan.reason
