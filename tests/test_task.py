"""Tests for the Task class."""

import pytest

from taskatlas._atlas import Atlas
from taskatlas._task import Task


class TestTaskCreation:
    def test_dict_construction(self):
        t = Task({"title": "Draft PRD", "stage": "active", "priority": "high"})
        assert t.title == "Draft PRD"
        assert t.stage == "active"
        assert t.priority == "high"
        assert t.id.startswith("t-")

    def test_kwargs_construction(self):
        t = Task(title="Draft PRD", stage="active")
        assert t.title == "Draft PRD"
        assert t.stage == "active"

    def test_defaults(self):
        t = Task({"title": "Minimal"})
        assert t.stage == "inbox"
        assert t.priority == "medium"
        assert t.tags == []
        assert t.notes == []
        assert t.parent_task_id is None
        assert t.child_task_ids == []
        assert t.goal_ids == []

    def test_with_tags(self):
        t = Task({"title": "Tagged", "tags": ["core", "api"]})
        assert t.tags == ["core", "api"]

    def test_invalid_stage_raises(self):
        with pytest.raises(ValueError, match="Invalid stage"):
            Task({"title": "Bad", "stage": "flying"})

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError, match="Invalid priority"):
            Task({"title": "Bad", "priority": "super"})

    def test_custom_id(self):
        t = Task({"id": "t-custom01", "title": "Custom"})
        assert t.id == "t-custom01"


class TestTaskEquality:
    def test_same_id_equal(self):
        t1 = Task({"id": "t-aaaaaaaa", "title": "A"})
        t2 = Task({"id": "t-aaaaaaaa", "title": "B"})
        assert t1 == t2

    def test_different_id_not_equal(self):
        t1 = Task({"title": "A"})
        t2 = Task({"title": "A"})
        assert t1 != t2

    def test_hash_consistent(self):
        t1 = Task({"id": "t-aaaaaaaa", "title": "A"})
        t2 = Task({"id": "t-aaaaaaaa", "title": "B"})
        assert hash(t1) == hash(t2)

    def test_not_equal_to_non_workitem(self):
        t = Task({"title": "A"})
        assert t != "not a task"


class TestTaskMove:
    def test_move_stage(self):
        t = Task({"title": "Work", "stage": "inbox"})
        t.move("active")
        assert t.stage == "active"

    def test_move_records_event(self):
        t = Task({"title": "Work", "stage": "inbox"})
        t.move("active", reason="Starting now")
        events = t.history()
        assert len(events) == 1
        assert events[0].event_type == "task_stage_changed"
        assert events[0].data["old_stage"] == "inbox"
        assert events[0].data["new_stage"] == "active"
        assert events[0].reason == "Starting now"

    def test_move_same_stage_noop(self):
        t = Task({"title": "Work", "stage": "active"})
        t.move("active")
        assert t.history() == []

    def test_move_invalid_stage_raises(self):
        t = Task({"title": "Work"})
        with pytest.raises(ValueError, match="Invalid stage"):
            t.move("flying")


class TestTaskPriority:
    def test_set_priority(self):
        t = Task({"title": "Work", "priority": "low"})
        t.set_priority("urgent", reason="Escalated")
        assert t.priority == "urgent"
        ev = t.history()[0]
        assert ev.event_type == "priority_changed"
        assert ev.data["old"] == "low"
        assert ev.data["new"] == "urgent"

    def test_set_same_priority_noop(self):
        t = Task({"title": "Work", "priority": "medium"})
        t.set_priority("medium")
        assert t.history() == []


class TestTaskNotes:
    def test_add_note(self):
        t = Task({"title": "Work"})
        entry = t.note("Important detail")
        assert entry["text"] == "Important detail"
        assert entry["id"].startswith("n-")
        assert len(t.notes) == 1

    def test_note_in_history(self):
        t = Task({"title": "Work"})
        t.note("First note")
        t.note("Second note")
        events = t.history(event_type="note_added")
        assert len(events) == 2

    def test_empty_note_raises(self):
        t = Task({"title": "Work"})
        with pytest.raises(ValueError, match="non-empty"):
            t.note("")


class TestTaskSubtasks:
    def test_add_subtask_dict(self):
        parent = Task({"title": "Parent"})
        child = parent.add_task({"title": "Child", "stage": "ready"})
        assert isinstance(child, Task)
        assert child.parent_task_id == parent.id
        assert child.id in parent.child_task_ids

    def test_add_subtask_instance(self):
        parent = Task({"title": "Parent"})
        child = Task({"title": "Child"})
        result = parent.add_task(child)
        assert result is child
        assert child.parent_task_id == parent.id

    def test_self_subtask_raises(self):
        t = Task({"id": "t-self0001", "title": "Self"})
        with pytest.raises(ValueError, match="cannot be its own"):
            t.add_task(t)

    def test_reparent_raises(self):
        p1 = Task({"title": "Parent1"})
        p2 = Task({"title": "Parent2"})
        child = Task({"title": "Child"})
        p1.add_task(child)
        with pytest.raises(ValueError, match="already has parent"):
            p2.add_task(child)


