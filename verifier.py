"""Plan verifier: checks a Plan against the owner's constraints and scores confidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a circular import at runtime
    from pawpal_system import Owner, Plan

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

ERROR_PENALTY = 0.3
WARNING_PENALTY = 0.1
ROUND_PENALTY = 0.05
REVIEW_THRESHOLD = 0.7
LOW_UTILIZATION = 0.5


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


def verify(plan: "Plan", owner: "Owner") -> list[Issue]:
    """Return every problem found in the plan (empty list means it passed)."""
    issues: list[Issue] = []

    # Duplicates: the same task object scheduled more than once.
    seen: set[int] = set()
    for task in plan.scheduled:
        if id(task) in seen:
            issues.append(
                Issue("error", "duplicate", f"'{task.title}' ({task.pet_name}) is scheduled twice.")
            )
        seen.add(id(task))

    # Time budget.
    if plan.total_min > owner.available_min:
        issues.append(
            Issue(
                "error",
                "over_budget",
                f"Plan uses {plan.total_min} min but only {owner.available_min} min are available.",
            )
        )

    # High-priority coverage.
    high_kept = sum(t.duration_min for t in plan.scheduled if t.priority == "high")
    has_lower_scheduled = any(t.priority != "high" for t in plan.scheduled)
    for task in plan.skipped:
        if task.priority != "high":
            continue
        fits_if_swapped = high_kept + task.duration_min <= owner.available_min
        if has_lower_scheduled and fits_if_swapped:
            issues.append(
                Issue(
                    "error",
                    "priority_inversion",
                    f"High-priority '{task.title}' ({task.pet_name}) was skipped although "
                    "lower-priority tasks were scheduled and it could replace them.",
                )
            )
        else:
            issues.append(
                Issue(
                    "warning",
                    "skipped_high",
                    f"High-priority '{task.title}' ({task.pet_name}) was skipped for lack of time.",
                )
            )

    # Low utilization.
    if plan.skipped and owner.available_min > 0:
        if plan.total_min / owner.available_min < LOW_UTILIZATION:
            issues.append(
                Issue(
                    "warning",
                    "low_utilization",
                    f"Only {plan.total_min} of {owner.available_min} min used while "
                    f"{len(plan.skipped)} task(s) were skipped.",
                )
            )

    return issues


def confidence_score(issues: list[Issue], rounds: int) -> float:
    """Score 0-1: starts at 1.0, minus penalties for issues and repair rounds."""
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    score = 1.0 - ERROR_PENALTY * errors - WARNING_PENALTY * warnings - ROUND_PENALTY * rounds
    return round(max(0.0, min(1.0, score)), 2)
