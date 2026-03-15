"""Tests for the Goal class."""

import pytest

from taskatlas._atlas import Atlas
from taskatlas._goal import Goal
from taskatlas._task import Task


class TestGoalCreation:
    def test_dict_construction(self):
        g = Goal({"title": "Ship v0", "status": "active", "priority": "high"})
        assert g.title == "Ship v0"
        assert g.status == "active"
        assert g.priority == "high"
        assert g.id.startswith("g-")

    def test_kwargs_construction(self):
        g = Goal(title="Ship v0", status="active")
        assert g.title == "Ship v0"

    def test_defaults(self):
        g = Goal({"title": "Minimal"})
        assert g.status == "proposed"
        assert g.priority == "medium"
        assert g.tags == []
        assert g.task_ids == []
        assert g.child_goal_ids == []
        assert g.parent_goal_id is None

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Invalid status"):
            Goal({"title": "Bad", "status": "flying"})

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError, match="Invalid priority"):
            Goal({"title": "Bad", "priority": "mega"})


class TestGoalEquality:
    def test_same_id_equal(self):
        g1 = Goal({"id": "g-aaaaaaaa", "title": "A"})
        g2 = Goal({"id": "g-aaaaaaaa", "title": "B"})
        assert g1 == g2

    def test_goal_not_equal_to_task(self):
        g = Goal({"id": "g-aaaaaaaa", "title": "A"})
        t = Task({"id": "t-aaaaaaaa", "title": "A"})
        assert g != t

    def test_hash_consistent(self):
        g1 = Goal({"id": "g-aaaaaaaa", "title": "A"})
        g2 = Goal({"id": "g-aaaaaaaa", "title": "B"})
        assert hash(g1) == hash(g2)


class TestGoalStatus:
    def test_set_status(self):
        g = Goal({"title": "G", "status": "proposed"})
        g.set_status("active", reason="Approved")
        assert g.status == "active"
        ev = g.history()[0]
        assert ev.event_type == "goal_status_changed"
        assert ev.data["old_status"] == "proposed"
        assert ev.data["new_status"] == "active"
        assert ev.reason == "Approved"

    def test_same_status_noop(self):
        g = Goal({"title": "G", "status": "active"})
        g.set_status("active")
        assert g.history() == []

    def test_invalid_status_raises(self):
        g = Goal({"title": "G"})
        with pytest.raises(ValueError, match="Invalid status"):
            g.set_status("invented")


class TestGoalTaskAttachment:
    def test_add_task_dict(self):
        g = Goal({"title": "G"})
        t = g.add_task({"title": "T", "stage": "ready"})
        assert isinstance(t, Task)
        assert t.id in g.task_ids
        assert g.id in t.goal_ids

    def test_add_task_instance(self):
        g = Goal({"title": "G"})
        t = Task({"title": "T"})
        result = g.add_task(t)
        assert result is t
        assert t.id in g.task_ids
        assert g.id in t.goal_ids

    def test_attach_task(self):
        g = Goal({"title": "G"})
        t = Task({"title": "T"})
        g.attach_task(t)
        assert t.id in g.task_ids
        assert g.id in t.goal_ids

    def test_detach_task(self):
        g = Goal({"title": "G"})
        t = Task({"title": "T"})
        g.add_task(t)
        g.detach_task(t)
        assert t.id not in g.task_ids
        assert g.id not in t.goal_ids

    def test_add_task_records_event(self):
        g = Goal({"title": "G"})
        g.add_task({"title": "T"})
        events = g.history(event_type="task_attached_to_goal")
        assert len(events) == 1

    def test_duplicate_attach_idempotent(self):
        g = Goal({"title": "G"})
        t = Task({"title": "T"})
        g.add_task(t)
        g.add_task(t)
        assert g.task_ids.count(t.id) == 1


