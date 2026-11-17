"""Tests for full serialization round-trips, atomic saves, integrity checks, and 0.2.0 migration."""

import json
import warnings

import pytest

import taskatlas as ta


class TestFullRoundTripAndAtomicSave:
    def test_full_hierarchy_round_trip(self, tmp_path):
        atlas = ta.Atlas("Persistence Suite", meta={"env": "test"})
        with atlas.as_actor("agent:planner"):
            dream = atlas.add_dream(
                "Autonomous Studio",
                vision="Continuous multi-agent engineering.",
                status="active",
                priority="high",
            )
            goal = dream.add_goal(
                "Ship intentionality substrate",
                status="active",
                priority="urgent",
                criteria=["Zero external deps", "Atomic save"],
            )
            subgoal = goal.add_goal("Persistence hardening", status="active")
            t1 = subgoal.add_task("Atomic temp-file replace", stage="ready", priority="high")
            t2 = subgoal.add_task("Integrity validator", stage="ready", priority="high")
            t2.link(t1, kind="depends_on")
            t1.complete("Implemented fsync + os.replace", artifacts=["taskatlas/_atlas.py"])
            t2.claim("agent:builder", move_active=True)
            t2.hold("Awaiting edge-case review")
            t2.note("Checking cyclic link edge case", meta={"cases": 4})

        save_path = tmp_path / "atlas.json"
        atlas.save(save_path)
        restored = ta.Atlas.load(save_path)

        assert restored.name == "Persistence Suite"
        assert restored.get_dream(dream.id).vision == dream.vision
        assert restored.get_goal(goal.id).criteria == ("Zero external deps", "Atomic save")
        rt1 = restored.get_task(t1.id)
        rt2 = restored.get_task(t2.id)
        assert rt1.result["artifacts"] == ["taskatlas/_atlas.py"]
        assert rt2.owner == "agent:builder"
        assert rt2.hold_reason == "Awaiting edge-case review"
        assert rt2.dependencies() == [rt1]
        assert len(restored.get_events()) == len(atlas.get_events())

        # Double round-trip stability
        assert restored.to_dict() == ta.Atlas.from_dict(restored.to_dict()).to_dict()

    def test_atomic_save_preserves_existing_file_on_failure(self, tmp_path):
        good = ta.Atlas("Safe")
        good.add_goal("Intact Goal")
        path = tmp_path / "atlas.json"
        good.save(path)

        bad = ta.Atlas("Corrupt Meta")
        bad._meta["unserializable"] = object()

        with pytest.raises(TypeError):
            bad.save(path)

        # Previous file on disk remains completely intact and valid JSON!
        recovered = ta.Atlas.load(path)
        assert recovered.name == "Safe"
        assert len(recovered.get_goals()) == 1


class TestIntegrityValidationAndLegacyMigration:
    def test_corrupt_dangling_references_and_cycles_rejected(self):
        atlas = ta.Atlas("Valid")
        g = atlas.add_goal("G")
        t1 = g.add_task("T1")
        t2 = g.add_task("T2")
        t1.link(t2, kind="depends_on")

        # Dangling task_id on goal
        bad_missing = atlas.to_dict()
        bad_missing["goals"][g.id]["task_ids"].append("t-missing1")
        with pytest.raises(ValueError, match="Invalid atlas data"):
            ta.Atlas.from_dict(bad_missing)

        # Cyclic depends_on injected into JSON
        bad_cycle = atlas.to_dict()
        bad_cycle["links"]["lk-injected"] = {
            "id": "lk-injected",
            "source_id": t2.id,
            "source_type": "task",
            "target_id": t1.id,
            "target_type": "task",
            "kind": "depends_on",
            "created_at": "2026-01-01T00:00:00+00:00",
            "meta": {},
        }
        with pytest.raises(ValueError, match="Cyclic depends_on"):
            ta.Atlas.from_dict(bad_cycle)

    def test_legacy_0_2_0_payload_migrates_cleanly(self):
        legacy = {
            "version": "0.2.0",
            "name": "Legacy Project",
            "goals": {
                "g-11111111": {
                    "id": "g-11111111",
                    "title": "Old Archived Goal",
                    "status": "archived",
                    "priority": "medium",
                    "task_ids": [],
                    "child_goal_ids": [],
                    "parent_goal_id": None,
                    "events": [],
                },
                "g-22222222": {
                    "id": "g-22222222",
                    "title": "Active Goal",
                    "status": "active",
                    "priority": "high",
                    "task_ids": ["t-aaaaaaaa", "t-bbbbbbbb"],
                    "child_goal_ids": [],
                    "parent_goal_id": None,
                    "events": [],
                },
            },
            "tasks": {
                "t-aaaaaaaa": {
                    "id": "t-aaaaaaaa",
                    "title": "Prereq",
                    "stage": "active",
                    "priority": "high",
                    "goal_ids": ["g-22222222"],
                    "child_task_ids": [],
                    "parent_task_id": None,
                    "link_ids": ["lk-00000001"],
                },
                "t-bbbbbbbb": {
                    "id": "t-bbbbbbbb",
                    "title": "Blocked Downstream",
                    "stage": "blocked",
                    "priority": "urgent",
                    "goal_ids": ["g-22222222"],
                    "child_task_ids": [],
                    "parent_task_id": None,
                    "link_ids": ["lk-00000001"],
                },
            },
            "links": {
                "lk-00000001": {
                    "id": "lk-00000001",
                    "source_id": "t-aaaaaaaa",
                    "source_type": "task",
                    "target_id": "t-bbbbbbbb",
                    "target_type": "task",
                    "kind": "blocks",
                }
            },
            "events": [],
        }

        migrated = ta.Atlas.from_dict(legacy)
        old_g = migrated.get_goal("g-11111111")
        assert old_g.status == "abandoned"
        assert old_g.archived is True

        downstream = migrated.get_task("t-bbbbbbbb")
        prereq = migrated.get_task("t-aaaaaaaa")
        assert downstream.stage == "ready"
        assert downstream.is_held is True
        assert downstream.dependencies() == [prereq]

        # Legacy payload without version warns and still loads
        no_ver = {"name": "Unversioned", "goals": {}, "tasks": {}}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            loaded = ta.Atlas.from_dict(no_ver)
            assert len(caught) == 1
        assert isinstance(json.dumps(loaded.to_dict()), str)
