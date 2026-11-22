import pytest

from guardrails import validate_owner
from pawpal_system import Owner, Pet, Plan, Scheduler, Task
from verifier import confidence_score, verify


def make_owner(avail, tasks):
    owner = Owner("Sam", available_min=avail)
    pet = Pet("Rex")
    for t in tasks:
        pet.add_task(t)
    owner.add_pet(pet)
    return owner


# ---------------- Scheduler ----------------
def test_high_priority_scheduled_first():
    o = make_owner(40, [Task("Groom", 30, "low"), Task("Walk", 30, "high")])
    plan = Scheduler().build_plan(o)
    assert [t.title for t in plan.scheduled] == ["Walk"]


def test_budget_respected():
    o = make_owner(50, [Task("A", 30, "high"), Task("B", 30, "medium"), Task("C", 15, "low")])
    plan = Scheduler().build_plan(o)
    assert plan.total_min <= 50


def test_skipped_tasks_are_explained():
    o = make_owner(10, [Task("Walk", 30, "high")])
    plan = Scheduler().build_plan(o)
    assert plan.skipped and any("Skipped 'Walk'" in line for line in plan.explanation)


# ---------------- Verifier ----------------
def test_clean_plan_has_no_issues():
    o = make_owner(60, [Task("Walk", 30, "high")])
    assert verify(Scheduler().build_plan(o), o) == []


def test_verifier_flags_over_budget():
    o = make_owner(20, [Task("Walk", 30, "high")])
    plan = Plan(o.all_tasks(), [], [])
    assert "over_budget" in {i.code for i in verify(plan, o)}


def test_verifier_flags_duplicate():
    o = make_owner(100, [Task("Walk", 30, "high")])
    t = o.all_tasks()[0]
    assert "duplicate" in {i.code for i in verify(Plan([t, t], [], []), o)}


def test_verifier_flags_priority_inversion():
    o = make_owner(50, [Task("Vet", 40, "high"), Task("Play", 10, "low")])
    vet, play = o.all_tasks()
    codes = {i.code for i in verify(Plan([play], [vet], []), o)}
    assert "priority_inversion" in codes


def test_unfittable_high_task_is_warning_not_error():
    o = make_owner(30, [Task("Vet", 90, "high"), Task("Feed", 10, "low")])
    vet, feed = o.all_tasks()
    issues = verify(Plan([feed], [vet], []), o)
    assert [i.severity for i in issues if i.code == "skipped_high"] == ["warning"]


# ---------------- Confidence ----------------
def test_confidence_penalties():
    o = make_owner(100, [Task("Walk", 30, "high")])
    t = o.all_tasks()[0]
    issues = verify(Plan([t, t], [], []), o)  # one duplicate error
    assert confidence_score(issues, rounds=1) == pytest.approx(0.65)


def test_confidence_floors_at_zero():
    o = make_owner(1, [Task("A", 30, "high")])
    t = o.all_tasks()[0]
    issues = verify(Plan([t, t, t], [], []), o)
    assert confidence_score(issues * 5, rounds=3) == 0.0


# ---------------- Repair loop ----------------
def test_repair_loop_fixes_errors():
    o = make_owner(40, [Task("Walk", 30, "high"), Task("Play", 20, "low")])
    t = o.all_tasks()
    plan = Scheduler().check_and_repair(Plan([t[0], t[0], t[1]], [], []), o)
    assert plan.rounds >= 1
    assert not any(i.severity == "error" for i in plan.issues)


def test_repair_loop_respects_max_rounds():
    o = make_owner(40, [Task("Walk", 30, "high"), Task("Play", 20, "low")])
    t = o.all_tasks()
    plan = Scheduler().check_and_repair(Plan([t[0], t[0], t[1]], [], []), o, max_rounds=0)
    assert plan.rounds == 0 and any(i.severity == "error" for i in plan.issues)


# ---------------- Guardrails ----------------
def test_guardrails_reject_bad_duration_and_title():
    o = make_owner(60, [Task("Walk", 30, "high"), Task("Nap", -5), Task("", 10), Task("Hike", 600)])
    r = validate_owner(o)
    assert [t.title for t in r.owner.all_tasks()] == ["Walk"]
    assert len(r.warnings) == 3


def test_guardrails_fix_priority_and_drop_duplicate():
    o = make_owner(60, [Task("Feed", 10, "urgent"), Task("feed", 5, "low")])
    r = validate_owner(o)
    tasks = r.owner.all_tasks()
    assert len(tasks) == 1 and tasks[0].priority == "medium"


def test_guardrails_do_not_modify_original():
    o = make_owner(60, [Task("Nap", -5), Task("Walk", 30, "high")])
    validate_owner(o)
    assert len(o.all_tasks()) == 2


def test_guardrails_block_owner_level_problems():
    assert not validate_owner(make_owner(0, [Task("Walk", 30, "high")])).ok
    assert not validate_owner(Owner("Sam")).ok
    assert not validate_owner(make_owner(60, [Task("Nap", -5)])).ok


# ---------------- plan_safely ----------------
def test_plan_safely_blocked_returns_error_plan():
    plan = Scheduler().plan_safely(make_owner(0, [Task("Walk", 30, "high")]))
    assert plan.error and plan.confidence == 0.0 and not plan.scheduled


def test_plan_safely_never_raises():
    plan = Scheduler().plan_safely(None)
    assert plan.error.startswith("Unexpected error")


def test_plan_safely_input_fixes_lower_confidence():
    o = make_owner(60, [Task("Walk", 30, "high"), Task("Nap", -5)])
    plan = Scheduler().plan_safely(o)
    assert plan.confidence == pytest.approx(0.95)
