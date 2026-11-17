"""Tests for the canonical Link model and causal endpoint rules."""

import pytest

from taskatlas._link import Link


class TestLinkModel:
    def test_causal_depends_on_between_tasks_and_goals(self):
        lk = Link(
            source_id="t-aaa11111",
            source_type="task",
            target_id="g-bbb22222",
            target_type="goal",
            kind="depends_on",
            meta={"note": "needs milestone"},
        )
        assert lk.id.startswith("lk-")
        assert lk.kind == "depends_on"
        assert lk.meta["note"] == "needs milestone"

    def test_dream_disallowed_on_causal_depends_on(self):
        # Open-horizon Dreams cannot act as causal prerequisites or dependents
        with pytest.raises(ValueError, match="depends_on"):
            Link(
                source_id="t-aaa11111",
                source_type="task",
                target_id="d-ccc33333",
                target_type="dream",
                kind="depends_on",
            )

    def test_dream_allowed_on_non_blocking_links(self):
        lk = Link(
            source_id="d-aaa11111",
            source_type="dream",
            target_id="d-bbb22222",
            target_type="dream",
            kind="relates_to",
        )
        assert lk.kind == "relates_to"

    def test_link_is_immutable_and_rejects_removed_kinds(self):
        lk = Link(
            source_id="t-aaa11111",
            source_type="task",
            target_id="t-bbb22222",
            target_type="task",
            kind="derived_from",
        )
        with pytest.raises(AttributeError, match="immutable"):
            lk.kind = "depends_on"

        with pytest.raises(ValueError, match="Invalid link kind"):
            Link(
                source_id="t-aaa11111",
                source_type="task",
                target_id="t-bbb22222",
                target_type="task",
                kind="supports",
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