class TestGoalSubgoals:
    def test_add_subgoal_dict(self):
        parent = Goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})
        assert isinstance(child, Goal)
        assert child.parent_goal_id == parent.id
        assert child.id in parent.child_goal_ids

    def test_add_subgoal_instance(self):
        parent = Goal({"title": "Parent"})
        child = Goal({"title": "Child"})
        result = parent.add_goal(child)
        assert result is child
        assert child.parent_goal_id == parent.id

    def test_self_subgoal_raises(self):
        g = Goal({"id": "g-self0001", "title": "Self"})
        with pytest.raises(ValueError, match="cannot be its own"):
            g.add_goal(g)

    def test_reparent_raises(self):
        p1 = Goal({"title": "P1"})
        p2 = Goal({"title": "P2"})
        child = Goal({"title": "Child"})
        p1.add_goal(child)
        with pytest.raises(ValueError, match="already has parent"):
            p2.add_goal(child)


class TestGoalNotes:
    def test_add_note(self):
        g = Goal({"title": "G"})
        entry = g.note("Keep it lightweight")
        assert entry["text"] == "Keep it lightweight"
        assert len(g.notes) == 1


class TestGoalSerialization:
    def test_round_trip(self):
        g1 = Goal({
            "title": "Ship v0",
            "summary": "Get it out",
            "status": "active",
            "priority": "high",
            "tags": ["core"],
        })
        g1.note("Important")
        g1.set_status("paused", reason="Blocked")

        d = g1.to_dict()
        g2 = Goal.from_dict(d)

        assert g2.id == g1.id
        assert g2.title == g1.title
        assert g2.status == g1.status
        assert g2.priority == g1.priority
        assert len(g2.notes) == 1
        assert len(g2._events) == 2


class TestGoalContext:
    def test_compact(self):
        g = Goal({"title": "G", "status": "active", "priority": "high"})
        ctx = g.context()
        assert ctx["title"] == "G"
        assert ctx["status"] == "active"

    def test_full(self):
        g = Goal({"title": "G"})
        g.note("note")
        ctx = g.context(mode="full")
        assert "summary" in ctx
        assert "progress" in ctx
        assert "notes" in ctx

    def test_compact_task_count(self):
        g = Goal({"title": "G"})
        t = Task({"title": "T"})
        g.add_task(t)
        ctx = g.context()
        assert ctx["task_count"] == 1


class TestGoalContextValidation:
    def test_invalid_mode_raises(self):
        g = Goal({"title": "G"})
        with pytest.raises(ValueError, match="Invalid context mode"):
            g.context(mode="everything")


class TestGoalDetachTaskPhantom:
    def test_detach_non_attached_task_is_noop(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})
        count = len(g._events)
        g.detach_task(t)
        assert len(g._events) == count


class TestGoalPropertyGuards:
    def test_status_rejects_invalid_value(self):
        g = Goal({"title": "G"})
        with pytest.raises(ValueError, match="Invalid status"):
            g.status = "nonexistent"

    def test_status_setter_emits_event(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "G", "status": "proposed"})
        g.status = "active"
        assert g.status == "active"
        assert any(e.event_type == "goal_status_changed" for e in g.history())

    def test_status_setter_noop_on_same_value(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "G", "status": "proposed"})
        count_before = len(g._events)
        g.status = "proposed"
        assert len(g._events) == count_before

    def test_priority_rejects_invalid_value(self):
        g = Goal({"title": "G"})
        with pytest.raises(ValueError, match="Invalid priority"):
            g.priority = "garbage"


class TestGoalFieldMutations:
    def test_set_title(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "Old"})
        g.set_title("New", reason="Renamed")
        assert g.title == "New"
        ev = g.history(event_type="title_changed")[0]
        assert ev.data["old"] == "Old"
        assert ev.data["new"] == "New"

    def test_add_tag(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "G"})
        g.add_tag("core")
        assert "core" in g.tags
        ev = g.history(event_type="tag_added")[0]
        assert ev.data["tag"] == "core"

    def test_remove_tag(self):
        atlas = Atlas()
        g = atlas.add_goal({"title": "G", "tags": ["core", "api"]})
        g.remove_tag("core")
        assert "core" not in g.tags


class TestGoalRepr:
    def test_repr(self):
        g = Goal({"title": "Ship v0"})
        r = repr(g)
        assert "Goal" in r
        assert "Ship v0" in r
