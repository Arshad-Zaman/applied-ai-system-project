"""PawPal+ core system: owner, pets, tasks, and a priority-based scheduler."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from guardrails import INPUT_PENALTY, validate_owner
from logging_setup import setup_logging
from verifier import REVIEW_THRESHOLD, Issue, confidence_score, verify

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

log = logging.getLogger("pawpal")


@dataclass
class Task:
    title: str
    duration_min: int
    priority: str = "medium"  # "high" | "medium" | "low"
    pet_name: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.priority, str):
            self.priority = self.priority.strip().lower()


@dataclass
class Pet:
    name: str
    species: str = "dog"
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        task.pet_name = self.name
        self.tasks.append(task)


@dataclass
class Owner:
    name: str
    available_min: int = 120
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        self.pets.append(pet)

    def all_tasks(self) -> list[Task]:
        return [t for pet in self.pets for t in pet.tasks]


@dataclass
class Plan:
    scheduled: list[Task]
    skipped: list[Task]
    explanation: list[str]
    confidence: float = 1.0
    issues: list[Issue] = field(default_factory=list)
    rounds: int = 0
    warnings: list[str] = field(default_factory=list)  # inputs fixed or rejected
    error: str = ""  # set when planning was blocked or crashed

    @property
    def total_min(self) -> int:
        return sum(t.duration_min for t in self.scheduled)

    @property
    def needs_review(self) -> bool:
        return self.confidence < REVIEW_THRESHOLD


class Scheduler:
    """Fits tasks into the owner's available time, highest priority first."""

    def build_plan(self, owner: Owner) -> Plan:
        ordered = sorted(
            owner.all_tasks(),
            key=lambda t: (PRIORITY_RANK.get(t.priority, 1), t.duration_min),
        )
        scheduled: list[Task] = []
        skipped: list[Task] = []
        explanation: list[str] = []
        used = 0

        for task in ordered:
            if used + task.duration_min <= owner.available_min:
                scheduled.append(task)
                used += task.duration_min
                explanation.append(
                    f"Scheduled '{task.title}' ({task.pet_name}, {task.priority} priority, "
                    f"{task.duration_min} min)."
                )
            else:
                skipped.append(task)
                explanation.append(
                    f"Skipped '{task.title}' ({task.pet_name}, {task.priority} priority): "
                    f"needs {task.duration_min} min but only {owner.available_min - used} min left."
                )

        return Plan(scheduled, skipped, explanation)

    # ------------------------------------------------------------------
    # Self-check loop: build -> verify -> repair -> verify (max_rounds)
    # ------------------------------------------------------------------
    def build_plan_checked(self, owner: Owner, max_rounds: int = 3) -> Plan:
        plan = self.build_plan(owner)
        return self.check_and_repair(plan, owner, max_rounds)

    def check_and_repair(self, plan: Plan, owner: Owner, max_rounds: int = 3) -> Plan:
        """Verify a plan and repair errors until it passes or rounds run out."""
        rounds = 0
        issues = verify(plan, owner)
        while any(i.severity == "error" for i in issues) and rounds < max_rounds:
            rounds += 1
            for note in self._repair(plan, owner, issues):
                plan.explanation.append(f"Repair round {rounds}: {note}")
                log.info("Repair round %d: %s", rounds, note)
            issues = verify(plan, owner)

        plan.issues = issues
        plan.rounds = rounds
        plan.confidence = confidence_score(issues, rounds)
        log.info(
            "Plan verified: %d min scheduled, %d skipped, confidence %.2f, %d repair round(s), %d issue(s).",
            plan.total_min, len(plan.skipped), plan.confidence, rounds, len(issues),
        )
        return plan

    # ------------------------------------------------------------------
    # Safe entry point: validate input -> checked plan -> never crash
    # ------------------------------------------------------------------
    def plan_safely(self, owner: Owner) -> Plan:
        setup_logging()
        try:
            result = validate_owner(owner)
            if not result.ok:
                msg = " ".join(result.blocking)
                return Plan([], [], [], confidence=0.0, warnings=result.warnings, error=msg)

            plan = self.build_plan_checked(result.owner)
            plan.warnings = result.warnings
            penalty = INPUT_PENALTY * len(result.warnings)
            plan.confidence = round(max(0.0, plan.confidence - penalty), 2)
            return plan
        except Exception as exc:  # last-resort guardrail: the UI must not crash
            log.exception("Unexpected error while planning")
            return Plan([], [], [], confidence=0.0, error=f"Unexpected error: {exc}")

    @staticmethod
    def _drop_order(task: Task) -> tuple[int, int]:
        """Lowest priority first, then longest first."""
        return (-PRIORITY_RANK.get(task.priority, 1), -task.duration_min)

    def _repair(self, plan: Plan, owner: Owner, issues: list[Issue]) -> list[str]:
        notes: list[str] = []
        codes = {i.code for i in issues if i.severity == "error"}

        if "duplicate" in codes:
            unique: list[Task] = []
            for task in plan.scheduled:
                if any(task is u for u in unique):
                    notes.append(f"removed duplicate '{task.title}'.")
                else:
                    unique.append(task)
            plan.scheduled = unique

        if "over_budget" in codes:
            while plan.total_min > owner.available_min and plan.scheduled:
                victim = min(plan.scheduled, key=self._drop_order)
                plan.scheduled.remove(victim)
                plan.skipped.append(victim)
                notes.append(f"dropped '{victim.title}' to fit the time budget.")

        if "priority_inversion" in codes:
            for task in [t for t in plan.skipped if t.priority == "high"]:
                lower = sorted(
                    (t for t in plan.scheduled if t.priority != "high"), key=self._drop_order
                )
                free = owner.available_min - plan.total_min
                dropped: list[Task] = []
                for victim in lower:
                    if free >= task.duration_min:
                        break
                    dropped.append(victim)
                    free += victim.duration_min
                if free >= task.duration_min and dropped:
                    for victim in dropped:
                        plan.scheduled.remove(victim)
                        plan.skipped.append(victim)
                    plan.skipped.remove(task)
                    plan.scheduled.append(task)
                    names = ", ".join(f"'{v.title}'" for v in dropped)
                    notes.append(f"swapped in high-priority '{task.title}' for {names}.")

        return notes
