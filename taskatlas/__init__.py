"""taskatlas - A lean, zero-dependency Python engine for Dreams, Goals, Tasks,
causal readiness, and operational continuity."""

from taskatlas._atlas import Atlas
from taskatlas._dream import Dream
from taskatlas._event import Event
from taskatlas._goal import Goal
from taskatlas._link import Link
from taskatlas._task import Task

__all__ = ["Atlas", "Dream", "Goal", "Task", "Link", "Event"]
__version__ = "0.1.0"
