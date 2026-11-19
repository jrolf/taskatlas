"""Tests for the optional Dream horizon, open-world momentum, and stall detection."""

import pytest

import taskatlas as ta


class TestDreamCreationAndContainment:
    def test_create_dream_and_attach_goals(self):
        atlas = ta.Atlas("Dream Lab")
        dream = atlas.add_dream(
            "Autonomous Research Lab",
            vision="Agents conduct, verify, and synthesize experiments overnight.",
            status="active",
            priority="high",
            tags=["research"],
        )

        assert isinstance(dream, ta.Dream)
        assert dream.id.startswith("d-")
        assert dream.vision.startswith("Agents conduct")
        assert atlas.get_dream(dream.id) is dream

        g1 = dream.add_goal("Experiment runner", status="active", priority="high")
        sub_g = g1.add_goal("Sandbox isolation", status="active")
        t1 = sub_g.add_task("Build container wrapper", stage="ready")
        sub_t = t1.add_task("Seccomp profile", stage="ready")

        assert g1.dream_id == dream.id
        assert sub_g.dream_id is None
        assert sub_g.effective_dream_id == dream.id
        assert t1.effective_dream_id == dream.id
        assert sub_t.effective_dream_id == dream.id
        assert len(dream.get_goals(recursive=False)) == 1
        assert len(dream.get_goals(recursive=True)) == 2
        assert sub_t in dream.scope_tasks(leaves_only=True)

    def test_dream_has_no_direct_task_shortcut(self):
        atlas = ta.Atlas("No Shortcuts")
        dream = atlas.add_dream("North Star")
        assert not hasattr(dream, "add_task")
        assert not hasattr(dream, "attach_task")

    def test_subgoal_cannot_attach_directly_to_dream(self):
        atlas = ta.Atlas("Hierarchy Guard")
        dream = atlas.add_dream("North Star")
        root = atlas.add_goal("Root Goal")
        sub = root.add_goal("Subgoal")

        with pytest.raises(ValueError, match="subgoal"):
            dream.attach_goal(sub)

    def test_goal_single_dream_invariant(self):
        atlas = ta.Atlas("Single Dream")
        d1 = atlas.add_dream("Dream 1")
        d2 = atlas.add_dream("Dream 2")
        goal = d1.add_goal("Shared candidate")

        with pytest.raises(ValueError, match="already belongs to Dream"):
            d2.attach_goal(goal)

        # Detaching allows clean reassignment
        d1.detach_goal(goal, reason="Realigned")
        d2.attach_goal(goal, reason="Moved to Dream 2")
        assert goal.dream_id == d2.id

    def test_promoting_goal_to_subgoal_within_same_dream_vs_conflicting_dream(self):
        atlas = ta.Atlas("Dream Subgoal Promotion")
        d1 = atlas.add_dream("Dream 1")
        d2 = atlas.add_dream("Dream 2")
        g_parent = d1.add_goal("Parent Goal")
        g_same = d1.add_goal("Same Dream Child")
        g_other = d2.add_goal("Other Dream Child")

        with pytest.raises(ValueError, match="conflicts with parent Goal Dream"):
            g_parent.attach_goal(g_other)

        # Nesting g_same under g_parent removes duplicate root entry on d1
        g_parent.attach_goal(g_same)
        assert g_same.dream_id is None
        assert g_same.effective_dream_id == d1.id
        assert d1.goal_ids == (g_parent.id,)


class TestDreamMomentumAndStallDetection:
    def test_stalled_when_active_dream_has_no_active_goals(self):
        atlas = ta.Atlas("Stall 1")
        dream = atlas.add_dream("North Star", status="active")
        dream.add_goal("Idea only", status="proposed")

        prog = dream.progress()
        assert prog["stalled"] is True
        assert prog["stall_reason"] == "no_active_goals"

    def test_stalled_when_active_goals_have_no_open_tasks(self):
        atlas = ta.Atlas("Stall 2")
        dream = atlas.add_dream("North Star", status="active")
        g1 = dream.add_goal("Wave 1", status="achieved")
        t1 = g1.add_task("Initial prototype", stage="ready")
        t1.complete("Shipped prototype")

        # Wave 2 is active, but has no open tasks planned yet
        dream.add_goal("Wave 2", status="active")

        prog = dream.progress()
        assert prog["achieved_goal_count"] == 1
        assert prog["active_goal_count"] == 1
        assert prog["stalled"] is True
        assert prog["stall_reason"] == "no_open_tasks"

    def test_stalled_when_all_open_tasks_are_blocked(self):
        atlas = ta.Atlas("Stall 3")
        dream = atlas.add_dream("North Star", status="active")
        goal = dream.add_goal("Wave 1", status="active")
        task = goal.add_task("Provision GPU cluster", stage="ready")
        task.hold("Waiting on cloud quota approval")

        prog = dream.progress()
        assert prog["stalled"] is True
        assert prog["stall_reason"] == "all_tasks_blocked"

        task.unhold("Quota approved")
        prog_after = dream.progress()
        assert prog_after["stalled"] is False
        assert prog_after["stall_reason"] is None
        assert prog_after["actionable_task_count"] == 1

    def test_seed_or_dormant_dream_is_not_flagged_stalled(self):
        atlas = ta.Atlas("Seed")
        dream = atlas.add_dream("Future Idea", status="seed")
        assert dream.progress()["stalled"] is False

    def test_dream_context_and_brief(self):
        atlas = ta.Atlas("Context")
        dream = atlas.add_dream(
            "Self-healing infra",
            vision="Zero-page overnight incident recovery.",
            status="active",
        )
        g = dream.add_goal("Automated rollback", status="active")
        g.add_task("Health probe", stage="ready")
        dream.note("Focusing on stateless services first.")

        compact = dream.context(mode="compact")
        assert compact["stalled"] is False
        assert compact["goal_count"] == 1
        assert "stateless" in compact["latest_note"]

        full = dream.context(mode="full")
        assert full["vision"].startswith("Zero-page")
        assert full["goals"][0]["title"] == "Automated rollback"

        brief = dream.brief()
        assert "Self-healing infra" in brief
        assert "Automated rollback" in brief
