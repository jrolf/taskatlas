"""Tests for Atlas factory enforcement, actor provenance, cursors, diffs, and compaction."""

import pytest

import taskatlas as ta


class TestAtlasFactoryAndIsolation:
    def test_standalone_instantiation_rejected_with_guidance(self):
        with pytest.raises(TypeError, match="Cannot instantiate Dream directly"):
            ta.Dream({"title": "Unbound"})
        with pytest.raises(TypeError, match="Cannot instantiate Goal directly"):
            ta.Goal({"title": "Unbound"})
        with pytest.raises(TypeError, match="Cannot instantiate Task directly"):
            ta.Task({"title": "Unbound"})

    def test_ergonomic_creation_styles(self):
        a1 = ta.Atlas("Positional Name")
        a2 = ta.Atlas({"name": "Dict Name"})
        a3 = ta.Atlas(name="Kwarg Name")
        assert a1.name == "Positional Name"
        assert a2.name == "Dict Name"
        assert a3.name == "Kwarg Name"

        g1 = a1.add_goal("Goal Positional", priority="high")
        g2 = a1.add_goal({"title": "Goal Dict", "status": "active"})
        t1 = g2.add_task("Task Positional", stage="ready")
        assert g1.priority == "high"
        assert t1.stage == "ready"
        assert a1.get_entity(t1.id) is t1

    def test_custom_stages_removed_and_unknown_options_rejected(self):
        with pytest.raises(ValueError, match="Unknown Atlas option"):
            ta.Atlas("Bad", task_stages=["todo", "done"])

        atlas = ta.Atlas("Strict")
        with pytest.raises(ValueError, match="Unknown Task option"):
            atlas.add_task("Typo", priorty="high")

    def test_passing_instance_to_add_directs_to_attach(self):
        atlas = ta.Atlas("Add vs Attach")
        goal = atlas.add_goal("G")
        task = atlas.add_task("T")

        with pytest.raises(TypeError, match="attach_task"):
            goal.add_task(task)

    def test_cross_atlas_attachment_and_linking_rejected(self):
        a1 = ta.Atlas("One")
        a2 = ta.Atlas("Two")
        g1 = a1.add_goal("G1")
        t2 = a2.add_task("T2")

        with pytest.raises(ValueError, match="different Atlas"):
            g1.attach_task(t2)
        with pytest.raises(ValueError, match="different Atlas"):
            g1.link(t2, kind="relates_to")


class TestActorProvenance:
    def test_as_actor_context_stamps_events_and_notes(self):
        atlas = ta.Atlas("Provenance", actor="system:init")
        goal = atlas.add_goal("Core API")
        assert goal.history()[0].actor == "system:init"

        with atlas.as_actor("agent:planner"):
            task = goal.add_task("Draft endpoints", stage="ready")
            note = task.note("Using OpenAPI 3.1")
            assert note["actor"] == "agent:planner"
            assert task.history()[0].actor == "agent:planner"

            # Explicit call-site actor overrides active context
            task.move("active", reason="Picked up", actor="agent:builder")
            assert task.history()[0].actor == "agent:builder"

        # Context restores prior actor cleanly
        assert atlas.actor == "system:init"
        planner_events = atlas.get_events(actor="agent:planner")
        assert len(planner_events) >= 2


