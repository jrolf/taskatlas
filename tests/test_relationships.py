"""Tests for containment, canonical causal links, cycle prevention, and live unblocking."""

import pytest

import taskatlas as ta


class TestContainmentAndReparenting:
    def test_multi_goal_attachment_and_detachment(self):
        atlas = ta.Atlas("Multi-Goal")
        g1 = atlas.add_goal("Public API")
        g2 = atlas.add_goal("Developer Docs")
        spec = atlas.add_task("OpenAPI schema")

        g1.attach_task(spec)
        g2.attach_task(spec.id)
        assert set(spec.goal_ids) == {g1.id, g2.id}

        g2.detach_task(spec)
        assert spec.goal_ids == (g1.id,)
        # Detaching a non-attached task is a silent no-op without phantom events
        before_count = len(g2.history())
        g2.detach_task(spec)
        assert len(g2.history()) == before_count

    def test_subtask_and_subgoal_reparenting_and_cycle_detection(self):
        atlas = ta.Atlas("Cycles")
        g1 = atlas.add_goal("G1")
        g2 = g1.add_goal("G2")
        g3 = g2.add_goal("G3")

        with pytest.raises(ValueError, match="Cyclic goal containment"):
            g3.attach_goal(g1)

        t1 = atlas.add_task("T1")
        t2 = t1.add_task("T2")
        t3 = t2.add_task("T3")

        with pytest.raises(ValueError, match="Cyclic task containment"):
            t3.attach_task(t1)

        # Detach t3 from t2 and re-attach under t1 cleanly
        t2.detach_task(t3)
        t1.attach_task(t3)
        assert t3.parent_task_id == t1.id


class TestCanonicalCausalDependencies:
    def test_blocks_helper_writes_canonical_depends_on_edge(self):
        atlas = ta.Atlas("Canonical")
        prereq = atlas.add_task("Build auth", stage="active")
        api = atlas.add_task("Expose endpoints", stage="ready")

        lk1 = prereq.blocks(api)
        lk2 = api.link(prereq, kind="depends_on")

        # Both point to the exact same deduplicated canonical Link!
        assert lk1 is lk2
        assert lk1.kind == "depends_on"
        assert lk1.source_id == api.id
        assert lk1.target_id == prereq.id
        assert prereq.dependents() == [api]
        assert api.blockers() == [prereq]
        assert api.is_topologically_blocked is True

        # Completing prereq clears blockers() while preserving historical dependencies()
        prereq.complete("Auth merged")
        assert api.blockers() == []
        assert api.dependencies() == [prereq]
        assert api.is_blocked is False

    def test_cross_layer_goal_task_causal_dependencies(self):
        atlas = ta.Atlas("Cross Layer")
        milestone = atlas.add_goal("Security Baseline", status="active")
        deploy = atlas.add_task("Public launch", stage="ready")
        deploy.link(milestone, kind="depends_on")

        assert deploy.is_blocked is True
        milestone.achieve(outcome="Audit signed off")
        assert deploy.is_blocked is False
        ctx = deploy.context(mode="full")
        assert ctx["satisfied_dependencies"][0]["outcome"] == "Audit signed off"

    def test_causal_dependency_cycle_rejected(self):
        atlas = ta.Atlas("DAG")
        a = atlas.add_task("A")
        b = atlas.add_task("B")
        c = atlas.add_task("C")

        a.link(b, kind="depends_on")
        b.link(c, kind="depends_on")

        with pytest.raises(ValueError, match="Cyclic dependency"):
            c.link(a, kind="depends_on")

        with pytest.raises(ValueError, match="Cyclic dependency"):
            a.blocks(c)

    def test_unlink_cleans_both_endpoints(self):
        atlas = ta.Atlas("Unlink")
        a = atlas.add_task("A")
        b = atlas.add_task("B")
        a.link(b, kind="depends_on")
        a.link(b, kind="relates_to")

        removed = a.unlink(target=b, kind="depends_on")
        assert removed == 1
        assert a.dependencies() == []
        assert len(a.get_links(kind="relates_to")) == 1
