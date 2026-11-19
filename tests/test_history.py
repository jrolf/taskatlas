"""Tests for the unified single-source-of-truth Atlas event log."""

import taskatlas as ta


class TestSingleEventStoreAndChronology:
    def test_creation_events_precede_attachment_across_all_containers(self):
        atlas = ta.Atlas("Chronology")
        dream = atlas.add_dream("Dream")
        goal = dream.add_goal("Root Goal")
        subgoal = goal.add_goal("Subgoal")
        task = subgoal.add_task("Parent Task")
        subtask = task.add_task("Child Task")

        # Chronological sequence from oldest to newest
        chronological = atlas.events_since(None)
        event_pairs = [(e.event_type, e.entity_id) for e in chronological]

        assert event_pairs == [
            ("dream_created", dream.id),
            ("goal_created", goal.id),
            ("goal_attached_to_dream", dream.id),
            ("goal_created", subgoal.id),
            ("subgoal_added", goal.id),
            ("task_created", task.id),
            ("task_attached_to_goal", subgoal.id),
            ("task_created", subtask.id),
            ("subtask_added", task.id),
        ]

    def test_events_serialized_once_at_atlas_root(self):
        atlas = ta.Atlas("Single Store")
        goal = atlas.add_goal("G")
        task = goal.add_task("T")
        task.move("active", reason="Started")
        task.note("Progressing")

        payload = atlas.to_dict()
        assert len(payload["events"]) == 5
        assert "events" not in payload["goals"][goal.id]
        assert "events" not in payload["tasks"][task.id]
        assert len(task.history()) == 3
        assert [e.id for e in task.history()] == [
            e.id for e in atlas.get_events(entity_id=task.id)
        ]