class TestTemporalCursorsAndDiffs:
    def test_cursor_and_events_since(self):
        atlas = ta.Atlas("Timeline")
        assert atlas.cursor is None

        g = atlas.add_goal("G", status="active")
        checkpoint = atlas.cursor
        assert checkpoint.startswith("ev-")

        t1 = g.add_task("T1", stage="ready")
        t1.move("active", reason="Started")

        delta = atlas.events_since(checkpoint)
        # Chronological (oldest first): task_created -> task_attached_to_goal -> task_stage_changed
        assert [e.event_type for e in delta] == [
            "task_created",
            "task_attached_to_goal",
            "task_stage_changed",
        ]

        with pytest.raises(KeyError, match="not found"):
            atlas.events_since("ev-deadbeef")

        # Timestamp cursor returns strictly newer events
        first_ts = atlas.events_since(None)[0].timestamp
        newer = atlas.events_since(first_ts)
        assert all(e.timestamp > first_ts for e in newer)

    def test_snapshot_diff_tracks_changes_and_unblocking(self):
        before = ta.Atlas("Snapshot")
        goal = before.add_goal("Launch", status="active")
        prereq = goal.add_task("Database migration", stage="active", priority="high")
        downstream = goal.add_task("Deploy service", stage="ready", priority="urgent")
        downstream.link(prereq, kind="depends_on")
        assert downstream.is_blocked is True

        after = before.copy()
        after_prereq = after.get_task(prereq.id)
        after_prereq.complete(
            "Migration applied cleanly",
            artifacts=["migrations/001.sql"],
        )
        added = after.get_goal(goal.id).add_task("Smoke test", stage="ready")
        added.note("Verify health endpoint")

        diff = before.diff(after)
        assert len(diff["tasks_added"]) == 1
        assert diff["tasks_added"][0]["id"] == added.id
        assert prereq.id in diff["task_changes"]
        assert diff["task_changes"][prereq.id]["stage"] == {
            "before": "active",
            "after": "done",
        }
        assert [u["id"] for u in diff["newly_unblocked_tasks"]] == [downstream.id]
        assert len(diff["notes_added"]) == 1
        assert diff["new_event_count"] >= 3


class TestAtlasCompaction:
    def test_compact_archives_and_prunes_safely(self):
        atlas = ta.Atlas("Long Running")
        g_done = atlas.add_goal("Old Milestone", status="achieved")
        t_done = g_done.add_task("Old Task", stage="ready")
        t_done.complete("Finished months ago")

        g_active = atlas.add_goal("Current Milestone", status="active")
        t_prereq_done = g_active.add_task("Shared Prereq", stage="ready")
        t_prereq_done.complete("Done, but active task still links to it")
        t_open = g_active.add_task("Open Task", stage="ready")
        t_open.link(t_prereq_done, kind="depends_on")

        report = atlas.compact(
            archive_terminal_tasks=True,
            archive_terminal_goals=True,
            prune_archived=True,
            keep_recent_events=5,
            actor="system:compactor",
        )

        # Old Milestone and Old Task had no active dependents -> pruned into ledger
        assert t_done.id not in atlas._tasks
        assert g_done.id not in atlas._goals
        assert report["pruned_tasks"] == 1
        assert report["pruned_goals"] == 1

        # t_prereq_done is archived, NOT pruned while g_active or t_open remains active
        assert t_prereq_done.id in atlas._tasks
        assert atlas.get_task(t_prereq_done.id).archived is True
        # Active goal retains completion credit (1/2 = 0.5) after compaction!
        assert g_active.progress()["done_count"] == 1
        assert g_active.progress()["done_ratio"] == 0.5
        assert atlas.meta["_compaction_ledger"]["done_tasks"] == 1
        assert atlas.meta["_compaction_ledger"]["achieved_goals"] == 1
        assert len(atlas.get_events()) <= 5

    def test_cross_wired_add_task_and_explicit_id_validation(self):
        atlas = ta.Atlas("Cross Wire")
        g1 = atlas.add_goal("G1")
        g2 = atlas.add_goal("G2")
        parent = g1.add_task("Parent")
        child = parent.add_task("Subtask also attached to G2", goal_ids=[g2.id])

        assert child.id in parent.child_task_ids
        assert child.id in g2.task_ids
        assert atlas.copy().get_task(child.id).parent_task_id == parent.id

        with pytest.raises(ValueError, match="Expected prefix"):
            atlas.add_task("Bad ID", id="ev-12345678")
        assert len(atlas.get_tasks()) == 2
