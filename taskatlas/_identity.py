"""Identity generation and validation for taskatlas entities."""

import uuid

_VALID_PREFIXES = frozenset({"d", "g", "t", "lk", "ev", "n"})


def make_id(prefix, existing=None):
    """Generate a prefixed unique identifier such as ``'t-a3f1b2c4'``.

    Parameters
    ----------
    prefix : str
        Entity prefix from ``{'d', 'g', 't', 'lk', 'ev', 'n'}``.
    existing : container or None
        Optional collection of in-use IDs; if supplied, regenerates on collision.
    """
    if prefix not in _VALID_PREFIXES:
        raise ValueError(
            f"Invalid ID prefix {prefix!r}. Must be one of {sorted(_VALID_PREFIXES)}"
        )

    for _ in range(16):
        candidate = f"{prefix}-{uuid.uuid4().hex[:8]}"
        if existing is None or candidate not in existing:
            return candidate

    # Fallback to full 12-hex suffix if a tiny prefix pool ever collides repeatedly
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def validate_id(entity_id, expected_prefix=None):
    """Validate that *entity_id* has a valid taskatlas prefix and body.

    Returns *entity_id* unchanged when valid; raises ``ValueError`` otherwise.
    """
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError(f"ID must be a non-empty string, got {entity_id!r}")

    parts = entity_id.split("-", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError(
            f"ID must have the form '{{prefix}}-{{hex}}', got {entity_id!r}"
        )

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
