"""Tests for Atlas query filtering across Dreams, Goals, and Tasks."""

import pytest

import taskatlas as ta


def _build_query_atlas():
    atlas = ta.Atlas("Filter Suite")
    d1 = atlas.add_dream("Research Lab", status="active", priority="high", tags=["ai"])
    d2 = atlas.add_dream("Idle Vision", status="active", priority="low")

    g1 = d1.add_goal("Ingestion", status="active", priority="urgent", tags=["data"])
    sub_g = g1.add_goal("Connectors", status="active", priority="high")
    g_standalone = atlas.add_goal("Maintenance", status="proposed", priority="low")

    t1 = sub_g.add_task("Kafka source", stage="active", priority="urgent", tags=["kafka", "core"])
    sub_t = t1.add_task("Offset commit", stage="ready", priority="high", tags=["kafka"])
    t2 = g_standalone.add_task("Rotate logs", stage="ready", priority="low", tags=["ops"])
    t2.hold("Waiting on cron window")

    t_arch = g_standalone.add_task("Old script", stage="inbox")
    t_arch.cancel("Obsolete", archive=True)

    t1.claim("agent:w1")
    return atlas, d1, d2, g1, sub_g, g_standalone, t1, sub_t, t2, t_arch


class TestTransitiveAndStateFiltering:
    def test_transitive_dream_and_goal_filters(self):
        atlas, d1, _, g1, sub_g, _, t1, sub_t, t2, _ = _build_query_atlas()

        # Querying by root goal g1 finds tasks under child sub_g and nested sub_t!
        g1_tasks = atlas.get_tasks(goal_id=g1.id)
        assert set(g1_tasks) == {t1, sub_t}

        # Querying by dream d1 finds both g1 and sub_g, and both t1 and sub_t!
        assert set(atlas.get_goals(dream_id=d1.id)) == {g1, sub_g}
        assert set(atlas.get_tasks(dream_id=d1.id)) == {t1, sub_t}

        # Tasks without any dream or without any goal
        assert atlas.get_tasks(dream_id=None) == [t2]
        orphan = atlas.add_task("Unattached chore", stage="inbox")
        assert atlas.get_tasks(goal_id=None) == [orphan]

    def test_stalled_blocked_held_and_claimed_filters(self):
        atlas, d1, d2, _, _, _, t1, _, t2, _ = _build_query_atlas()

        assert atlas.get_dreams(stalled=True) == [d2]
        assert atlas.get_dreams(stalled=False) == [d1]
        assert atlas.get_tasks(blocked=True) == [t2]
        assert atlas.get_tasks(held=True) == [t2]
        assert atlas.get_tasks(claimed=True) == [t1]
        assert atlas.get_tasks(owner="agent:w1") == [t1]

    def test_archived_modes_and_callable_where(self):
        atlas, *_, t_arch = _build_query_atlas()

        assert t_arch not in atlas.get_tasks()
        assert atlas.get_tasks(archived=True) == [t_arch]
        assert t_arch in atlas.get_tasks(archived=None)

        kafka_only = atlas.get_tasks(where=lambda t: "Offset" in t.title)
        assert len(kafka_only) == 1

    def test_sorting_direction_and_validation(self):
        atlas, *_ = _build_query_atlas()

        desc = atlas.get_tasks(order_by="priority")
        asc = atlas.get_tasks(order_by="priority", descending=False)
        assert desc[0].priority == "urgent"
        assert asc[0].priority == "low"

        with pytest.raises(ValueError, match="Unknown filter key"):
            atlas.get_tasks(nonexistent=True)
