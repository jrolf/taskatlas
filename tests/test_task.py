"""Tests for Task receipts, holds, worker claims, property guards, and context propagation."""

import pytest

import taskatlas as ta


class TestTaskReceiptsAndLifecycle:
    def test_complete_records_receipt_and_propagates_downstream(self):
        atlas = ta.Atlas("Receipts")
        dream = atlas.add_dream("Autonomous Cloud", status="active")
        goal = dream.add_goal("Ship API", status="active")

        spec_task = goal.add_task("Write OpenAPI spec", stage="active", priority="high")
        impl_task = goal.add_task("Generate server stubs", stage="ready", priority="high")
        impl_task.link(spec_task, kind="depends_on")

        assert impl_task.is_blocked is True

        receipt = spec_task.complete(
            "Published OpenAPI 3.1 schema for auth and billing.",
            artifacts=["specs/openapi.yaml"],
            data={"endpoint_count": 12},
            actor="agent:architect",
        )
        assert spec_task.stage == "done"
        assert receipt["artifacts"] == ["specs/openapi.yaml"]
        assert spec_task.result["data"]["endpoint_count"] == 12

        # Downstream task unblocks automatically and sees upstream receipt in context() and brief()
        assert impl_task.is_blocked is False
        full_ctx = impl_task.context(mode="full")
        assert full_ctx["dream"]["title"] == "Autonomous Cloud"
        assert full_ctx["unsatisfied_blockers"] == []
        upstream = full_ctx["satisfied_dependencies"][0]
        assert upstream["id"] == spec_task.id
        assert upstream["result"]["artifacts"] == ["specs/openapi.yaml"]

        brief = impl_task.brief()
        assert "specs/openapi.yaml" in brief
        assert "Autonomous Cloud" in brief

    def test_cancel_and_reopen_lifecycle(self):
        atlas = ta.Atlas("Cancel")
        replacement = atlas.add_task("New approach", stage="ready")
        obsolete = atlas.add_task("Old approach", stage="active")

        rec = obsolete.cancel(
            reason="Superseded by streaming design",
            superseded_by=replacement,
        )
        assert obsolete.stage == "canceled"
        assert rec["superseded_by"] == replacement.id

        # Reopening clears terminal receipt
        obsolete.move("ready", reason="Reconsidering")
        assert obsolete.result is None


class TestExternalHolds:
    def test_hold_and_unhold_preserve_workflow_stage(self):
        atlas = ta.Atlas("Holds")
        task = atlas.add_task("Deploy webhook", stage="review")

        task.hold("Waiting on security sign-off")
        assert task.stage == "review"
        assert task.is_held is True
        assert task.is_blocked is True
        assert task.hold_reason == "Waiting on security sign-off"

        task.unhold("Security approved")
        assert task.stage == "review"
        assert task.is_held is False
        assert task.is_blocked is False
        assert task.hold_reason is None

    def test_cannot_hold_terminal_task(self):
        atlas = ta.Atlas("Terminal Hold")
        task = atlas.add_task("Finished")
        task.complete("Done")

        with pytest.raises(ValueError, match="terminal"):
            task.hold("Too late")


class TestWorkerClaims:
    def test_claim_conflict_guard_and_release(self):
        atlas = ta.Atlas("Multi-Agent")
        task = atlas.add_task("Index corpus", stage="ready")

        task.claim("agent:worker-1", move_active=True)
        assert task.owner == "agent:worker-1"
        assert task.stage == "active"

        # Idempotent for same owner
        task.claim("agent:worker-1")

        # Rejects competing worker until released
        with pytest.raises(ValueError, match="already claimed"):
            task.claim("agent:worker-2")

        task.release(reason="Worker-1 timed out")
        assert task.owner is None

        task.claim("agent:worker-2")
        assert task.owner == "agent:worker-2"

        # Completing automatically releases active claim
        task.complete("Indexed 10k docs")
        assert task.owner is None


class TestTaskPropertyGuards:
    def test_direct_mutation_raises_helpful_errors(self):
        atlas = ta.Atlas("Guards")
        task = atlas.add_task("Protected")

        with pytest.raises(AttributeError, match="move"):
            task.stage = "done"
        with pytest.raises(AttributeError, match="claim"):
            task.owner = "rogue"
        with pytest.raises(AttributeError, match="add_tag"):
            task.tags = ["bypass"]
        with pytest.raises(TypeError):
            task.meta["untracked"] = True

        task.update_meta({"tracked": True}, reason="Recorded cleanly")
        assert task.meta["tracked"] is True
