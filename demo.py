"""Runs three example inputs through PawPal+ end to end and prints the results.

Usage:  python demo.py
Full log (including guardrail warnings) is written to pawpal.log.
"""

from __future__ import annotations

import logging

from logging_setup import setup_logging
from pawpal_system import Owner, Pet, Scheduler, Task


def make_owner(available_min: int, tasks: list[Task]) -> Owner:
    owner = Owner("Jordan", available_min=available_min)
    pet = Pet("Mochi")
    for task in tasks:
        pet.add_task(task)
    owner.add_pet(pet)
    return owner


def describe(task: Task) -> str:
    return f"{task.title or '(no title)'} ({task.duration_min}m, {task.priority})"


def run(title: str, owner: Owner) -> None:
    print(f"=== {title} ===")
    print(f"Available: {owner.available_min} min")
    print("Tasks:     " + ", ".join(describe(t) for t in owner.all_tasks()))
    print()

    plan = Scheduler().plan_safely(owner)
    if plan.error:
        print(f"ERROR: {plan.error}\n")
        return

    print(
        f"Time used: {plan.total_min}/{owner.available_min} min | Confidence: {plan.confidence:.2f} "
        f"| Repairs: {plan.rounds} | Needs review: {plan.needs_review}"
    )
    print("Scheduled: " + (", ".join(t.title for t in plan.scheduled) or "-"))
    print("Skipped:   " + (", ".join(describe(t) for t in plan.skipped) or "-"))
    for line in plan.explanation:
        print(f"  - {line}")
    for issue in plan.issues:
        print(f"  issue: {issue}")
    for warning in plan.warnings:
        print(f"  guardrail: {warning}")
    print()


def main() -> None:
    logger = setup_logging()
    # Keep the demo output readable: warnings still go to pawpal.log, just not the console.
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.CRITICAL)

    run(
        "Run 1: normal day",
        make_owner(90, [
            Task("Morning walk", 30, "high"),
            Task("Feed breakfast", 10, "high"),
            Task("Give medication", 5, "high"),
            Task("Grooming", 40, "low"),
            Task("Fetch in the yard", 25, "medium"),
        ]),
    )
    run(
        "Run 2: a high-priority task that cannot fit",
        make_owner(30, [
            Task("Vet visit", 90, "high"),
            Task("Feed breakfast", 10, "high"),
            Task("Grooming", 15, "low"),
        ]),
    )
    run(
        "Run 3: messy input",
        make_owner(60, [
            Task("Morning walk", 30, "high"),
            Task("", 10, "low"),
            Task("Nap", -5, "low"),
            Task("Feed breakfast", 10, "URGENT"),
            Task("morning walk", 15, "low"),
            Task("Hike", 600, "low"),
        ]),
    )


if __name__ == "__main__":
    main()
