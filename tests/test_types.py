"""Tests for the types module."""

from taskatlas._types import (
    DEFAULT_GOAL_STATUSES,
    DEFAULT_TASK_STAGES,
    LINK_KINDS,
    PRIORITY_LEVELS,
    PRIORITY_ORDER,
    UNSET,
)


class TestDefaults:
    def test_task_stages_present(self):
        assert "inbox" in DEFAULT_TASK_STAGES
        assert "done" in DEFAULT_TASK_STAGES
        assert "archived" in DEFAULT_TASK_STAGES

    def test_goal_statuses_present(self):
        assert "proposed" in DEFAULT_GOAL_STATUSES
        assert "achieved" in DEFAULT_GOAL_STATUSES
        assert "archived" in DEFAULT_GOAL_STATUSES

    def test_priorities_ordered(self):
        assert PRIORITY_ORDER["urgent"] > PRIORITY_ORDER["high"]
        assert PRIORITY_ORDER["high"] > PRIORITY_ORDER["medium"]
        assert PRIORITY_ORDER["medium"] > PRIORITY_ORDER["low"]

    def test_link_kinds(self):
        assert "depends_on" in LINK_KINDS
        assert "blocks" in LINK_KINDS
        assert "supports" in LINK_KINDS


class TestUnset:
    def test_falsy(self):
        assert not UNSET

    def test_repr(self):
        assert repr(UNSET) == "UNSET"

    def test_singleton(self):
        from taskatlas._types import _Unset
        assert _Unset() is UNSET
