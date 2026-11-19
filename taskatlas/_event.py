"""Immutable historical event model for taskatlas."""

import copy
from datetime import datetime, timezone
from types import MappingProxyType

from taskatlas._identity import make_id


def _freeze_value(value):
    """Recursively freeze dicts and lists so event payloads cannot be mutated."""
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, dict):
        frozen = {k: _freeze_value(v) for k, v in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(v) for v in value)
    return copy.deepcopy(value)


def _thaw_value(value):
    """Convert frozen mapping proxies and tuples back into plain JSON structures."""
    if isinstance(value, MappingProxyType):
        return {k: _thaw_value(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {k: _thaw_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(v) for v in value]
    if isinstance(value, list):
        return [_thaw_value(v) for v in value]
    return copy.deepcopy(value)


class Event:
    """An immutable, append-only record of a meaningful mutation in an Atlas.

    Once constructed, attribute assignment raises ``AttributeError`` and the
    nested ``data`` mapping is read-only.
    """

    __slots__ = (
        "_id",
        "_event_type",
        "_entity_id",
        "_entity_type",
        "_timestamp",
        "_data",
        "_reason",
        "_actor",
    )

    def __init__(
        self,
        *,
        event_type,
        entity_id,
        entity_type,
        data=None,
        reason=None,
        actor=None,
        id=None,
        timestamp=None,
    ):
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("entity_id must be a non-empty string")
        if entity_type not in ("atlas", "dream", "goal", "task"):
            raise ValueError(
                f"entity_type must be 'atlas', 'dream', 'goal', or 'task', "
                f"got {entity_type!r}"
            )

        object.__setattr__(self, "_id", id or make_id("ev"))
        object.__setattr__(self, "_event_type", event_type)
        object.__setattr__(self, "_entity_id", entity_id)
        object.__setattr__(self, "_entity_type", entity_type)
        object.__setattr__(
            self,
            "_timestamp",
            timestamp or datetime.now(timezone.utc).isoformat(),
        )
        object.__setattr__(self, "_data", _freeze_value(data or {}))
        object.__setattr__(self, "_reason", reason)
        object.__setattr__(self, "_actor", actor)

    def __setattr__(self, name, value):
        raise AttributeError("Event instances are immutable")

    def __delattr__(self, name):
        raise AttributeError("Event instances are immutable")

    @property
    def id(self):
        return self._id

    @property
    def event_type(self):
        return self._event_type

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def entity_type(self):
        return self._entity_type

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def data(self):
        return self._data

    @property
    def reason(self):
        return self._reason

    @property
    def actor(self):
        return self._actor

    def to_dict(self):
        """Serialize this event into a plain JSON-compatible dict."""
        payload = {
            "id": self._id,
            "event_type": self._event_type,
            "entity_id": self._entity_id,
            "entity_type": self._entity_type,
            "timestamp": self._timestamp,
            "data": _thaw_value(self._data),
            "reason": self._reason,
        }
        if self._actor is not None:
            payload["actor"] = self._actor
        return payload

    @classmethod
    def from_dict(cls, payload):
        """Reconstruct an immutable Event from a serialized dict."""
        return cls(
            id=payload["id"],
            event_type=payload["event_type"],
            entity_id=payload["entity_id"],
            entity_type=payload["entity_type"],
            timestamp=payload["timestamp"],
            data=payload.get("data", {}),
            reason=payload.get("reason"),
            actor=payload.get("actor"),
        )

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return self._id == other._id

    def __hash__(self):
        return hash(("Event", self._id))

    def __repr__(self):
        return (
            f"Event({self._event_type!r}, "
            f"entity={self._entity_type}:{self._entity_id})"
        )
