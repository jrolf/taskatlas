"""Filtering and sorting helpers for atlas queries."""

from __future__ import annotations

from taskatlas._types import PRIORITY_ORDER, UNSET, _Unset

_KNOWN_FILTER_KEYS = frozenset({
    "stage", "status", "priority", "tags", "title_contains",
    "archived", "blocked", "has_tasks", "goal_id", "parent_id",
    "linked_to", "id", "order_by", "limit",
})


def _matches(item, key: str, value) -> bool:
    """Check whether *item* satisfies a single filter criterion."""
    if key == "title_contains":
        return value.lower() in (item.title or "").lower()

    if key == "tags":
        item_tags = set(getattr(item, "tags", []))
        required = value if isinstance(value, (list, tuple, set)) else [value]
        return bool(item_tags & set(required))

    if key == "archived":
        stage_or_status = getattr(item, "stage", None) or getattr(item, "status", None)
        is_archived = stage_or_status == "archived"
        return is_archived == value

    if key == "blocked":
        return (getattr(item, "stage", None) == "blocked") == value

    if key == "has_tasks":
        has = bool(getattr(item, "task_ids", []))
        return has == value

    if key == "goal_id":
        return value in getattr(item, "goal_ids", [])

    if key == "parent_id":
        return getattr(item, "parent_task_id", None) == value or \
               getattr(item, "parent_goal_id", None) == value

    if key == "linked_to":
        link_ids = getattr(item, "_link_ids", [])
        if not link_ids or item._atlas is None:
            return False
        for lid in link_ids:
            lk = item._atlas._links.get(lid)
            if lk and (lk.source_id == value or lk.target_id == value):
                return True
        return False

    if key == "order_by":
        return True

    attr_val = getattr(item, key, UNSET)
    if isinstance(attr_val, _Unset):
        return False
    if isinstance(value, (list, tuple, set)):
        return attr_val in value
    return attr_val == value


def filter_items(items: list, **criteria) -> list:
    """Conjunctive filter: all criteria must match."""
    unknown = set(criteria) - _KNOWN_FILTER_KEYS
    if unknown:
        raise ValueError(
            f"Unknown filter key(s): {sorted(unknown)}. "
            f"Valid keys: {sorted(_KNOWN_FILTER_KEYS)}"
        )
    include_archived = criteria.pop("archived", UNSET)

    if isinstance(include_archived, _Unset):
        criteria["archived"] = False
    else:
        criteria["archived"] = include_archived

    order_by = criteria.pop("order_by", None)
    limit = criteria.pop("limit", None)

    result = []
    for item in items:
        if all(_matches(item, k, v) for k, v in criteria.items()):
            result.append(item)

    if order_by:
        result = sort_items(result, order_by)
    if limit is not None:
        result = result[:limit]
    return result


def sort_items(items: list, order_by: str) -> list:
    """Sort items by a field name. Priority uses ordinal ranking (highest first)."""
    if order_by == "priority":
        return sorted(
            items,
            key=lambda x: PRIORITY_ORDER.get(getattr(x, "priority", "medium"), 0),
            reverse=True,
        )
    if order_by in ("created_at", "updated_at"):
        return sorted(
            items,
            key=lambda x: getattr(x, order_by, ""),
            reverse=True,
        )
    return sorted(items, key=lambda x: getattr(x, order_by, ""))
