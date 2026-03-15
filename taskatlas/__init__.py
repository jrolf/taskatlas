"""taskatlas — A lean Python library for representing goals, tasks,
relationships, priority, evolution, and history."""

from taskatlas._atlas import Atlas
from taskatlas._event import Event
from taskatlas._goal import Goal
from taskatlas._link import Link
from taskatlas._task import Task

__all__ = ["Atlas", "Goal", "Task", "Link", "Event"]
__version__ = "0.0.2"
