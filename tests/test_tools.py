"""Tests for the zero-dependency LLM agent tool schemas and dispatch router."""

import json

import taskatlas as ta


class TestAgentToolSeam:
    def test_tool_schemas_are_valid_json_schema_objects(self):
        schemas = ta.Atlas.tool_schemas()
        names = [s["name"] for s in schemas]
        assert names == [
            "atlas_orient",
            "atlas_inspect",
            "atlas_upsert_dream",
            "atlas_upsert_goal",
            "atlas_add_task",
            "atlas_update_task",
            "atlas_complete_task",
            "atlas_note",
            "atlas_link",
        ]
        for schema in schemas:
            assert schema["parameters"]["type"] == "object"
            assert isinstance(json.dumps(schema), str)

    def test_end_to_end_agent_loop_via_dispatch_and_as_tools(self):
        atlas = ta.Atlas("Agent Driven")
        bound = {spec["name"]: spec["fn"] for spec in atlas.as_tools(actor="agent:alpha")}

        # 1. Create Dream and Goal
        d_res = bound["atlas_upsert_dream"]({
            "title": "Autonomous Pipeline",
            "vision": "Self-maintaining ingestion.",
            "status": "active",
            "priority": "high",
        })
        assert d_res["ok"] is True
        dream_id = d_res["result"]["id"]

        g_res = bound["atlas_upsert_goal"]({
            "title": "Ship connector v1",
            "dream_id": dream_id,
            "status": "active",
            "priority": "urgent",
            "criteria": ["Passes replay harness"],
        })
        assert g_res["ok"] is True
        goal_id = g_res["result"]["id"]

        # 2. Plan two dependent tasks (passing JSON string args like raw LLM tool calls)
        t1_res = atlas.dispatch(
            "atlas_add_task",
            json.dumps({
                "title": "Define wire schema",
                "goal_id": goal_id,
                "stage": "ready",
                "priority": "medium",
            }),
            actor="agent:alpha",
        )
        t1_id = t1_res["result"]["id"]

        t2_res = bound["atlas_add_task"]({
            "title": "Implement parser",
            "goal_id": goal_id,
            "stage": "ready",
            "priority": "urgent",
            "depends_on_ids": [t1_id],
        })
        t2_id = t2_res["result"]["id"]
        assert t2_res["result"]["is_blocked"] is True

        # 3. Orient: t1 is boosted to URGENT at the top of the ready queue!
        orient = bound["atlas_orient"]({"format": "structured"})
        assert orient["result"]["queue"][0]["id"] == t1_id
        assert orient["result"]["queue"][0]["effective_priority"] == "urgent"

        # 4. Claim, note, and complete t1 with artifacts
        bound["atlas_update_task"]({
            "task_id": t1_id,
            "claim": "agent:alpha",
            "stage": "active",
            "reason": "Starting schema design",
        })
        bound["atlas_note"]({"entity_id": t1_id, "text": "Chose JSON Lines envelope."})
        done_res = bound["atlas_complete_task"]({
            "task_id": t1_id,
            "summary": "Wire schema finalized.",
            "artifacts": ["schemas/wire.json"],
        })
        assert done_res["ok"] is True

        # 5. Inspect t2: now unblocked with upstream artifact receipt visible!
        inspect_t2 = bound["atlas_inspect"]({"entity_id": t2_id, "mode": "full"})
        assert inspect_t2["result"]["is_blocked"] is False
        satisfied = inspect_t2["result"]["satisfied_dependencies"][0]
        assert satisfied["result"]["artifacts"] == ["schemas/wire.json"]

    def test_dispatch_errors_return_structured_self_correction_hints(self):
        atlas = ta.Atlas("Error Hints")
        unknown = atlas.dispatch("nonexistent_tool", {})
        assert unknown["ok"] is False
        assert "Valid tools" in unknown["hint"]

        missing = atlas.dispatch("atlas_inspect", {"entity_id": "t-deadbeef"})
        assert missing["ok"] is False
        assert "atlas_orient" in missing["hint"]

        # Directing agent to atlas_complete_task if it tries moving to 'done' via update_task
        t = atlas.add_task("Work", stage="active")
        wrong_tool = atlas.dispatch(
            "atlas_update_task",
            {"task_id": t.id, "stage": "done"},
        )
        assert wrong_tool["ok"] is False
        assert "atlas_complete_task" in wrong_tool["error"]

        # Link and unlink via atlas_link, and cancel via atlas_complete_task
        t2 = atlas.add_task("Followup", stage="ready")
        lk_res = atlas.dispatch(
            "atlas_link",
            {"source_id": t2.id, "target_id": t.id, "kind": "depends_on"},
        )
        assert lk_res["ok"] is True
        assert t2.is_blocked is True

        unlk_res = atlas.dispatch(
            "atlas_link",
            {"source_id": t2.id, "target_id": t.id, "kind": "depends_on", "remove": True},
        )
        assert unlk_res["result"]["removed"] == 1
        assert t2.is_blocked is False

        cancel_res = atlas.dispatch(
            "atlas_complete_task",
            {"task_id": t2.id, "resolution": "canceled", "summary": "Dropped scope"},
        )
        assert cancel_res["ok"] is True
        assert t2.stage == "canceled"

        # Bare string where JSON array is expected returns error (never shreds chars)
        g = atlas.add_goal("G")
        bad_tags = atlas.dispatch(
            "atlas_upsert_goal",
            {"goal_id": g.id, "tags": "backend"},
        )
        assert bad_tags["ok"] is False
        assert g.tags == ()

        # Malformed non-dict call on bound as_tools() returns structured error receipt
        orient_fn = atlas.as_tools()[0]["fn"]
        bad_call = orient_fn(12345)
        assert bad_call["ok"] is False
