"""Tests for the filtering engine."""

import pytest

from taskatlas._filtering import filter_items, sort_items
from taskatlas._task import Task
from taskatlas._goal import Goal


def _make_tasks():
    """Create a set of tasks for filtering tests."""
    return [
        Task({"id": "t-00000001", "title": "Alpha", "stage": "active", "priority": "high", "tags": ["core"]}),
        Task({"id": "t-00000002", "title": "Beta", "stage": "ready", "priority": "medium", "tags": ["api"]}),
        Task({"id": "t-00000003", "title": "Gamma design", "stage": "blocked", "priority": "urgent", "tags": ["core", "api"]}),
        Task({"id": "t-00000004", "title": "Delta", "stage": "done", "priority": "low", "tags": ["docs"]}),
        Task({"id": "t-00000005", "title": "Epsilon", "stage": "archived", "priority": "medium", "tags": ["old"]}),
    ]


class TestFilterTasks:
    def test_no_filters_excludes_archived(self):
        tasks = _make_tasks()
        result = filter_items(tasks)
        assert len(result) == 4
        assert all(t.stage != "archived" for t in result)

    def test_include_archived(self):
        tasks = _make_tasks()
        result = filter_items(tasks, archived=True)
        assert len(result) == 1
        assert result[0].id == "t-00000005"

    def test_filter_by_stage(self):
        tasks = _make_tasks()
        result = filter_items(tasks, stage="active")
        assert len(result) == 1
        assert result[0].id == "t-00000001"

    def test_filter_by_priority(self):
        tasks = _make_tasks()
        result = filter_items(tasks, priority="high")
        assert len(result) == 1
        assert result[0].id == "t-00000001"

    def test_filter_by_tags(self):
        tasks = _make_tasks()
        result = filter_items(tasks, tags=["core"])
        assert len(result) == 2

    def test_filter_by_tags_any_match(self):
        tasks = _make_tasks()
        result = filter_items(tasks, tags=["api", "docs"])
        assert len(result) == 3

    def test_title_contains(self):
        tasks = _make_tasks()
        result = filter_items(tasks, title_contains="design")
        assert len(result) == 1
        assert result[0].id == "t-00000003"

    def test_title_contains_case_insensitive(self):
        tasks = _make_tasks()
        result = filter_items(tasks, title_contains="ALPHA")
        assert len(result) == 1

    def test_blocked_filter(self):
        tasks = _make_tasks()
        result = filter_items(tasks, blocked=True)
        assert len(result) == 1
        assert result[0].stage == "blocked"

    def test_conjunctive(self):
        tasks = _make_tasks()
        result = filter_items(tasks, priority="high", stage="active")
        assert len(result) == 1
        assert result[0].id == "t-00000001"

    def test_conjunctive_no_match(self):
        tasks = _make_tasks()
        result = filter_items(tasks, priority="high", stage="blocked")
        assert len(result) == 0

    def test_filter_by_id(self):
        tasks = _make_tasks()
        result = filter_items(tasks, id="t-00000002")
        assert len(result) == 1


class TestFilterGoals:
    def test_filter_by_status(self):
        goals = [
            Goal({"title": "A", "status": "active"}),
            Goal({"title": "B", "status": "proposed"}),
            Goal({"title": "C", "status": "archived"}),
        ]
        result = filter_items(goals, status="active")
        assert len(result) == 1
        assert result[0].title == "A"

    def test_archived_default_excluded(self):
        goals = [
            Goal({"title": "A", "status": "active"}),
            Goal({"title": "B", "status": "archived"}),
        ]
        result = filter_items(goals)
        assert len(result) == 1


class TestSorting:
    def test_sort_by_priority(self):
        tasks = _make_tasks()
        active = [t for t in tasks if t.stage != "archived"]
        result = sort_items(active, "priority")
        priorities = [t.priority for t in result]
        assert priorities[0] == "urgent"
        assert priorities[-1] == "low"

    def test_sort_by_title(self):
        tasks = _make_tasks()
        result = sort_items(tasks, "title")
        assert result[0].title == "Alpha"
        assert result[-1].title == "Gamma design"

    def test_filter_with_order_by(self):
        tasks = _make_tasks()
        result = filter_items(tasks, tags=["core"], order_by="priority")
        assert result[0].priority == "urgent"
        assert result[1].priority == "high"


class TestMultiValueFiltering:
    def test_stage_list_filter(self):
        tasks = _make_tasks()
        result = filter_items(tasks, stage=["active", "blocked"])
        stages = {t.stage for t in result}
        assert stages <= {"active", "blocked"}
        assert len(result) >= 1

    def test_priority_list_filter(self):
        tasks = _make_tasks()
        result = filter_items(tasks, priority=["high", "urgent"])
        for t in result:
            assert t.priority in ("high", "urgent")


class TestLimitParameter:
    def test_limit_on_tasks(self):
        tasks = _make_tasks()
        result = filter_items(tasks, limit=2)
        assert len(result) == 2

    def test_limit_with_order(self):
        tasks = _make_tasks()
        result = filter_items(tasks, order_by="priority", limit=1)
        assert len(result) == 1
        assert result[0].priority == "urgent"


class TestFilterValidation:
    def test_unknown_key_raises(self):
        tasks = _make_tasks()
        with pytest.raises(ValueError, match="Unknown filter key"):
            filter_items(tasks, staeg="active")

    def test_multiple_unknown_keys_raises(self):
        tasks = _make_tasks()
        with pytest.raises(ValueError, match="Unknown filter key"):
            filter_items(tasks, staeg="active", priorty="high")
