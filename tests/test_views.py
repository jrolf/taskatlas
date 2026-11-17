"""Tests for board, progressive tree, critical-path readiness queue, summary, and briefs."""

import taskatlas as ta


class TestProgressiveTreeAndBoard:
    def test_tree_omits_dreams_when_none_exist(self):
        atlas = ta.Atlas("Goal Only")
        g = atlas.add_goal("Ship CLI", status="active")
        g.add_task("Argparse setup", stage="ready")
        atlas.add_task("Unattached chore", stage="inbox")

        tree = atlas.tree()
        assert "dreams" not in tree
        assert "goals" in tree
        assert "unattached_tasks" in tree
        assert "dream_count" not in atlas.summary()
        assert "## Dreams" not in atlas.brief()

    def test_tree_surfaces_dreams_and_filters_archived_at_all_depths(self):
        atlas = ta.Atlas("Full Hierarchy")
        d = atlas.add_dream("Platform Vision", status="active")
        g_dream = d.add_goal("Core Engine", status="active")
        sub_g_arch = g_dream.add_goal("Archived Subgoal", status="abandoned")
        sub_g_arch.archive()

        parent_t = g_dream.add_task("Parent Task", stage="active")
        sub_t_visible = parent_t.add_task("Visible Subtask", stage="ready")
        sub_t_arch = parent_t.add_task("Archived Subtask", stage="canceled")
        sub_t_arch.archive()

        g_standalone = atlas.add_goal("Standalone Ops", status="active")

        tree = atlas.tree()
        assert len(tree["dreams"]) == 1
        assert len(tree["unattached_goals"]) == 1
        assert tree["unattached_goals"][0]["id"] == g_standalone.id

        dream_goal_node = tree["dreams"][0]["goals"][0]
        assert "subgoals" not in dream_goal_node  # archived subgoal excluded!
        subtasks = dream_goal_node["tasks"][0]["subtasks"]
        assert [s["id"] for s in subtasks] == [sub_t_visible.id]

        # Transitive board includes subtasks under goal_id and dream_id
        board = atlas.board(dream_id=d.id)
        ready_ids = [c["id"] for c in board["stages"]["ready"]]
        assert sub_t_visible.id in ready_ids


