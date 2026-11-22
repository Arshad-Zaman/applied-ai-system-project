"""Evaluation harness: runs labeled scenarios through PawPal+ and prints a pass/fail table.

Usage:  python eval.py
Exit code is 1 if any scenario fails.
"""

from __future__ import annotations

import sys

from pawpal_system import Owner, Pet, Plan, Scheduler, Task


def make_owner(avail: int, tasks: list[Task]) -> Owner:
    owner = Owner("Sam", available_min=avail)
    pet = Pet("Rex")
    for t in tasks:
        pet.add_task(t)
    owner.add_pet(pet)
    return owner


def titles(plan: Plan) -> list[str]:
    return [t.title for t in plan.scheduled]


# Each scenario returns (plan, passed, note).
def s_normal():
    o = make_owner(120, [Task("Walk", 30, "high"), Task("Feed", 10, "high"), Task("Play", 20, "low")])
    p = Scheduler().plan_safely(o)
    return p, p.rounds == 0 and p.confidence == 1.0 and len(p.scheduled) == 3, "all 3 tasks scheduled"


def s_tight_budget():
    o = make_owner(45, [Task("Walk", 30, "high"), Task("Feed", 10, "high"), Task("Groom", 40, "low")])
    p = Scheduler().plan_safely(o)
    return p, titles(p) == ["Feed", "Walk"], "high-priority kept, low skipped"


def s_high_too_long():
    o = make_owner(30, [Task("Vet visit", 90, "high"), Task("Feed", 10, "high")])
    p = Scheduler().plan_safely(o)
    ok = any(i.code == "skipped_high" for i in p.issues) and p.confidence < 1.0
    return p, ok, "skipped high-priority task flagged"


def s_flawed_duplicate_budget():
    o = make_owner(40, [Task("Walk", 30, "high"), Task("Play", 20, "low"), Task("Feed", 10, "high")])
    t = o.all_tasks()
    bad = Plan([t[0], t[0], t[1], t[2]], [], [])
    p = Scheduler().check_and_repair(bad, o)
    ok = p.rounds >= 1 and p.total_min <= 40 and not any(i.severity == "error" for i in p.issues)
    return p, ok, "duplicate + over-budget repaired"


def s_flawed_inversion():
    o = make_owner(50, [Task("Vet", 40, "high"), Task("Play", 10, "low"), Task("Brush", 20, "medium")])
    t = o.all_tasks()
    bad = Plan([t[1], t[2]], [t[0]], [])
    p = Scheduler().check_and_repair(bad, o)
    return p, titles(p) == ["Vet"] and p.rounds == 1, "high-priority swapped in"


def s_messy_input():
    o = make_owner(
        60,
        [Task("Walk", 30, "high"), Task("", 10, "low"), Task("Nap", -5, "low"),
         Task("Feed", 10, "URGENT"), Task("walk", 15, "low")],
    )
    p = Scheduler().plan_safely(o)
    return p, len(p.warnings) == 4 and titles(p) == ["Walk", "Feed"], "4 inputs fixed/rejected, plan built"


def s_zero_time():
    p = Scheduler().plan_safely(make_owner(0, [Task("Walk", 30, "high")]))
    return p, bool(p.error) and p.confidence == 0.0 and not p.scheduled, "blocked with error message"


def s_none_input():
    p = Scheduler().plan_safely(None)
    return p, p.error.startswith("Unexpected error") and p.confidence == 0.0, "caught, no crash"


SCENARIOS = [
    ("1 Normal day", s_normal),
    ("2 Tight budget", s_tight_budget),
    ("3 High task too long", s_high_too_long),
    ("4 Flawed: duplicate+budget", s_flawed_duplicate_budget),
    ("5 Flawed: priority inversion", s_flawed_inversion),
    ("6 Messy input", s_messy_input),
    ("7 Zero available time", s_zero_time),
    ("8 None as input", s_none_input),
]


def main() -> int:
    print(f"{'Scenario':<30} {'Result':<6} {'Conf':>5} {'Repairs':>8} {'Input warns':>12}  Note")
    print("-" * 95)
    passed = 0
    confidences = []
    for name, fn in SCENARIOS:
        plan, ok, note = fn()
        passed += ok
        confidences.append(plan.confidence)
        print(
            f"{name:<30} {'PASS' if ok else 'FAIL':<6} {plan.confidence:>5.2f} "
            f"{plan.rounds:>8} {len(plan.warnings):>12}  {note}"
        )
    print("-" * 95)
    print(f"{passed}/{len(SCENARIOS)} passed, average confidence {sum(confidences) / len(confidences):.2f}")
    return 0 if passed == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(main())
