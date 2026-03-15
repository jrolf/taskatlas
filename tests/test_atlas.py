"""Tests for the Atlas class."""

import pytest

from taskatlas._atlas import Atlas
from taskatlas._goal import Goal
from taskatlas._task import Task


class TestAtlasCreation:
    def test_basic(self):
        a = Atlas({"name": "My Atlas"})
        assert a.name == "My Atlas"
        assert a.created_at
        assert a._goals == {}
        assert a._tasks == {}

    def test_kwargs(self):
        a = Atlas(name="My Atlas")
        assert a.name == "My Atlas"

    def test_defaults(self):
        a = Atlas()
        assert a.name == ""
        assert len(a.task_stages) == 7
        assert len(a.goal_statuses) == 5

    def test_custom_stages(self):
        a = Atlas({"task_stages": ["todo", "doing", "done"]})
        assert a.task_stages == ("todo", "doing", "done")

    def test_repr(self):
        a = Atlas({"name": "Test"})
        assert "Test" in repr(a)


class TestAtlasAddGoal:
    def test_add_goal_dict(self):
        a = Atlas()
        g = a.add_goal({"title": "Ship v0", "priority": "high"})
        assert isinstance(g, Goal)
        assert g.id in a._goals
        assert g._atlas is a

    def test_add_goal_instance(self):
        a = Atlas()
        g = Goal({"title": "Ship v0"})
        result = a.add_goal(g)
        assert result is g
        assert g._atlas is a

    def test_add_goal_emits_event(self):
        a = Atlas()
        g = a.add_goal({"title": "Ship v0"})
        events = a.get_events(event_type="goal_created")
        assert len(events) == 1
        assert events[0].entity_id == g.id

    def test_duplicate_same_instance_ok(self):
        a = Atlas()
        g = Goal({"title": "G"})
        a.add_goal(g)
        result = a.add_goal(g)
        assert result is g

    def test_duplicate_different_instance_raises(self):
        a = Atlas()
        a.add_goal({"id": "g-dup00001", "title": "First"})
        with pytest.raises(ValueError, match="already exists"):
            a.add_goal({"id": "g-dup00001", "title": "Second"})

    def test_add_goal_invalid_type_raises(self):
        a = Atlas()
        with pytest.raises(TypeError):
            a.add_goal(42)


class TestAtlasAddTask:
    def test_add_task_dict(self):
        a = Atlas()
        t = a.add_task({"title": "Draft PRD"})
        assert isinstance(t, Task)
        assert t.id in a._tasks
        assert t._atlas is a

    def test_add_task_instance(self):
        a = Atlas()
        t = Task({"title": "Draft PRD"})
        result = a.add_task(t)
        assert result is t

    def test_add_task_emits_event(self):
        a = Atlas()
        t = a.add_task({"title": "Work"})
        events = a.get_events(event_type="task_created")
        assert len(events) == 1
        assert events[0].entity_id == t.id


class TestAtlasRetrieval:
    def test_get_goal(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        assert a.get_goal(g.id) is g

    def test_get_task(self):
        a = Atlas()
        t = a.add_task({"title": "T"})
        assert a.get_task(t.id) is t

    def test_get_goal_not_found(self):
        a = Atlas()
        with pytest.raises(KeyError, match="No goal"):
            a.get_goal("g-nonexist")

    def test_get_task_not_found(self):
        a = Atlas()
        with pytest.raises(KeyError, match="No task"):
            a.get_task("t-nonexist")

    def test_same_instance_returned(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        assert a.get_goal(g.id) is g

    def test_get_goals_filtered(self):
        a = Atlas()
        a.add_goal({"title": "A", "status": "active", "priority": "high"})
        a.add_goal({"title": "B", "status": "proposed", "priority": "low"})
        result = a.get_goals(status="active")
        assert len(result) == 1
        assert result[0].title == "A"

    def test_get_tasks_filtered(self):
        a = Atlas()
        a.add_task({"title": "A", "stage": "active", "priority": "high"})
        a.add_task({"title": "B", "stage": "inbox", "priority": "low"})
        result = a.get_tasks(stage="active")
        assert len(result) == 1
        assert result[0].title == "A"

    def test_get_tasks_by_goal_id(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        t1 = a.add_task({"title": "T1"})
        t2 = a.add_task({"title": "T2"})
        g.attach_task(t1)
        result = a.get_tasks(goal_id=g.id)
        assert len(result) == 1
        assert result[0].id == t1.id

    def test_get_tasks_ordered(self):
        a = Atlas()
        a.add_task({"title": "Low", "priority": "low"})
        a.add_task({"title": "Urgent", "priority": "urgent"})
        a.add_task({"title": "High", "priority": "high"})
        result = a.get_tasks(order_by="priority")
        assert result[0].title == "Urgent"
        assert result[1].title == "High"


class TestAtlasEvents:
    def test_get_events(self):
        a = Atlas()
        a.add_goal({"title": "G"})
        a.add_task({"title": "T"})
        events = a.get_events()
        assert len(events) == 2

    def test_get_events_by_entity(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        a.add_task({"title": "T"})
        events = a.get_events(entity_id=g.id)
        assert len(events) == 1

    def test_recent(self):
        a = Atlas()
        for i in range(30):
            a.add_task({"title": f"T{i}"})
        recent = a.recent(limit=5)
        assert len(recent) == 5

    def test_mutation_events_in_atlas(self):
        a = Atlas()
        t = a.add_task({"title": "Work"})
        t.move("active", reason="Starting")
        events = a.get_events(entity_id=t.id)
        types = [e.event_type for e in events]
        assert "task_created" in types
        assert "task_stage_changed" in types


class TestAtlasGoalTaskIntegration:
    def test_goal_add_task_registers_in_atlas(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        t = g.add_task({"title": "T"})
        assert t.id in a._tasks
        assert t._atlas is a

    def test_task_add_subtask_registers_in_atlas(self):
        a = Atlas()
        t1 = a.add_task({"title": "Parent"})
        t2 = t1.add_task({"title": "Child"})
        assert t2.id in a._tasks
        assert t2._atlas is a

    def test_goal_add_subgoal_registers_in_atlas(self):
        a = Atlas()
        g1 = a.add_goal({"title": "Parent"})
        g2 = g1.add_goal({"title": "Child"})
        assert g2.id in a._goals
        assert g2._atlas is a

    def test_goal_get_tasks_returns_objects(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        t1 = g.add_task({"title": "T1"})
        t2 = g.add_task({"title": "T2"})
        tasks = g.get_tasks()
        assert len(tasks) == 2
        assert t1 in tasks
        assert t2 in tasks

    def test_task_get_subtasks_returns_objects(self):
        a = Atlas()
        t1 = a.add_task({"title": "Parent"})
        t2 = t1.add_task({"title": "Child"})
        children = t1.get_tasks()
        assert len(children) == 1
        assert children[0] is t2

    def test_attach_task_by_id(self):
        a = Atlas()
        g = a.add_goal({"title": "G"})
        t = a.add_task({"title": "T"})
        g.attach_task(t.id)
        assert t.id in g.task_ids
        assert g.id in t.goal_ids
