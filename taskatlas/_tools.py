"""Zero-dependency LLM agent tool schemas and structured tool dispatch for Atlas."""

import copy
import json

from taskatlas._types import (
    DREAM_STATUSES,
    GOAL_STATUSES,
    LINK_KINDS,
    PRIORITY_LEVELS,
    TASK_STAGES,
)

_TOOL_SCHEMAS = (
    {
        "name": "atlas_orient",
        "description": (
            "Get a token-tight situational briefing and prioritized ready queue "
            "for the Atlas, optionally scoped to a specific Dream or Goal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dream_id": {
                    "type": "string",
                    "description": "Optional Dream ID ('d-...') to scope orientation.",
                },
                "goal_id": {
                    "type": "string",
                    "description": "Optional Goal ID ('g-...') to scope orientation.",
                },
                "format": {
                    "type": "string",
                    "enum": ["brief", "structured"],
                    "description": "Return compact Markdown ('brief') or dicts ('structured').",
                },
                "queue_limit": {
                    "type": "integer",
                    "description": "Max ready tasks to include (default 5).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "atlas_inspect",
        "description": (
            "Inspect hydrated neighborhood context, blockers, upstream receipts, "
            "notes, and recent history for any Dream, Goal, or Task by ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Entity ID ('d-...', 'g-...', or 't-...').",
                },
                "mode": {
                    "type": "string",
                    "enum": ["compact", "full", "brief"],
                    "description": "Detail level (default 'full').",
                },
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "atlas_upsert_dream",
        "description": (
            "Create a new top-level Dream vision (when dream_id is omitted) or "
            "update an existing Dream's status, vision, title, summary, or priority."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dream_id": {
                    "type": "string",
                    "description": "Existing Dream ID ('d-...') to update; omit to create.",
                },
                "title": {"type": "string", "description": "Dream title."},
                "vision": {
                    "type": "string",
                    "description": "Enduring north-star vision description.",
                },
                "summary": {"type": "string", "description": "Short summary."},
                "status": {"type": "string", "enum": list(DREAM_STATUSES)},
                "priority": {"type": "string", "enum": list(PRIORITY_LEVELS)},
                "tags": {"type": "array", "items": {"type": "string"}},
                "archive": {"type": "boolean"},
                "reason": {
                    "type": "string",
                    "description": "Causal reason recorded in history for updates.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "atlas_upsert_goal",
        "description": (
            "Create a new convergent Goal (when goal_id is omitted) or update an "
            "existing Goal's status, criteria, outcome, priority, or Dream attachment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_id": {
                    "type": "string",
                    "description": "Existing Goal ID ('g-...') to update; omit to create.",
                },
                "title": {"type": "string", "description": "Goal title."},
                "summary": {"type": "string", "description": "Goal summary."},
                "status": {"type": "string", "enum": list(GOAL_STATUSES)},
                "priority": {"type": "string", "enum": list(PRIORITY_LEVELS)},
                "dream_id": {
                    "type": "string",
                    "description": "Optional parent Dream ID ('d-...') for root goals.",
                },
                "parent_goal_id": {
                    "type": "string",
                    "description": "Optional parent Goal ID ('g-...') for subgoals.",
                },
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Falsifiable acceptance criteria.",
                },
                "outcome": {
                    "type": "string",
                    "description": "Outcome summary when achieved or abandoned.",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
                "archive": {"type": "boolean"},
                "reason": {
                    "type": "string",
                    "description": "Causal reason recorded in history for updates.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "atlas_add_task",
        "description": (
            "Create a new executable Task, optionally attached to a Goal, nested "
            "as a subtask, and wired with causal depends_on prerequisite IDs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Actionable task title."},
                "summary": {"type": "string", "description": "Detailed task scope."},
                "stage": {
                    "type": "string",
                    "enum": ["inbox", "ready", "active", "review"],
                },
                "priority": {"type": "string", "enum": list(PRIORITY_LEVELS)},
                "goal_id": {
                    "type": "string",
                    "description": "Goal ID ('g-...') this task advances.",
                },
                "parent_task_id": {
                    "type": "string",
                    "description": "Parent Task ID ('t-...') when decomposing into subtasks.",
                },
                "depends_on_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Goal/Task IDs that must finish before this task is ready.",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
    },
    {
        "name": "atlas_update_task",
        "description": (
            "Update an in-progress Task: move non-terminal stage, change priority, "
            "claim/release worker ownership, place/clear an external hold, or archive."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID ('t-...')."},
                "stage": {
                    "type": "string",
                    "enum": ["inbox", "ready", "active", "review"],
                },
                "priority": {"type": "string", "enum": list(PRIORITY_LEVELS)},
                "claim": {
                    "type": "string",
                    "description": "Worker/agent identifier claiming this task.",
                },
                "release": {
                    "type": "boolean",
                    "description": "Set true to release current worker claim.",
                },
                "hold_reason": {
                    "type": "string",
                    "description": "Non-empty reason to place task on external hold.",
                },
                "unhold": {
                    "type": "boolean",
                    "description": "Set true to clear an active external hold.",
                },
                "archive": {"type": "boolean"},
                "reason": {
                    "type": "string",
                    "description": "Causal reason for the state transition.",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "atlas_complete_task",
        "description": (
            "Finish a Task as 'done' (with summary, artifact paths, and structured "
            "data receipt) or 'canceled' (dropping obsolete work without blocking progress)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID ('t-...')."},
                "resolution": {
                    "type": "string",
                    "enum": ["done", "canceled"],
                    "description": "Terminal resolution (default 'done').",
                },
                "summary": {
                    "type": "string",
                    "description": "Summary of deliverables produced or cancellation reason.",
                },
                "artifacts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths or URIs produced by this task.",
                },
                "data": {
                    "type": "object",
                    "description": "Structured metrics or output metadata.",
                },
                "superseded_by": {
                    "type": "string",
                    "description": "Optional replacement Task ID when canceled.",
                },
                "archive": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "atlas_note",
        "description": (
            "Append a timestamped narrative note (with optional metadata) to any entity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Dream, Goal, or Task ID.",
                },
                "text": {"type": "string", "description": "Non-empty note body."},
                "meta": {"type": "object"},
            },
            "required": ["entity_id", "text"],
        },
    },
    {
        "name": "atlas_link",
        "description": (
            "Create or remove a typed relationship ('depends_on', 'relates_to', "
            "'derived_from') between two entities."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "kind": {"type": "string", "enum": list(LINK_KINDS)},
                "remove": {
                    "type": "boolean",
                    "description": "Set true to unlink instead of creating the link.",
                },
                "reason": {"type": "string"},
            },
            "required": ["source_id", "target_id", "kind"],
        },
    },
)

_SCHEMA_BY_NAME = {schema["name"]: schema for schema in _TOOL_SCHEMAS}


def get_tool_schemas():
    """Return deep-copied JSON Schema descriptors for all TaskAtlas agent tools."""
    return copy.deepcopy(list(_TOOL_SCHEMAS))


def _ok(tool_name, result):
    return {"ok": True, "tool": tool_name, "result": result}


def _err(tool_name, message, hint=""):
    payload = {"ok": False, "tool": tool_name, "error": message}
    if hint:
        payload["hint"] = hint
    return payload


def _expect_str_list(value, field_name):
    """Ensure optional list arguments from LLMs are JSON arrays of strings, not bare strings."""
    if value is None:
        return []
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise TypeError(
            f"Parameter {field_name!r} must be a list of strings, "
            f"got {type(value).__name__}"
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Each entry in {field_name!r} must be a non-empty string")
    return list(value)


def _parse_arguments(raw_args):
    if raw_args is None:
        return {}
    if isinstance(raw_args, str):
        stripped = raw_args.strip()
        if not stripped:
            return {}
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("JSON tool arguments must decode to an object")
        return parsed
    if isinstance(raw_args, dict):
        return dict(raw_args)
    raise TypeError(
        f"Tool arguments must be a dict or JSON string, got {type(raw_args).__name__}"
    )


def dispatch_tool(atlas, tool_name, arguments=None, *, actor=None):
    """Validate and execute one named tool call against *atlas*.

    Always returns a JSON-serializable receipt dict ``{'ok': bool, ...}`` with
    actionable error hints on invalid IDs, lifecycle violations, or cycles.
    """
    if tool_name not in _SCHEMA_BY_NAME:
        return _err(
            tool_name,
            f"Unknown tool {tool_name!r}",
            hint=f"Valid tools: {sorted(_SCHEMA_BY_NAME)}",
        )

    try:
        args = _parse_arguments(arguments)
    except (ValueError, TypeError) as exc:
        return _err(
            tool_name,
            f"Invalid tool arguments: {exc}",
            hint="Pass a JSON object matching the tool's parameter schema.",
        )

    try:
        if tool_name == "atlas_orient":
            fmt = args.get("format", "brief")
            dream_id = args.get("dream_id")
            goal_id = args.get("goal_id")
            q_limit = args.get("queue_limit", 5)
            if fmt == "brief":
                return _ok(
                    tool_name,
                    {
                        "brief": atlas.brief(
                            dream_id=dream_id,
                            goal_id=goal_id,
                            queue_limit=q_limit,
                        )
                    },
                )
            if fmt == "structured":
                return _ok(
                    tool_name,
                    {
                        "summary": atlas.summary(),
                        "queue": atlas.queue(
                            dream_id=dream_id,
                            goal_id=goal_id,
                            limit=q_limit,
                        ),
                    },
                )
            raise ValueError(f"Invalid format {fmt!r}; expected 'brief' or 'structured'")

        if tool_name == "atlas_inspect":
            entity_id = args.get("entity_id")
            if not entity_id:
                raise ValueError("Missing required parameter 'entity_id'")
            entity = atlas.get_entity(entity_id)
            mode = args.get("mode", "full")
            if mode == "brief":
                return _ok(tool_name, {"id": entity.id, "brief": entity.brief()})
            return _ok(tool_name, entity.context(mode=mode))

        if tool_name == "atlas_upsert_dream":
            dream_id = args.get("dream_id")
            reason = args.get("reason")
            if dream_id is None:
                title = args.get("title")
                if not title:
                    raise ValueError("Creating a Dream requires 'title'")
                dream = atlas.add_dream(
                    title=title,
                    vision=args.get("vision", ""),
                    summary=args.get("summary", ""),
                    status=args.get("status", "seed"),
                    priority=args.get("priority", "medium"),
                    tags=args.get("tags"),
                    actor=actor,
                )
                if args.get("archive"):
                    dream.archive(reason=reason, actor=actor)
                return _ok(tool_name, dream.context(mode="compact"))

            dream = atlas.get_dream(dream_id)
            if "title" in args and args["title"] is not None:
                dream.set_title(args["title"], reason=reason, actor=actor)
            if "vision" in args and args["vision"] is not None:
                dream.set_vision(args["vision"], reason=reason, actor=actor)
            if "summary" in args and args["summary"] is not None:
                dream.set_summary(args["summary"], reason=reason, actor=actor)
            if "status" in args and args["status"] is not None:
                dream.set_status(args["status"], reason=reason, actor=actor)
            if "priority" in args and args["priority"] is not None:
                dream.set_priority(args["priority"], reason=reason, actor=actor)
            for tag in _expect_str_list(args.get("tags"), "tags"):
                dream.add_tag(tag, actor=actor)
            if args.get("archive") is True:
                dream.archive(reason=reason, actor=actor)
            elif args.get("archive") is False:
                dream.unarchive(reason=reason, actor=actor)
            return _ok(tool_name, dream.context(mode="compact"))

        if tool_name == "atlas_upsert_goal":
            goal_id = args.get("goal_id")
            reason = args.get("reason")
            if goal_id is None:
                title = args.get("title")
                if not title:
                    raise ValueError("Creating a Goal requires 'title'")
                goal = atlas.add_goal(
                    title=title,
                    summary=args.get("summary", ""),
                    status=args.get("status", "proposed"),
                    priority=args.get("priority", "medium"),
                    dream_id=args.get("dream_id"),
                    parent_goal_id=args.get("parent_goal_id"),
                    criteria=args.get("criteria"),
                    outcome=args.get("outcome", ""),
                    tags=args.get("tags"),
                    actor=actor,
                )
                if args.get("archive"):
                    goal.archive(reason=reason, actor=actor)
                return _ok(tool_name, goal.context(mode="compact"))

            goal = atlas.get_goal(goal_id)
            if "title" in args and args["title"] is not None:
                goal.set_title(args["title"], reason=reason, actor=actor)
            if "summary" in args and args["summary"] is not None:
                goal.set_summary(args["summary"], reason=reason, actor=actor)
            if "dream_id" in args and args["dream_id"] is not None:
                atlas.get_dream(args["dream_id"]).attach_goal(
                    goal, reason=reason, actor=actor
                )
            if "parent_goal_id" in args and args["parent_goal_id"] is not None:
                atlas.get_goal(args["parent_goal_id"]).attach_goal(
                    goal, reason=reason, actor=actor
                )
            for crit in _expect_str_list(args.get("criteria"), "criteria"):
                goal.add_criterion(crit, actor=actor)
            if "status" in args and args["status"] is not None:
                goal.set_status(
                    args["status"],
                    reason=reason,
                    outcome=args.get("outcome"),
                    actor=actor,
                )
            elif "outcome" in args and args["outcome"] is not None:
                goal.set_outcome(args["outcome"], reason=reason, actor=actor)
            if "priority" in args and args["priority"] is not None:
                goal.set_priority(args["priority"], reason=reason, actor=actor)
            for tag in _expect_str_list(args.get("tags"), "tags"):
                goal.add_tag(tag, actor=actor)
            if args.get("archive") is True:
                goal.archive(reason=reason, actor=actor)
            elif args.get("archive") is False:
                goal.unarchive(reason=reason, actor=actor)
            return _ok(tool_name, goal.context(mode="compact"))

        if tool_name == "atlas_add_task":
            title = args.get("title")
            if not title:
                raise ValueError("atlas_add_task requires a non-empty 'title'")
            stage = args.get("stage", "inbox")
            if stage in ("done", "canceled"):
                raise ValueError(
                    "Create tasks in an active workflow stage ('inbox', 'ready', "
                    "'active', 'review') and finish them via atlas_complete_task"
                )
            goal_ids = [args["goal_id"]] if args.get("goal_id") else None
            dep_ids = _expect_str_list(args.get("depends_on_ids"), "depends_on_ids")
            dep_targets = [atlas.get_entity(dep_id) for dep_id in dep_ids]
            task = atlas.add_task(
                title=title,
                summary=args.get("summary", ""),
                stage=stage,
                priority=args.get("priority", "medium"),
                goal_ids=goal_ids,
                parent_task_id=args.get("parent_task_id"),
                tags=args.get("tags"),
                actor=actor,
            )
            for dep_target in dep_targets:
                task.link(dep_target, kind="depends_on", actor=actor)
            return _ok(tool_name, task.context(mode="compact"))

        if tool_name == "atlas_update_task":
            task_id = args.get("task_id")
            if not task_id:
                raise ValueError("Missing required parameter 'task_id'")
            task = atlas.get_task(task_id)
            reason = args.get("reason")

            if args.get("release"):
                task.release(reason=reason, actor=actor)
            if args.get("claim"):
                task.claim(args["claim"], reason=reason, actor=actor)
            if args.get("unhold"):
                task.unhold(reason=reason, actor=actor)
            if args.get("hold_reason"):
                task.hold(args["hold_reason"], actor=actor)
            if "stage" in args and args["stage"] is not None:
                if args["stage"] in ("done", "canceled"):
                    raise ValueError(
                        f"Use 'atlas_complete_task' to transition a task to "
                        f"{args['stage']!r} with a completion receipt"
                    )
                if args["stage"] not in TASK_STAGES:
                    raise ValueError(f"Invalid stage {args['stage']!r}")
                task.move(args["stage"], reason=reason, actor=actor)
            if "priority" in args and args["priority"] is not None:
                task.set_priority(args["priority"], reason=reason, actor=actor)
            if args.get("archive") is True:
                task.archive(reason=reason, actor=actor)
            elif args.get("archive") is False:
                task.unarchive(reason=reason, actor=actor)
            return _ok(tool_name, task.context(mode="compact"))

        if tool_name == "atlas_complete_task":
            task_id = args.get("task_id")
            if not task_id:
                raise ValueError("Missing required parameter 'task_id'")
            task = atlas.get_task(task_id)
            resolution = args.get("resolution", "done")
            summary = args.get("summary", "")
            reason = args.get("reason")
            archive = bool(args.get("archive", False))

            if resolution == "done":
                receipt = task.complete(
                    summary=summary,
                    artifacts=args.get("artifacts"),
                    data=args.get("data"),
                    reason=reason,
                    archive=archive,
                    actor=actor,
                )
            elif resolution == "canceled":
                receipt = task.cancel(
                    reason=reason or summary or "Canceled",
                    superseded_by=args.get("superseded_by"),
                    archive=archive,
                    actor=actor,
                )
            else:
                raise ValueError(
                    f"Invalid resolution {resolution!r}; expected 'done' or 'canceled'"
                )
            return _ok(
                tool_name,
                {"task": task.context(mode="compact"), "receipt": receipt},
            )

        if tool_name == "atlas_note":
            entity_id = args.get("entity_id")
            text = args.get("text")
            if not entity_id or not text:
                raise ValueError("atlas_note requires both 'entity_id' and 'text'")
            entity = atlas.get_entity(entity_id)
            entry = entity.note(text, meta=args.get("meta"), actor=actor)
            return _ok(tool_name, {"entity_id": entity.id, "note": entry})

        if tool_name == "atlas_link":
            source_id = args.get("source_id")
            target_id = args.get("target_id")
            kind = args.get("kind")
            if not source_id or not target_id or not kind:
                raise ValueError(
                    "atlas_link requires 'source_id', 'target_id', and 'kind'"
                )
            source = atlas.get_entity(source_id)
            target = atlas.get_entity(target_id)
            reason = args.get("reason")
            if args.get("remove"):
                removed = source.unlink(
                    target=target,
                    kind=kind,
                    direction="outgoing",
                    reason=reason,
                    actor=actor,
                )
                return _ok(tool_name, {"removed": removed})
            lk = source.link(target, kind=kind, reason=reason, actor=actor)
            return _ok(tool_name, lk.to_dict())

    except KeyError as exc:
        return _err(
            tool_name,
            str(exc),
            hint="Call 'atlas_orient' first to verify existing Dream, Goal, and Task IDs.",
        )
    except (ValueError, TypeError) as exc:
        return _err(
            tool_name,
            str(exc),
            hint="Inspect the entity with 'atlas_inspect' and verify allowed lifecycle values.",
        )

    return _err(tool_name, f"Unhandled tool {tool_name!r}")


def build_bound_tools(atlas, *, actor=None):
    """Build ``[{name, description, parameters, fn}, ...]`` specs bound to *atlas*.

    Compatible directly with ThoughtFlow::

        tools = [TOOL(**spec) for spec in atlas.as_tools(actor="agent:worker")]
    """
    specs = []
    for schema in get_tool_schemas():
        name = schema["name"]

        def _make_fn(bound_name):
            def _call(arguments=None, **kwargs):
                if arguments is None:
                    return dispatch_tool(atlas, bound_name, kwargs, actor=actor)
                if isinstance(arguments, dict) and kwargs:
                    merged = dict(arguments)
                    merged.update(kwargs)
                    return dispatch_tool(atlas, bound_name, merged, actor=actor)
                return dispatch_tool(atlas, bound_name, arguments, actor=actor)

            return _call

        specs.append({
            "name": name,
            "description": schema["description"],
            "parameters": schema["parameters"],
            "fn": _make_fn(name),
        })
    return specs
