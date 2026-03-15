"""Integration tests for serialization round-trips."""

import json

import taskatlas as ta


class TestAtlasRoundTrip:
    def _build_atlas(self):
        atlas = ta.Atlas({"name": "Serialization Test", "meta": {"version": 1}})

        g1 = atlas.add_goal({
            "title": "Ship v0 API",
            "summary": "Define and stabilize the public surface.",
            "status": "active",
            "priority": "high",
            "tags": ["core", "api"],
        })

        g2 = g1.add_goal({"title": "Define naming", "priority": "medium"})

        t1 = g1.add_task({
            "title": "Define Atlas class",
            "stage": "active",
            "priority": "high",
            "tags": ["atlas"],
        })

        t2 = g1.add_task({
            "title": "Define Goal class",
            "stage": "ready",
            "priority": "high",
        })

        sub1 = t2.add_task({"title": "Goal status lifecycle", "stage": "ready"})
        sub2 = t2.add_task({"title": "Goal progress semantics", "stage": "inbox"})

        t1.note("Need stronger naming distinction")
        g1.note("Keep it lighter than Jira")

        t1.link(t2, kind="relates_to")
        g1.link(g2, kind="supports")

        t1.move("review", reason="Implementation done")
        g1.set_status("active", reason="Scope approved")

        return atlas, g1, g2, t1, t2, sub1, sub2

    def test_to_dict_is_json_serializable(self):
        atlas, *_ = self._build_atlas()
        d = atlas.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_round_trip_preserves_goals(self):
        atlas1, g1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        g1_restored = atlas2.get_goal(g1.id)
        assert g1_restored.title == g1.title
        assert g1_restored.status == g1.status
        assert g1_restored.priority == g1.priority
        assert g1_restored.tags == g1.tags

    def test_round_trip_preserves_tasks(self):
        atlas1, _, _, t1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        t1_restored = atlas2.get_task(t1.id)
        assert t1_restored.title == t1.title
        assert t1_restored.stage == t1.stage
        assert t1_restored.priority == t1.priority

    def test_round_trip_preserves_notes(self):
        atlas1, _, _, t1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        t1_restored = atlas2.get_task(t1.id)
        assert len(t1_restored.notes) == len(t1.notes)
        assert t1_restored.notes[0]["text"] == t1.notes[0]["text"]

    def test_round_trip_preserves_goal_task_attachment(self):
        atlas1, g1, _, t1, t2, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        g1_r = atlas2.get_goal(g1.id)
        assert t1.id in g1_r.task_ids
        assert t2.id in g1_r.task_ids

    def test_round_trip_preserves_task_hierarchy(self):
        atlas1, _, _, _, t2, sub1, sub2 = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        t2_r = atlas2.get_task(t2.id)
        assert sub1.id in t2_r.child_task_ids
        assert sub2.id in t2_r.child_task_ids

        sub1_r = atlas2.get_task(sub1.id)
        assert sub1_r.parent_task_id == t2.id

    def test_round_trip_preserves_goal_hierarchy(self):
        atlas1, g1, g2, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        g1_r = atlas2.get_goal(g1.id)
        assert g2.id in g1_r.child_goal_ids

        g2_r = atlas2.get_goal(g2.id)
        assert g2_r.parent_goal_id == g1.id

    def test_round_trip_preserves_links(self):
        atlas1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        assert len(atlas2._links) == len(atlas1._links)

    def test_round_trip_preserves_events(self):
        atlas1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        assert len(atlas2._events) == len(atlas1._events)

    def test_round_trip_preserves_atlas_metadata(self):
        atlas1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        assert atlas2.name == atlas1.name
        assert atlas2.meta == atlas1.meta
        assert atlas2.task_stages == atlas1.task_stages
        assert atlas2.goal_statuses == atlas1.goal_statuses

    def test_round_trip_preserves_timestamps(self):
        atlas1, _, _, t1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        t1_r = atlas2.get_task(t1.id)
        assert t1_r.created_at == t1.created_at

    def test_double_round_trip_stable(self):
        atlas1, *_ = self._build_atlas()
        d1 = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d1)
        d2 = atlas2.to_dict()

        assert d1["name"] == d2["name"]
        assert d1["meta"] == d2["meta"]
        assert set(d1["goals"].keys()) == set(d2["goals"].keys())
        assert set(d1["tasks"].keys()) == set(d2["tasks"].keys())
        assert set(d1["links"].keys()) == set(d2["links"].keys())
        assert len(d1["events"]) == len(d2["events"])

    def test_equality_after_round_trip(self):
        atlas1, g1, _, t1, *_ = self._build_atlas()
        d = atlas1.to_dict()
        atlas2 = ta.Atlas.from_dict(d)

        g1_r = atlas2.get_goal(g1.id)
        t1_r = atlas2.get_task(t1.id)

        assert g1_r.id == g1.id
        assert t1_r.id == t1.id


class TestGoalTaskSerialization:
    def test_goal_to_dict_standalone(self):
        g = ta.Goal({"title": "G", "status": "active", "priority": "high"})
        g.note("note")
        d = g.to_dict()
        assert d["title"] == "G"
        assert d["status"] == "active"
        assert len(d["notes"]) == 1

    def test_task_to_dict_standalone(self):
        t = ta.Task({"title": "T", "stage": "active", "priority": "high"})
        t.note("note")
        d = t.to_dict()
        assert d["title"] == "T"
        assert d["stage"] == "active"
        assert len(d["notes"]) == 1


class TestSerializationHardening:
    def test_to_dict_includes_version(self):
        atlas = ta.Atlas({"name": "Test"})
        d = atlas.to_dict()
        assert "version" in d
        assert d["version"] == "0.2.0"

    def test_from_dict_no_version_warns(self):
        payload = {"name": "Legacy", "goals": {}, "tasks": {}}
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            atlas = ta.Atlas.from_dict(payload)
            assert len(w) == 1
            assert "version" in str(w[0].message).lower()
        assert atlas.name == "Legacy"

    def test_from_dict_invalid_type_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Invalid atlas data"):
            ta.Atlas.from_dict("not a dict")

    def test_from_dict_corrupt_goals_raises(self):
        import pytest
        payload = {"version": "0.2.0", "goals": {"g-bad": "not_a_dict"}, "tasks": {}}
        with pytest.raises(ValueError, match="Invalid atlas data"):
            ta.Atlas.from_dict(payload)

    def test_save_and_load_roundtrip(self, tmp_path):
        atlas = ta.Atlas({"name": "SaveTest"})
        g = atlas.add_goal({"title": "G", "status": "active"})
        t = g.add_task({"title": "T", "stage": "ready"})
        t.note("hello")

        path = str(tmp_path / "atlas.json")
        atlas.save(path)
        loaded = ta.Atlas.load(path)

        assert loaded.name == "SaveTest"
        assert loaded.get_goal(g.id).title == "G"
        assert loaded.get_task(t.id).title == "T"

    def test_deserialized_entities_are_functional(self):
        atlas = ta.Atlas({"name": "Test"})
        t = atlas.add_task({"title": "T", "stage": "inbox"})
        payload = atlas.to_dict()

        restored = ta.Atlas.from_dict(payload)
        rt = restored.get_task(t.id)
        rt.move("active", reason="Testing")
        rt.note("Works after restore")
        assert rt.stage == "active"
        assert len(rt.notes) == 1
