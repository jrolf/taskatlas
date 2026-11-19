"""Tests for lifecycle constants, canonical link kinds, and sentinels."""

from taskatlas._types import (
    DREAM_STATUSES,
    GOAL_STATUSES,
    LINK_KINDS,
    PRIORITY_ORDER,
    TASK_STAGES,
    UNSET,
    _Unset,
)


class TestLifecycleVocabularies:
    def test_dream_statuses(self):
        assert DREAM_STATUSES == (
            "seed",
            "active",
            "dormant",
            "realized",
            "abandoned",
        )

    def test_goal_statuses(self):
        assert GOAL_STATUSES == (
            "proposed",
            "active",
            "paused",
            "achieved",
            "abandoned",
        )

    def test_task_stages_separate_from_blockage_and_archival(self):
        assert TASK_STAGES == (
            "inbox",
            "ready",
            "active",
            "review",
            "done",
            "canceled",
        )
        assert "blocked" not in TASK_STAGES
        assert "archived" not in TASK_STAGES

    def test_canonical_link_kinds(self):
        assert LINK_KINDS == ("depends_on", "relates_to", "derived_from")

    def test_priority_ordering(self):
        assert PRIORITY_ORDER["urgent"] > PRIORITY_ORDER["high"]
        assert PRIORITY_ORDER["high"] > PRIORITY_ORDER["medium"]
        assert PRIORITY_ORDER["medium"] > PRIORITY_ORDER["low"]


class TestUnsetSentinel:
    def test_unset_singleton_and_falsy(self):
        assert not UNSET
        assert repr(UNSET) == "UNSET"
        assert _Unset() is UNSET


class TestPackageVersionSync:
    def test_dunder_version_matches_pyproject_toml(self):
        import re
        from pathlib import Path

        import taskatlas as ta

        pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.M)
        assert match is not None
        assert ta.__version__ == match.group(1)
