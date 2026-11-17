"""Filtering and sorting helpers for Atlas queries across Dreams, Goals, and Tasks."""

from taskatlas._types import PRIORITY_ORDER, UNSET, _Unset

_KNOWN_FILTER_KEYS = frozenset({
    "id",
    "stage",
    "status",
    "priority",
    "tags",
    "title_contains",
    "archived",
    "blocked",
    "is_blocked",
    "held",
    "is_held",
    "stalled",
    "owner",
    "claimed",
    "has_tasks",
    "has_goals",
    "goal_id",
    "dream_id",
    "parent_id",
    "linked_to",
    "where",
    "order_by",
    "descending",
    "limit",
})


def _as_collection(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        return set(value)
    return None


def _matches(item, key, value):
    """Evaluate a single filter criterion against *item*."""
    if key == "title_contains":
        if not isinstance(value, str):
            raise TypeError("title_contains filter expects a string")
        return value.lower() in (item.title or "").lower()

    if key == "tags":
        item_tags = set(item.tags)
        required = _as_collection(value)
        if required is None:
            required = {value}
        return bool(item_tags & required)

    if key == "archived":
        if value is None:
            return True
        return item.archived == bool(value)

    if key in ("blocked", "is_blocked"):
        return bool(getattr(item, "is_blocked", False)) == bool(value)

    if key in ("held", "is_held"):
        return bool(getattr(item, "is_held", False)) == bool(value)

    if key == "stalled":
        if item._entity_type != "dream":
            return False
        return item.progress()["stalled"] == bool(value)

    if key == "claimed":
        has_owner = getattr(item, "owner", None) is not None
        return has_owner == bool(value)

    if key == "owner":
        item_owner = getattr(item, "owner", UNSET)
        if isinstance(item_owner, _Unset):
            return False
        many = _as_collection(value)
        if many is not None:
            return item_owner in many
        return item_owner == value

    if key == "has_tasks":
        if item._entity_type == "goal":
            has = bool(item.scope_tasks(recursive=True, include_archived=False))
        elif item._entity_type == "dream":
            has = bool(item.scope_tasks(include_archived=False))
        else:
            return False
        return has == bool(value)

    if key == "has_goals":
        if item._entity_type != "dream":
            return False
        has = bool(item.get_goals(recursive=True, include_archived=False))
        return has == bool(value)

    if key == "goal_id":
        if item._entity_type != "task":
            return False
        eff_goals = set(item.effective_goal_ids)
        many = _as_collection(value)
        if many is not None:
            return bool(eff_goals & many)
        if value is None:
            return len(eff_goals) == 0
        return value in eff_goals

    if key == "dream_id":
        many = _as_collection(value)
        if item._entity_type == "goal":
            did = item.effective_dream_id
            if many is not None:
                return did in many
            return did == value
        if item._entity_type == "task":
            dids = set(item.effective_dream_ids)
            if many is not None:
                return bool(dids & many)
            if value is None:
                return len(dids) == 0
            return value in dids
        return False

    if key == "parent_id":
        if item._entity_type == "task":
            pid = item.parent_task_id
        elif item._entity_type == "goal":
            pid = item.parent_goal_id
        else:
            return False
        many = _as_collection(value)
        if many is not None:
            return pid in many
        return pid == value

    if key == "linked_to":
        targets = _as_collection(value) or {value}
        for lk in item.get_links():
            other_id = lk.target_id if lk.source_id == item.id else lk.source_id
            if other_id in targets:
                return True
        return False

    if key == "where":
        if not callable(value):
            raise TypeError("where filter must be a callable predicate")
        return bool(value(item))

    attr_val = getattr(item, key, UNSET)
    if isinstance(attr_val, _Unset):
        return False
    many = _as_collection(value)
    if many is not None:
        return attr_val in many
    return attr_val == value


def filter_items(items, **criteria):
    """Apply conjunctive keyword filters, optional sorting, and result slicing."""
    unknown = set(criteria) - _KNOWN_FILTER_KEYS
    if unknown:
        raise ValueError(
            f"Unknown filter key(s): {sorted(unknown)}. "
            f"Valid keys: {sorted(_KNOWN_FILTER_KEYS)}"
        )

    archived_opt = criteria.pop("archived", UNSET)
    if isinstance(archived_opt, _Unset):
        criteria["archived"] = False
    else:
        criteria["archived"] = archived_opt

    order_by = criteria.pop("order_by", None)
    descending = criteria.pop("descending", None)
    limit = criteria.pop("limit", None)

    result = []
    for item in items:
        if all(_matches(item, k, v) for k, v in criteria.items()):
            result.append(item)

    if order_by is not None:
        result = sort_items(result, order_by, descending=descending)
    if limit is not None:
        result = result[:limit]
    return result


def sort_items(items, order_by, *, descending=None):
    """Sort *items* by a field name with sensible default direction."""
    if order_by == "priority":
        reverse = True if descending is None else bool(descending)
        return sorted(
            items,
            key=lambda x: PRIORITY_ORDER.get(getattr(x, "priority", "medium"), 0),
            reverse=reverse,
        )

    if order_by in ("created_at", "updated_at"):
        reverse = True if descending is None else bool(descending)
        return sorted(
            items,
            key=lambda x: getattr(x, order_by, ""),
            reverse=reverse,
        )

    if order_by in ("title", "id", "stage", "status"):
        reverse = False if descending is None else bool(descending)
        return sorted(
            items,
            key=lambda x: getattr(x, order_by, "") or "",
            reverse=reverse,
        )

    raise ValueError(
        f"Unsupported order_by field {order_by!r}. "
        f"Must be one of ['created_at', 'id', 'priority', 'stage', 'status', "
        f"'title', 'updated_at']"
    )
