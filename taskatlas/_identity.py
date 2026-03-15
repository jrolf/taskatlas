"""Identity generation for taskatlas entities."""

from __future__ import annotations

import uuid

_VALID_PREFIXES = frozenset({"g", "t", "lk", "ev", "n"})


def make_id(prefix: str) -> str:
    """Generate a prefixed unique identifier.

    Format: ``{prefix}-{8 hex chars}`` e.g. ``"g-a3f1b2c4"``
    """
    if prefix not in _VALID_PREFIXES:
        raise ValueError(
            f"Invalid ID prefix {prefix!r}. Must be one of {sorted(_VALID_PREFIXES)}"
        )
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def validate_id(entity_id: str, expected_prefix: str | None = None) -> str:
    """Validate that *entity_id* looks like a taskatlas ID.

    Returns the ID unchanged if valid; raises ``ValueError`` otherwise.
    """
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError(f"ID must be a non-empty string, got {entity_id!r}")

    parts = entity_id.split("-", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError(f"ID must have the form '{{prefix}}-{{hex}}', got {entity_id!r}")

    prefix = parts[0]
    if prefix not in _VALID_PREFIXES:
        raise ValueError(
            f"Unknown ID prefix {prefix!r} in {entity_id!r}. "
            f"Must be one of {sorted(_VALID_PREFIXES)}"
        )

    if expected_prefix is not None and prefix != expected_prefix:
        raise ValueError(
            f"Expected prefix {expected_prefix!r} but got {prefix!r} in {entity_id!r}"
        )

    return entity_id
