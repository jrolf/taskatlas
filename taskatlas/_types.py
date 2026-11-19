"""Shared constants, lifecycle vocabularies, and sentinels for taskatlas."""

DREAM_STATUSES = (
    "seed",
    "active",
    "dormant",
    "realized",
    "abandoned",
)

GOAL_STATUSES = (
    "proposed",
    "active",
    "paused",
    "achieved",
    "abandoned",
)

TERMINAL_GOAL_STATUSES = frozenset({"achieved", "abandoned"})

TASK_STAGES = (
    "inbox",
    "ready",
    "active",
    "review",
    "done",
    "canceled",
)

TERMINAL_TASK_STAGES = frozenset({"done", "canceled"})

PRIORITY_LEVELS = (
    "low",
    "medium",
    "high",
    "urgent",
)

PRIORITY_ORDER = {level: idx for idx, level in enumerate(PRIORITY_LEVELS)}
PRIORITY_BY_RANK = {idx: level for idx, level in enumerate(PRIORITY_LEVELS)}

# Canonical link vocabulary:
# - depends_on: causal prerequisite between convergent/executable entities (Goal/Task)
# - relates_to: non-blocking contextual cross-reference (Dream/Goal/Task)
# - derived_from: lineage pointer to prior or inspiring work (Dream/Goal/Task)
LINK_KINDS = (
    "depends_on",
    "relates_to",
    "derived_from",
)

ENTITY_TYPES = ("dream", "goal", "task")
CAUSAL_ENTITY_TYPES = frozenset({"goal", "task"})


class _Unset:
    """Sentinel used to distinguish 'not provided' from None."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "UNSET"

    def __bool__(self):
        return False


UNSET = _Unset()
