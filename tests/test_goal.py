"""Tests for Goal lifecycle, criteria, outcomes, property guards, and transitive progress."""

import pytest

import taskatlas as ta


class TestGoalLifecycleAndCriteria:
    def test_criteria_and_achieve_outcome(self):
        atlas = ta.Atlas("Goals")
        goal = atlas.add_goal(
            "Ship ingestion v1",
            status="active",
            priority="urgent",
            criteria=[
                "At-least-once delivery under broker restart",
                "p99 latency under 50ms",
            ],
        )

        assert len(goal.criteria) == 2
        goal.add_criterion("Runbook published")
        assert len(goal.criteria) == 3
        goal.remove_criterion("Runbook published")
        assert len(goal.criteria) == 2

        goal.achieve(outcome="Deployed v1.0; p99 measured at 18ms.")
        assert goal.status == "achieved"
        assert "18ms" in goal.outcome

    def test_abandon_and_archive_preserve_resolution(self):
        atlas = ta.Atlas("Abandonment")
        goal = atlas.add_goal("Speculative integration", status="proposed")
        goal.abandon(reason="Partner sunsetted their API", archive=True)

        assert goal.status == "abandoned"
        assert goal.archived is True
        assert atlas.get_goals() == []
        assert atlas.get_goals(archived=True) == [goal]

    def test_direct_property_assignment_blocked_with_guidance(self):
        atlas = ta.Atlas("Guards")
        goal = atlas.add_goal("Protected")

        with pytest.raises(AttributeError, match="set_status"):
            goal.status = "active"
        with pytest.raises(AttributeError, match="set_priority"):
            goal.priority = "high"
        with pytest.raises(AttributeError, match="set_title"):
            goal.title = "Mutated"
        with pytest.raises(AttributeError, match="archive"):
            goal.archived = True


class TestGoalTransitiveProgress:
    def test_progress_walks_subgoals_and_subtasks_without_double_counting(self):
        atlas = ta.Atlas("Transitive Progress")
        parent_goal = atlas.add_goal("Platform", status="active")
        sub_goal = parent_goal.add_goal("Database", status="active")

        container_task = sub_goal.add_task("Storage engine", stage="active")
        leaf1 = container_task.add_task("Schema migration", stage="ready")
        leaf2 = container_task.add_task("Connection pool", stage="ready")
        leaf3 = container_task.add_task("Dropped experiment", stage="inbox")

        # Even if leaf1 is also directly attached to parent_goal, it must count once
        parent_goal.attach_task(leaf1)

        leaf1.complete("Migrations green")
        # Archive completed leaf1 - it must STILL count toward completion!
        leaf1.archive(reason="Clean up board")
        # Cancel obsolete leaf3 - it must NOT lock done_ratio below 1.0!
        leaf3.cancel(reason="No longer needed")

        prog_half = parent_goal.progress()
        assert prog_half["task_count"] == 2
        assert prog_half["canceled_count"] == 1
        assert prog_half["done_count"] == 1
        assert prog_half["done_ratio"] == 0.5

        leaf2.complete("Pool tuned")
        prog_full = parent_goal.progress()
        assert prog_full["done_count"] == 2
        assert prog_full["task_count"] == 2
        assert prog_full["done_ratio"] == 1.0

    def test_hydrated_goal_context_and_brief(self):
        atlas = ta.Atlas("Hydrated Goal")
        dream = atlas.add_dream("North Star", status="active")
        goal = dream.add_goal(
            "API Gateway",
            status="active",
            criteria=["Auth middleware complete"],
        )
        t1 = goal.add_task("JWT verifier", stage="active", priority="high")

        ctx = goal.context(mode="full")
        assert ctx["dream"]["title"] == "North Star"
        assert ctx["criteria"] == ["Auth middleware complete"]
        assert ctx["tasks"][0]["id"] == t1.id
        assert ctx["tasks"][0]["title"] == "JWT verifier"

        brief = goal.brief()
        assert "North Star" in brief
        assert "Auth middleware complete" in brief
        assert "JWT verifier" in brief
