"""Tests for the Link model."""

import pytest

from taskatlas._link import Link


class TestLinkCreation:
    def test_basic(self):
        lk = Link(
            source_id="t-aaa11111",
            source_type="task",
            target_id="t-bbb22222",
            target_type="task",
            kind="depends_on",
        )
        assert lk.id.startswith("lk-")
        assert lk.kind == "depends_on"
        assert lk.source_id == "t-aaa11111"
        assert lk.target_id == "t-bbb22222"
        assert lk.meta == {}

    def test_goal_to_task(self):
        lk = Link(
            source_id="g-aaa11111",
            source_type="goal",
            target_id="t-bbb22222",
            target_type="task",
            kind="supports",
        )
        assert lk.source_type == "goal"
        assert lk.target_type == "task"

    def test_with_meta(self):
        lk = Link(
            source_id="t-aaa11111",
            source_type="task",
            target_id="t-bbb22222",
            target_type="task",
            kind="blocks",
            meta={"severity": "critical"},
        )
        assert lk.meta["severity"] == "critical"

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="Invalid link kind"):
            Link(
                source_id="t-aaa11111",
                source_type="task",
                target_id="t-bbb22222",
                target_type="task",
                kind="invented_kind",
            )

    def test_invalid_source_type_raises(self):
        with pytest.raises(ValueError, match="source_type"):
            Link(
                source_id="x-aaa11111",
                source_type="widget",
                target_id="t-bbb22222",
                target_type="task",
                kind="blocks",
            )

    def test_self_link_raises(self):
        with pytest.raises(ValueError, match="itself"):
            Link(
                source_id="t-aaa11111",
                source_type="task",
                target_id="t-aaa11111",
                target_type="task",
                kind="relates_to",
            )


class TestLinkSerialization:
    def test_round_trip(self):
        lk1 = Link(
            source_id="g-aaa11111",
            source_type="goal",
            target_id="t-bbb22222",
            target_type="task",
            kind="supports",
            meta={"note": "critical path"},
        )
        d = lk1.to_dict()
        lk2 = Link.from_dict(d)

        assert lk2.id == lk1.id
        assert lk2.source_id == lk1.source_id
        assert lk2.target_id == lk1.target_id
        assert lk2.kind == lk1.kind
        assert lk2.meta == lk1.meta
        assert lk2.created_at == lk1.created_at


class TestLinkRepr:
    def test_repr(self):
        lk = Link(
            source_id="t-aaa11111",
            source_type="task",
            target_id="g-bbb22222",
            target_type="goal",
            kind="relates_to",
        )
        r = repr(lk)
        assert "relates_to" in r
        assert "t-aaa11111" in r
        assert "g-bbb22222" in r
