"""Input guardrails: validate and clean an Owner before any plan is built."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pawpal_system import Owner

log = logging.getLogger("pawpal")

VALID_PRIORITIES = ("high", "medium", "low")
MAX_TASK_MIN = 480
INPUT_PENALTY = 0.05  # confidence penalty per fixed/rejected input


@dataclass
class ValidationResult:
    owner: "Owner"  # cleaned copy; the caller's original is never modified
    warnings: list[str] = field(default_factory=list)  # fixes and rejected tasks
    blocking: list[str] = field(default_factory=list)  # problems that stop planning

    @property
    def ok(self) -> bool:
        return not self.blocking


def validate_owner(owner: "Owner") -> ValidationResult:
    """Return a cleaned copy of the owner plus everything fixed, rejected or blocking."""
    clean = copy.deepcopy(owner)
    result = ValidationResult(owner=clean)

    avail = clean.available_min
    if isinstance(avail, bool) or not isinstance(avail, int) or avail <= 0:
        result.blocking.append(f"Available time must be a positive number of minutes (got {avail!r}).")
    if not clean.pets:
        result.blocking.append("Owner has no pets.")

    for pet in clean.pets:
        kept = []
        seen_titles: set[str] = set()
        for task in pet.tasks:
            title = task.title.strip() if isinstance(task.title, str) else ""
            dur = task.duration_min

            if not title:
                result.warnings.append(f"Rejected a task on {pet.name}: empty title.")
                continue
            if isinstance(dur, bool) or not isinstance(dur, int) or dur <= 0:
                result.warnings.append(
                    f"Rejected '{title}' ({pet.name}): duration must be a positive whole number (got {dur!r})."
                )
                continue
            if dur > MAX_TASK_MIN:
                result.warnings.append(
                    f"Rejected '{title}' ({pet.name}): {dur} min exceeds the {MAX_TASK_MIN} min limit."
                )
                continue
            if title.lower() in seen_titles:
                result.warnings.append(f"Dropped duplicate '{title}' on {pet.name}.")
                continue
            seen_titles.add(title.lower())

            task.title = title
            if task.priority not in VALID_PRIORITIES:
                result.warnings.append(
                    f"Fixed '{title}' ({pet.name}): unknown priority {task.priority!r}, set to 'medium'."
                )
                task.priority = "medium"
            kept.append(task)
        pet.tasks = kept

    if clean.pets and not clean.all_tasks():
        result.blocking.append("There are no valid tasks to schedule.")

    for msg in result.warnings:
        log.warning("Input guardrail: %s", msg)
    for msg in result.blocking:
        log.error("Input guardrail blocked planning: %s", msg)
    return result
