"""Integration tests for automatic history / event generation."""

import taskatlas as ta


class TestAutomaticEvents:
    def test_goal_created_event(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        events = atlas.get_events(entity_id=g.id)
        assert any(e.event_type == "goal_created" for e in events)

    def test_task_created_event(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T"})
        events = atlas.get_events(entity_id=t.id)
        assert any(e.event_type == "task_created" for e in events)

    def test_stage_change_event(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T", "stage": "inbox"})
        t.move("active", reason="Starting now")

        ev = t.history(event_type="task_stage_changed")[0]
        assert ev.data["old_stage"] == "inbox"
        assert ev.data["new_stage"] == "active"
        assert ev.reason == "Starting now"
        assert ev.entity_id == t.id

    def test_status_change_event(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G", "status": "proposed"})
        g.set_status("active", reason="Approved")

        ev = g.history(event_type="goal_status_changed")[0]
        assert ev.data["old_status"] == "proposed"
        assert ev.data["new_status"] == "active"

    def test_priority_change_event(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T", "priority": "low"})
        t.set_priority("urgent", reason="Escalated")

        ev = t.history(event_type="priority_changed")[0]
        assert ev.data["old"] == "low"
        assert ev.data["new"] == "urgent"

    def test_note_added_event(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T"})
        entry = t.note("Important detail")

        ev = t.history(event_type="note_added")[0]
        assert ev.data["note_id"] == entry["id"]

    def test_task_attached_to_goal_event(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = g.add_task({"title": "T"})

        ev = g.history(event_type="task_attached_to_goal")[0]
        assert ev.data["task_id"] == t.id

    def test_subtask_added_event(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})

        ev = parent.history(event_type="subtask_added")[0]
        assert ev.data["child_id"] == child.id

    def test_subgoal_added_event(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})

        ev = parent.history(event_type="subgoal_added")[0]
        assert ev.data["child_id"] == child.id

    def test_link_added_event(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        lk = t1.link(t2, kind="blocks")

        ev = t1.history(event_type="link_added")[0]
        assert ev.data["link_id"] == lk.id
        assert ev.data["kind"] == "blocks"

    def test_link_removed_event(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        t1.link(t2, kind="blocks")
        t1.unlink(target=t2)

        ev = t1.history(event_type="link_removed")[0]
        assert ev.data["kind"] == "blocks"


class TestCreationEventConsistency:
    """Verify creation events fire from all creation paths and appear in
    both entity history and atlas event log."""

    def test_task_created_via_goal_add_task(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = g.add_task({"title": "T"})
        assert any(e.event_type == "task_created" for e in t.history())
        assert any(
            e.event_type == "task_created" and e.entity_id == t.id
            for e in atlas.get_events()
        )

    def test_task_created_via_task_add_task(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})
        assert any(e.event_type == "task_created" for e in child.history())
        assert any(
            e.event_type == "task_created" and e.entity_id == child.id
            for e in atlas.get_events()
        )

    def test_goal_created_via_goal_add_goal(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})
        assert any(e.event_type == "goal_created" for e in child.history())
        assert any(
            e.event_type == "goal_created" and e.entity_id == child.id
            for e in atlas.get_events()
        )

    def test_entity_history_matches_atlas_events(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T"})
        t.move("active", reason="go")
        t.note("hello")

        entity_types = {e.event_type for e in t.history()}
        atlas_types = {
            e.event_type
            for e in atlas.get_events(entity_id=t.id)
        }
        assert entity_types == atlas_types

    def test_goal_add_task_emits_both_created_and_attached(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = g.add_task({"title": "T"})
        atlas_types = [e.event_type for e in atlas.get_events()]
        assert "task_created" in atlas_types
        assert "task_attached_to_goal" in atlas_types

    def test_creation_event_has_title_data(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "My Task"})
        ev = t.history(event_type="task_created")[0]
        assert ev.data["title"] == "My Task"


class TestEventRetrieval:
    def test_entity_history_newest_first(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T"})
        t.note("first")
        t.note("second")
        t.move("active")

        history = t.history()
        assert history[0].event_type == "task_stage_changed"
        assert history[-1].event_type == "task_created"

    def test_entity_history_with_limit(self):
        atlas = ta.Atlas()
        t = atlas.add_task({"title": "T"})
        for i in range(10):
            t.note(f"note {i}")

        history = t.history(limit=3)
        assert len(history) == 3

    def test_atlas_get_events_newest_first(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})
        t.move("active")

        events = atlas.get_events()
        assert events[0].event_type == "task_stage_changed"

    def test_atlas_get_events_by_type(self):
        atlas = ta.Atlas()
        atlas.add_goal({"title": "G"})
        atlas.add_task({"title": "T"})

        goal_events = atlas.get_events(event_type="goal_created")
        assert len(goal_events) == 1

    def test_atlas_recent(self):
        atlas = ta.Atlas()
        for i in range(25):
            atlas.add_task({"title": f"T{i}"})
        recent = atlas.recent(limit=5)
        assert len(recent) == 5

    def test_mutations_propagate_to_atlas_events(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})
        g.attach_task(t)
        t.move("active")
        t.note("detail")

        all_events = atlas.get_events()
        types = {e.event_type for e in all_events}
        assert "goal_created" in types
        assert "task_created" in types
        assert "task_attached_to_goal" in types
        assert "task_stage_changed" in types
        assert "note_added" in types