class TestCriticalPathReadinessQueue:
    def test_decomposed_subtasks_surface_in_goal_and_dream_queues(self):
        # Regression test: decomposed goal tasks must surface subtasks in queue(goal_id=...)
        atlas = ta.Atlas("Subtask Queue")
        dream = atlas.add_dream("Vision", status="active")
        goal = dream.add_goal("Backend", status="active")
        parent = goal.add_task("Database layer", stage="active", priority="urgent")
        sub1 = parent.add_task("Connection pooling", stage="ready", priority="high")

        goal_q = atlas.queue(goal_id=goal.id)
        dream_q = atlas.queue(dream_id=dream.id)
        assert [item["id"] for item in goal_q] == [sub1.id]
        assert [item["id"] for item in dream_q] == [sub1.id]

        # Once all subtasks finish, open parent resurfaces so it can be integrated and closed
        sub1.complete("Pool verified")
        resurfaced = atlas.queue(goal_id=goal.id)
        assert [item["id"] for item in resurfaced] == [parent.id]

    def test_subtasks_inherit_critical_path_urgency_from_parent_dependents(self):
        atlas = ta.Atlas("Container Critical Path")
        goal = atlas.add_goal("Data Engine", status="active")
        schema_parent = goal.add_task("Schema registry", stage="active", priority="medium")
        subtask = schema_parent.add_task("WAL storage", stage="ready", priority="low")
        urgent_parser = goal.add_task("SQL parser", stage="ready", priority="urgent")
        urgent_parser.link(schema_parent, kind="depends_on")

        q = atlas.queue()
        assert q[0]["id"] == subtask.id
        assert q[0]["effective_priority"] == "urgent"
        assert q[0]["priority_boosted"] is True
        assert q[0]["unblocks_count"] == 1

    def test_critical_path_priority_inheritance_and_filtering(self):
        atlas = ta.Atlas("Critical Path")
        goal = atlas.add_goal("Release", status="active")

        # Low-priority prerequisite blocks an Urgent downstream task!
        prereq = goal.add_task("Provision certs", stage="ready", priority="low")
        urgent_deploy = goal.add_task("Cut prod traffic", stage="ready", priority="urgent")
        urgent_deploy.link(prereq, kind="depends_on")

        medium_other = goal.add_task("Polish CSS", stage="ready", priority="medium")
        held_task = goal.add_task("Vendor webhook", stage="ready", priority="urgent")
        held_task.hold("Waiting on vendor")
        review_task = goal.add_task("PR awaiting review", stage="review", priority="urgent")
        claimed_task = goal.add_task("Worker 1 job", stage="active", priority="urgent")
        claimed_task.claim("agent:w1")

        q = atlas.queue()
        q_ids = [item["id"] for item in q]

        # Blocked, held, review, and claimed-by-others tasks are excluded
        assert urgent_deploy.id not in q_ids
        assert held_task.id not in q_ids
        assert review_task.id not in q_ids
        assert claimed_task.id not in q_ids

        # Low prereq inherited URGENT priority from urgent_deploy and ranks #1!
        assert q_ids == [prereq.id, medium_other.id]
        assert q[0]["effective_priority"] == "urgent"
        assert q[0]["priority_boosted"] is True
        assert q[0]["unblocks_count"] == 1

        # Requesting queue for agent:w1 includes its claimed task
        w1_ids = [item["id"] for item in atlas.queue(owner="agent:w1")]
        assert claimed_task.id in w1_ids

    def test_pausing_goal_or_dormant_dream_pauses_queue_tasks(self):
        atlas = ta.Atlas("Pause Physics")
        dream = atlas.add_dream("Long Arc", status="active")
        goal = dream.add_goal("Phase 1", status="active")
        task = goal.add_task("Build feature", stage="ready")

        assert [item["id"] for item in atlas.queue()] == [task.id]

        goal.set_status("paused", reason="Deferred to next month")
        assert atlas.queue() == []

        goal.set_status("active", reason="Resumed")
        assert len(atlas.queue()) == 1

        dream.set_status("dormant", reason="Hibernating dream")
        assert atlas.queue() == []

    def test_subgoal_pause_and_ancestor_task_hold_gate_subtasks(self):
        atlas = ta.Atlas("Hierarchy Gating")
        root_goal = atlas.add_goal("Root Goal", status="active")
        sub_goal = root_goal.add_goal("Subgoal", status="active")
        parent_task = sub_goal.add_task("Parent Task", stage="active")
        leaf = parent_task.add_task("Leaf Task", stage="ready")

        assert [item["id"] for item in atlas.queue()] == [leaf.id]

        # Pausing subgoal under active root goal pauses leaf
        sub_goal.set_status("paused", reason="Paused subgoal")
        assert atlas.queue() == []
        sub_goal.set_status("active", reason="Resumed subgoal")

        # Pausing root goal while subgoal stays active also pauses leaf
        root_goal.set_status("paused", reason="Paused root")
        assert atlas.queue() == []
        root_goal.set_status("active", reason="Resumed root")

        # Holding ancestor container task gates its open leaf subtasks
        parent_task.hold("Waiting on architecture review")
        assert atlas.queue() == []
        parent_task.unhold("Approved")
        assert [item["id"] for item in atlas.queue()] == [leaf.id]

    def test_dream_priority_breaks_ties_without_hijacking_urgent_tactical_work(self):
        atlas = ta.Atlas("Dream Tiebreak")
        high_dream = atlas.add_dream("High Dream", status="active", priority="urgent")
        g_dream = high_dream.add_goal("Dream Goal", status="active", priority="medium")
        t_dream_med = g_dream.add_task("Dream medium task", stage="ready", priority="medium")

        g_ops = atlas.add_goal("Prod Incident", status="active", priority="medium")
        t_ops_urgent = g_ops.add_task("Fix outage", stage="ready", priority="urgent")
        t_ops_med = g_ops.add_task("Ops medium task", stage="ready", priority="medium")

        q_ids = [item["id"] for item in atlas.queue()]
        # Urgent tactical outage fix still wins #1; among equal medium tasks, high-dream task wins!
        assert q_ids == [t_ops_urgent.id, t_dream_med.id, t_ops_med.id]
