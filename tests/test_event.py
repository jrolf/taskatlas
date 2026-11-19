"""Tests for the immutable Event model."""

import pytest

from taskatlas._event import Event


class TestEventImmutabilityAndFields:
    def test_creation_and_actor_provenance(self):
        ev = Event(
            event_type="task_stage_changed",
            entity_id="t-abc12345",
            entity_type="task",
            data={"old_stage": "ready", "new_stage": "active", "nested": [1, 2]},
            reason="Picked up task",
            actor="agent:worker-1",
        )
        assert ev.id.startswith("ev-")
        assert ev.event_type == "task_stage_changed"
        assert ev.entity_id == "t-abc12345"
        assert ev.actor == "agent:worker-1"
        assert ev.reason == "Picked up task"
        assert ev.data["nested"] == (1, 2)

    def test_attribute_and_data_mutation_blocked(self):
        ev = Event(
            event_type="note_added",
            entity_id="d-abc12345",
            entity_type="dream",
            data={"note_id": "n-11111111"},
        )
        with pytest.raises(AttributeError, match="immutable"):
            ev.reason = "tampered"

        with pytest.raises(TypeError):
            ev.data["note_id"] = "n-tampered"

    def test_round_trip_serialization(self):
        ev1 = Event(
            event_type="dream_created",
            entity_id="d-abc12345",
            entity_type="dream",
            data={"title": "Research Lab"},
            reason="Initial seed",
            actor="human:james",
        )
        restored = Event.from_dict(ev1.to_dict())
        assert restored == ev1
        assert restored.actor == "human:james"
        assert restored.data["title"] == "Research Lab"