class TestTaskSerialization:
    def test_round_trip(self):
        t1 = Task({
            "title": "Work",
            "summary": "Do the thing",
            "stage": "active",
            "priority": "high",
            "tags": ["core"],
            "meta": {"source": "test"},
        })
        t1.note("A note")
        t1.move("review", reason="Done coding")

        d = t1.to_dict()
        t2 = Task.from_dict(d)

        assert t2.id == t1.id
        assert t2.title == t1.title
        assert t2.summary == t1.summary
        assert t2.stage == t1.stage
        assert t2.priority == t1.priority
        assert t2.tags == t1.tags
        assert t2.meta == t1.meta
        assert len(t2.notes) == 1
        assert len(t2._events) == 2

    def test_to_dict_contains_events(self):
        t = Task({"title": "Work"})
        t.move("active")
        d = t.to_dict()
        assert len(d["events"]) == 1
        assert d["events"][0]["event_type"] == "task_stage_changed"


class TestTaskContext:
    def test_compact(self):
        t = Task({"title": "Work", "stage": "active", "priority": "high", "tags": ["api"]})
        ctx = t.context()
        assert ctx["title"] == "Work"
        assert ctx["stage"] == "active"
        assert ctx["priority"] == "high"
        assert ctx["tags"] == ["api"]

    def test_full(self):
        t = Task({"title": "Work", "stage": "active"})
        t.note("detail")
        ctx = t.context(mode="full")
        assert "summary" in ctx
        assert "notes" in ctx
        assert "recent_events" in ctx

    def test_compact_includes_latest_note(self):
        t = Task({"title": "Work"})
        t.note("my note")
        ctx = t.context()
        assert ctx["latest_note"] == "my note"

    def test_invalid_mode_raises(self):
        t = Task({"title": "T"})
        with pytest.raises(ValueError, match="Invalid context mode"):
            t.context(mode="detailed")


class TestTaskPropertyGuards:
    def test_stage_rejects_invalid_value(self):
        t = Task({"title": "T"})
        with pytest.raises(ValueError, match="Invalid stage"):
            t.stage = "nonexistent"

    def test_stage_setter_emits_event(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T", "stage": "inbox"})
        t.stage = "active"
        assert t.stage == "active"
        assert any(e.event_type == "task_stage_changed" for e in t.history())

    def test_stage_setter_noop_on_same_value(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T", "stage": "inbox"})
        count_before = len(t._events)
        t.stage = "inbox"
        assert len(t._events) == count_before

    def test_priority_rejects_invalid_value(self):
        t = Task({"title": "T"})
        with pytest.raises(ValueError, match="Invalid priority"):
            t.priority = "garbage"

    def test_priority_setter_emits_event(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T", "priority": "low"})
        t.priority = "high"
        assert t.priority == "high"
        assert any(e.event_type == "priority_changed" for e in t.history())


class TestTaskFieldMutations:
    def test_set_title(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "Old"})
        t.set_title("New", reason="Clarified scope")
        assert t.title == "New"
        ev = t.history(event_type="title_changed")[0]
        assert ev.data["old"] == "Old"
        assert ev.data["new"] == "New"
        assert ev.reason == "Clarified scope"

    def test_set_title_noop_on_same(self):
        t = Task({"title": "Same"})
        count = len(t._events)
        t.set_title("Same")
        assert len(t._events) == count

    def test_set_summary(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T", "summary": "old"})
        t.set_summary("new", reason="Expanded")
        assert t.summary == "new"
        ev = t.history(event_type="summary_changed")[0]
        assert ev.data["old"] == "old"
        assert ev.data["new"] == "new"

    def test_add_tag(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T"})
        t.add_tag("backend")
        assert "backend" in t.tags
        ev = t.history(event_type="tag_added")[0]
        assert ev.data["tag"] == "backend"

    def test_add_tag_idempotent(self):
        t = Task({"title": "T", "tags": ["a"]})
        count = len(t._events)
        t.add_tag("a")
        assert len(t._events) == count

    def test_remove_tag(self):
        atlas = Atlas()
        t = atlas.add_task({"title": "T", "tags": ["api", "core"]})
        t.remove_tag("api")
        assert "api" not in t.tags
        ev = t.history(event_type="tag_removed")[0]
        assert ev.data["tag"] == "api"

    def test_remove_tag_not_present_raises(self):
        t = Task({"title": "T"})
        with pytest.raises(ValueError, match="not present"):
            t.remove_tag("nonexistent")


class TestTaskRepr:
    def test_repr(self):
        t = Task({"title": "Draft PRD"})
        r = repr(t)
        assert "Task" in r
        assert "Draft PRD" in r
