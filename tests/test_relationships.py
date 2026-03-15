"""Integration tests for relationships — containment, attachment, and typed links."""

import pytest

import taskatlas as ta


class TestGoalTaskAttachment:
    def test_goal_add_task_registers_both(self):
        atlas = ta.Atlas({"name": "R"})
        goal = ta.Goal({"title": "Ship v0", "status": "active"})
        atlas.add_goal(goal)

        task = goal.add_task({"title": "Define API", "stage": "ready"})

        assert task.id in atlas._tasks
        assert task.id in goal.task_ids
        assert goal.id in task.goal_ids

    def test_task_attached_to_multiple_goals(self):
        atlas = ta.Atlas()
        g1 = atlas.add_goal({"title": "G1"})
        g2 = atlas.add_goal({"title": "G2"})
        task = atlas.add_task({"title": "Shared work"})

        g1.attach_task(task)
        g2.attach_task(task)

        assert g1.id in task.goal_ids
        assert g2.id in task.goal_ids
        assert task.id in g1.task_ids
        assert task.id in g2.task_ids

    def test_detach_task_cleans_both(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})
        g.attach_task(t)
        g.detach_task(t)

        assert t.id not in g.task_ids
        assert g.id not in t.goal_ids

    def test_attach_by_id_string(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})
        g.attach_task(t.id)

        assert t.id in g.task_ids
        assert g.id in t.goal_ids

    def test_attach_by_id_requires_atlas(self):
        g = ta.Goal({"title": "G"})
        with pytest.raises(ValueError, match="not registered"):
            g.attach_task("t-someid01")


class TestGoalHierarchy:
    def test_subgoal_parent_child(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})

        assert child.parent_goal_id == parent.id
        assert child.id in parent.child_goal_ids
        assert child.id in atlas._goals

    def test_nested_subgoals(self):
        atlas = ta.Atlas()
        g1 = atlas.add_goal({"title": "Level 1"})
        g2 = g1.add_goal({"title": "Level 2"})
        g3 = g2.add_goal({"title": "Level 3"})

        assert g3.parent_goal_id == g2.id
        assert g2.parent_goal_id == g1.id

    def test_get_child_goals(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        c1 = parent.add_goal({"title": "C1"})
        c2 = parent.add_goal({"title": "C2"})

        children = parent.get_goals()
        assert len(children) == 2
        assert c1 in children
        assert c2 in children


class TestTaskHierarchy:
    def test_subtask_parent_child(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})

        assert child.parent_task_id == parent.id
        assert child.id in parent.child_task_ids
        assert child.id in atlas._tasks

    def test_nested_subtasks(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "L1"})
        t2 = t1.add_task({"title": "L2"})
        t3 = t2.add_task({"title": "L3"})

        assert t3.parent_task_id == t2.id
        assert t2.parent_task_id == t1.id


class TestTypedLinks:
    def test_task_to_task_link(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})

        lk = t1.link(t2, kind="depends_on")
        assert lk.source_id == t1.id
        assert lk.target_id == t2.id
        assert lk.kind == "depends_on"
        assert lk.id in atlas._links

    def test_goal_to_task_link(self):
        atlas = ta.Atlas()
        g = atlas.add_goal({"title": "G"})
        t = atlas.add_task({"title": "T"})

        lk = g.link(t, kind="supports")
        assert lk.source_type == "goal"
        assert lk.target_type == "task"

    def test_goal_to_goal_link(self):
        atlas = ta.Atlas()
        g1 = atlas.add_goal({"title": "G1"})
        g2 = atlas.add_goal({"title": "G2"})

        lk = g1.link(g2, kind="relates_to")
        assert lk.kind == "relates_to"

    def test_link_with_meta(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        lk = t1.link(t2, kind="blocks", meta={"severity": "critical"})
        assert lk.meta["severity"] == "critical"

    def test_get_links(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        t3 = atlas.add_task({"title": "T3"})

        t1.link(t2, kind="depends_on")
        t1.link(t3, kind="relates_to")

        links = t1.get_links()
        assert len(links) == 2

    def test_unlink_by_target(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        t3 = atlas.add_task({"title": "T3"})

        t1.link(t2, kind="depends_on")
        t1.link(t3, kind="relates_to")

        removed = t1.unlink(target=t2)
        assert removed == 1
        assert len(t1.get_links()) == 1

    def test_unlink_by_kind(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})
        t3 = atlas.add_task({"title": "T3"})

        t1.link(t2, kind="depends_on")
        t1.link(t3, kind="depends_on")

        removed = t1.unlink(kind="depends_on")
        assert removed == 2
        assert len(t1.get_links()) == 0

    def test_link_invalid_kind_raises(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "T1"})
        t2 = atlas.add_task({"title": "T2"})

        with pytest.raises(ValueError, match="Invalid link kind"):
            t1.link(t2, kind="invented")

    def test_containment_separate_from_links(self):
        """Subtask structure must not appear as links."""
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})

        assert child.parent_task_id == parent.id
        assert len(parent.get_links()) == 0


