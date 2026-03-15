"""Tests for the Event model."""

import pytest

from taskatlas._event import Event


class TestEventCreation:
    def test_basic_creation(self):
        ev = Event(
            event_type="task_created",
            entity_id="t-abc12345",
            entity_type="task",
        )
        assert ev.event_type == "task_created"
        assert ev.entity_id == "t-abc12345"
        assert ev.entity_type == "task"
        assert ev.id.startswith("ev-")
        assert ev.timestamp  # non-empty ISO string
        assert ev.data == {}
        assert ev.reason is None

    def test_with_data_and_reason(self):
        ev = Event(
            event_type="task_stage_changed",
            entity_id="t-abc12345",
            entity_type="task",
            data={"old_stage": "inbox", "new_stage": "active"},
            reason="Starting work",
        )
        assert ev.data["old_stage"] == "inbox"
        assert ev.reason == "Starting work"

    def test_custom_id(self):
        ev = Event(
            id="ev-custom01",
            event_type="goal_created",
            entity_id="g-abc12345",
            entity_type="goal",
        )
        assert ev.id == "ev-custom01"

    def test_custom_timestamp(self):
        ts = "2025-01-15T10:30:00+00:00"
        ev = Event(
            event_type="goal_created",
            entity_id="g-abc12345",
            entity_type="goal",
            timestamp=ts,
        )
        assert ev.timestamp == ts


class TestEventSerialization:
    def test_to_dict(self):
        ev = Event(
            event_type="note_added",
            entity_id="t-abc12345",
            entity_type="task",
            data={"note_id": "n-00112233"},
            reason="context note",
        )
        d = ev.to_dict()
        assert d["event_type"] == "note_added"
        assert d["entity_id"] == "t-abc12345"
        assert d["data"]["note_id"] == "n-00112233"
        assert d["reason"] == "context note"
        assert "id" in d
        assert "timestamp" in d

    def test_round_trip(self):
        ev1 = Event(
            event_type="priority_changed",
            entity_id="g-abc12345",
            entity_type="goal",
            data={"old": "medium", "new": "high"},
            reason="escalated",
        )
        d = ev1.to_dict()
        ev2 = Event.from_dict(d)

        assert ev2.id == ev1.id
        assert ev2.event_type == ev1.event_type
        assert ev2.entity_id == ev1.entity_id
        assert ev2.entity_type == ev1.entity_type
        assert ev2.timestamp == ev1.timestamp
        assert ev2.data == ev1.data
        assert ev2.reason == ev1.reason


class TestEventRepr:
    def test_repr(self):
        ev = Event(
            event_type="task_created",
            entity_id="t-abc12345",
            entity_type="task",
        )
        r = repr(ev)
        assert "task_created" in r
        assert "t-abc12345" in r
