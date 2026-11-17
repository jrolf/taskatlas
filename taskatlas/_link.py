"""Link model for typed cross-references between taskatlas entities."""

import copy
from datetime import datetime, timezone
from types import MappingProxyType

from taskatlas._identity import make_id
from taskatlas._types import CAUSAL_ENTITY_TYPES, ENTITY_TYPES, LINK_KINDS


class Link:
    """A typed, directed cross-reference between two entities in an Atlas.

    Causal ``depends_on`` links are restricted to convergent/executable entities
    (``Goal`` and ``Task``) so open-horizon ``Dream`` objects never create
    permanent topological deadlocks. Non-blocking ``relates_to`` and
    ``derived_from`` links may connect any combination of ``Dream``, ``Goal``,
    and ``Task``.
    """

    __slots__ = (
        "_id",
        "_source_id",
        "_source_type",
        "_target_id",
        "_target_type",
        "_kind",
        "_created_at",
        "_meta",
    )

    def __init__(
        self,
        *,
        source_id,
        source_type,
        target_id,
        target_type,
        kind,
        meta=None,
        id=None,
        created_at=None,
    ):
        if kind not in LINK_KINDS:
            raise ValueError(
                f"Invalid link kind {kind!r}. Must be one of {list(LINK_KINDS)}"
            )
        if source_type not in ENTITY_TYPES:
            raise ValueError(
                f"source_type must be one of {list(ENTITY_TYPES)}, got {source_type!r}"
            )
        if target_type not in ENTITY_TYPES:
            raise ValueError(
                f"target_type must be one of {list(ENTITY_TYPES)}, got {target_type!r}"
            )
        if source_id == target_id:
            raise ValueError("Cannot link an entity to itself")

        if kind == "depends_on":
            if (
                source_type not in CAUSAL_ENTITY_TYPES
                or target_type not in CAUSAL_ENTITY_TYPES
            ):
                raise ValueError(
                    "Causal 'depends_on' links are only allowed between Goals and "
                    "Tasks; use 'relates_to' or 'derived_from' when linking a Dream"
                )

        object.__setattr__(self, "_id", id or make_id("lk"))
        object.__setattr__(self, "_source_id", source_id)
        object.__setattr__(self, "_source_type", source_type)
        object.__setattr__(self, "_target_id", target_id)
        object.__setattr__(self, "_target_type", target_type)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(
            self,
            "_created_at",
            created_at or datetime.now(timezone.utc).isoformat(),
        )
        copied_meta = copy.deepcopy(dict(meta)) if meta else {}
        object.__setattr__(self, "_meta", MappingProxyType(copied_meta))

    def __setattr__(self, name, value):
        raise AttributeError("Link instances are immutable")

    def __delattr__(self, name):
        raise AttributeError("Link instances are immutable")

    @property
    def id(self):
        return self._id

    @property
    def source_id(self):
        return self._source_id

    @property
    def source_type(self):
        return self._source_type

    @property
    def target_id(self):
        return self._target_id

    @property
    def target_type(self):
        return self._target_type

    @property
    def kind(self):
        return self._kind

    @property
    def created_at(self):
        return self._created_at

    @property
    def meta(self):
        return self._meta

    def to_dict(self):
        """Serialize this link into a plain JSON-compatible dict."""
        return {
            "id": self._id,
            "source_id": self._source_id,
            "source_type": self._source_type,
            "target_id": self._target_id,
            "target_type": self._target_type,
            "kind": self._kind,
            "created_at": self._created_at,
            "meta": copy.deepcopy(dict(self._meta)),
        }

    @classmethod
    def from_dict(cls, payload):
        """Reconstruct a Link from a serialized dict."""
        return cls(
            id=payload["id"],
            source_id=payload["source_id"],
            source_type=payload["source_type"],
            target_id=payload["target_id"],
            target_type=payload["target_type"],
            kind=payload["kind"],
            created_at=payload.get("created_at"),
            meta=payload.get("meta", {}),
        )

    def __eq__(self, other):
        if not isinstance(other, Link):
            return NotImplemented
        return self._id == other._id

    def __hash__(self):
        return hash(("Link", self._id))

    def __repr__(self):
        return (
            f"Link({self._source_type}:{self._source_id} "
            f"--{self._kind}--> "
            f"{self._target_type}:{self._target_id})"
        )