class TestSubtaskDetachment:
    def test_detach_subtask(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})
        parent.detach_task(child)
        assert child.parent_task_id is None
        assert child.id not in parent.child_task_ids
        assert child.id in atlas._tasks  # still in atlas

    def test_detach_subtask_emits_event(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})
        parent.detach_task(child)
        ev = parent.history(event_type="subtask_detached")[0]
        assert ev.data["child_id"] == child.id

    def test_detach_subtask_by_id(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        child = parent.add_task({"title": "Child"})
        parent.detach_task(child.id)
        assert child.parent_task_id is None

    def test_detach_nonchild_is_noop(self):
        atlas = ta.Atlas()
        parent = atlas.add_task({"title": "Parent"})
        other = atlas.add_task({"title": "Other"})
        count = len(parent._events)
        parent.detach_task(other)
        assert len(parent._events) == count

    def test_detach_and_reattach_to_new_parent(self):
        atlas = ta.Atlas()
        p1 = atlas.add_task({"title": "P1"})
        p2 = atlas.add_task({"title": "P2"})
        child = p1.add_task({"title": "Child"})
        p1.detach_task(child)
        p2.add_task(child)
        assert child.parent_task_id == p2.id
        assert child.id in p2.child_task_ids


class TestSubgoalDetachment:
    def test_detach_subgoal(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})
        parent.detach_goal(child)
        assert child.parent_goal_id is None
        assert child.id not in parent.child_goal_ids
        assert child.id in atlas._goals

    def test_detach_subgoal_emits_event(self):
        atlas = ta.Atlas()
        parent = atlas.add_goal({"title": "Parent"})
        child = parent.add_goal({"title": "Child"})
        parent.detach_goal(child)
        ev = parent.history(event_type="subgoal_detached")[0]
        assert ev.data["child_id"] == child.id


class TestLinkDeduplication:
    def test_duplicate_link_returns_existing(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "A"})
        t2 = atlas.add_task({"title": "B"})
        lk1 = t1.link(t2, kind="depends_on")
        lk2 = t1.link(t2, kind="depends_on")
        assert lk1 is lk2
        assert len(atlas._links) == 1

    def test_different_kind_not_deduplicated(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "A"})
        t2 = atlas.add_task({"title": "B"})
        t1.link(t2, kind="depends_on")
        t1.link(t2, kind="relates_to")
        assert len(atlas._links) == 2


class TestLinkFiltering:
    def test_get_links_by_kind(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "A"})
        t2 = atlas.add_task({"title": "B"})
        t3 = atlas.add_task({"title": "C"})
        t1.link(t2, kind="depends_on")
        t1.link(t3, kind="blocks")
        assert len(t1.get_links(kind="depends_on")) == 1
        assert len(t1.get_links(kind="blocks")) == 1

    def test_get_links_outgoing(self):
        atlas = ta.Atlas()
        t1 = atlas.add_task({"title": "A"})
        t2 = atlas.add_task({"title": "B"})
        t1.link(t2, kind="depends_on")
        assert len(t1.get_links(direction="outgoing")) == 1
        assert len(t1.get_links(direction="incoming")) == 0
        assert len(t2.get_links(direction="incoming")) == 1
        assert len(t2.get_links(direction="outgoing")) == 0

    def test_get_blockers(self):
        atlas = ta.Atlas()
        a = atlas.add_task({"title": "A"})
        b = atlas.add_task({"title": "B"})
        c = atlas.add_task({"title": "C"})
        b.link(a, kind="blocks")
        a.link(c, kind="depends_on")
        blockers = a.get_blockers()
        assert len(blockers) == 2

    def test_get_dependents(self):
        atlas = ta.Atlas()
        a = atlas.add_task({"title": "A"})
        b = atlas.add_task({"title": "B"})
        b.link(a, kind="depends_on")
        deps = a.get_dependents()
        assert len(deps) == 1
        assert deps[0].source_id == b.id
