"""Tests for view rendering — board, tree, queue, summary."""

import pytest

from taskatlas._atlas import Atlas
from taskatlas._goal import Goal
from taskatlas._task import Task


def _populated_atlas():
    """Build an atlas with goals, tasks, subtasks for view tests."""
    a = Atlas({"name": "View Tests"})

    g1 = a.add_goal({"title": "Ship v0", "status": "active", "priority": "high"})
    g2 = a.add_goal({"title": "Write docs", "status": "proposed", "priority": "medium"})

    t1 = a.add_task({"title": "Define API", "stage": "active", "priority": "high", "tags": ["core"]})
    t2 = a.add_task({"title": "Build models", "stage": "ready", "priority": "high", "tags": ["core"]})
    t3 = a.add_task({"title": "Write tests", "stage": "inbox", "priority": "medium"})
    t4 = a.add_task({"title": "Review PR", "stage": "done", "priority": "low"})

    g1.attach_task(t1)
    g1.attach_task(t2)
    g2.attach_task(t3)

    sub1 = t2.add_task({"title": "Define Task class", "stage": "active", "priority": "high"})
    sub2 = t2.add_task({"title": "Define Goal class", "stage": "ready", "priority": "medium"})

    return a, g1, g2, t1, t2, t3, t4, sub1, sub2


class TestBoardView:
    def test_basic_board(self):
        a, *_ = _populated_atlas()
        board = a.board()
        assert "stages" in board
        assert "active" in board["stages"]
        assert "inbox" in board["stages"]

    def test_board_excludes_archived(self):
        a, *_ = _populated_atlas()
        t = a.add_task({"title": "Old", "stage": "inbox"})
        t.move("archived")
        board = a.board()
        all_ids = []
        for tasks in board["stages"].values():
            all_ids.extend(t["id"] for t in tasks)
        assert t.id not in all_ids

    def test_board_scoped_to_goal(self):
        a, g1, g2, t1, t2, t3, *_ = _populated_atlas()
        board = a.board(goal_id=g1.id)
        all_ids = []
        for tasks in board["stages"].values():
            all_ids.extend(t["id"] for t in tasks)
        assert t1.id in all_ids
        assert t2.id in all_ids
        assert t3.id not in all_ids

    def test_board_invalid_goal_raises(self):
        a = Atlas()
        with pytest.raises(KeyError):
            a.board(goal_id="g-nonexist")

    def test_board_task_summaries_have_fields(self):
        a, *_ = _populated_atlas()
        board = a.board()
        for tasks in board["stages"].values():
            for t in tasks:
                assert "id" in t
                assert "title" in t
                assert "priority" in t


class TestTreeView:
    def test_tree_has_goals(self):
        a, g1, *_ = _populated_atlas()
        tree = a.tree()
        assert "goals" in tree
        goal_ids = [g["id"] for g in tree["goals"]]
        assert g1.id in goal_ids

    def test_tree_goals_have_tasks(self):
        a, g1, *_ = _populated_atlas()
        tree = a.tree()
        g1_node = next(g for g in tree["goals"] if g["id"] == g1.id)
        assert "tasks" in g1_node

    def test_tree_tasks_have_subtasks(self):
        a, g1, g2, t1, t2, *_ = _populated_atlas()
        tree = a.tree()
        g1_node = next(g for g in tree["goals"] if g["id"] == g1.id)
        t2_node = next(t for t in g1_node["tasks"] if t["id"] == t2.id)
        assert "subtasks" in t2_node
        assert len(t2_node["subtasks"]) == 2

    def test_unattached_tasks_in_tree(self):
        a, _, _, _, _, _, t4, *_ = _populated_atlas()
        tree = a.tree()
        assert "unattached_tasks" in tree
        ids = [t["id"] for t in tree["unattached_tasks"]]
        assert t4.id in ids

    def test_archived_excluded_from_tree(self):
        a = Atlas()
        g = a.add_goal({"title": "G", "status": "archived"})
        tree = a.tree()
        assert "goals" not in tree


class TestQueueView:
    def test_queue_sorted_by_priority(self):
        a, *_ = _populated_atlas()
        q = a.queue()
        priorities = [t["priority"] for t in q]
        assert priorities[0] == "high"

    def test_queue_excludes_done(self):
        a, _, _, _, _, _, t4, *_ = _populated_atlas()
        q = a.queue()
        ids = [t["id"] for t in q]
        assert t4.id not in ids

    def test_queue_excludes_parent_tasks(self):
        a, _, _, _, t2, _, _, _, _ = _populated_atlas()
        q = a.queue()
        ids = [t["id"] for t in q]
        assert t2.id not in ids

    def test_queue_scoped_to_goal(self):
        a, g1, g2, t1, *_ = _populated_atlas()
        q = a.queue(goal_id=g1.id)
        goal_ids_in_queue = {t["id"] for t in q}
        assert t1.id in goal_ids_in_queue

    def test_queue_fields(self):
        a, *_ = _populated_atlas()
        q = a.queue()
        for t in q:
            assert "id" in t
            assert "title" in t
            assert "priority" in t
            assert "stage" in t


class TestSummaryView:
    def test_summary_counts(self):
        a, *_ = _populated_atlas()
        s = a.summary()
        assert s["goal_count"] == 2
        assert s["task_count"] == 6  # 4 top-level + 2 subtasks

    def test_summary_by_stage(self):
        a, *_ = _populated_atlas()
        s = a.summary()
        assert "active" in s["by_stage"]

    def test_summary_by_status(self):
        a, *_ = _populated_atlas()
        s = a.summary()
        assert "active" in s["by_status"]

    def test_summary_recent_events(self):
        a, *_ = _populated_atlas()
        s = a.summary()
        assert len(s["recent_events"]) > 0


class TestViewEnhancements:
    def test_queue_with_limit(self):
        a, *_ = _populated_atlas()
        q = a.queue(limit=2)
        assert len(q) == 2

    def test_board_task_summaries_include_stage(self):
        a, *_ = _populated_atlas()
        b = a.board()
        for stage, items in b["stages"].items():
            for item in items:
                assert "stage" in item
                assert item["stage"] == stage
