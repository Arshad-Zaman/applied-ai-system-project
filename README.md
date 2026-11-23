# PawPal+ — A Self-Checking Pet Care Planner

PawPal+ builds a daily care plan for a pet owner from the time they have available and a list of tasks. It then checks its own plan before showing it, fixes mistakes it finds, and gives the plan a confidence score. If the score is low, the owner is asked to review the plan instead of trusting it blindly.

This matters because a planner that only outputs a schedule gives the owner no way to know when it got something wrong. PawPal+ shows its reasoning, flags what it is unsure about, and keeps the owner as the final decision maker.

**AI feature:** a reliability harness made of input guardrails, a verifier with a repair loop, confidence scoring and a human review step. It is rule-based. There is no LLM in this version (see Design Decisions for why).

## Base Project

This is an extension of **PawPal+ (Module 2)**. The original project was a Streamlit app that helps a busy pet owner plan care tasks like walks, feeding, meds and grooming. It was meant to track tasks with a duration and priority, build a daily plan around the owner's constraints, and explain why it picked that plan.

The original version stopped at planning. It had no way to check whether the plan was any good, no handling for bad input, and no tests. This project adds all of those.

## Architecture Overview

The full diagram is in [diagrams/architecture.mmd](diagrams/architecture.mmd) and the class structure is in [diagrams/uml.mmd](diagrams/uml.mmd). Both are Mermaid source files.

Data flows in this order:

1. The owner enters their time, pets and tasks in the Streamlit UI (`app.py`).
2. `Scheduler.plan_safely()` is the single entry point and wraps everything in error handling.
3. **Input guardrails** (`guardrails.py`) clean the input on a copy. Bad tasks are rejected or fixed, and owner-level problems (no time, no pets) block the plan.
4. The **scheduler** sorts tasks by priority, then duration, and fills the available time.
5. The **verifier** (`verifier.py`) audits the plan. If it finds errors, the **repair loop** fixes them and re-verifies, up to 3 rounds.
6. A **confidence score** is calculated. Below 0.7 the UI shows a review banner.
7. The owner **accepts the plan or goes back to edit tasks** (human in the loop).
8. Every stage writes to `pawpal.log`.

| File | What it does |
|------|--------------|
| `app.py` | Streamlit UI |
| `pawpal_system.py` | Task, Pet, Owner, Plan and Scheduler classes, the repair loop and `plan_safely()` |
| `guardrails.py` | Input validation |
| `verifier.py` | Plan checks and confidence score |
| `logging_setup.py` | Logging to `pawpal.log` |
| `eval.py` | Runs 8 scenarios and prints a pass/fail table |
| `tests/test_pawpal.py` | 19 pytest unit tests |

## Setup Instructions

```bash
git clone https://github.com/Arshad-Zaman/applied-ai-system-project.git
cd applied-ai-system-project
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app, the evaluation and the tests:

```bash
streamlit run app.py     # interactive UI
python eval.py           # 8-scenario evaluation table
pytest                   # 19 unit tests
```

No API key is needed. Everything runs locally.

## Sample Interactions

Run this command to reproduce all three examples below:

```bash
python demo.py
```

The output below is copied from that command. The owner is Jordan and the pet is Mochi. Guardrail warnings also go to `pawpal.log`.

### Run 1: Normal day

Input: 90 minutes available, 5 tasks.

```
=== Run 1: normal day ===
Available: 90 min
Tasks:     Morning walk (30m, high), Feed breakfast (10m, high), Give medication (5m, high), Grooming (40m, low), Fetch in the yard (25m, medium)

Time used: 70/90 min | Confidence: 1.00 | Repairs: 0 | Needs review: False
Scheduled: Give medication, Feed breakfast, Morning walk, Fetch in the yard
Skipped:   Grooming (40m, low)
  - Scheduled 'Give medication' (Mochi, high priority, 5 min).
  - Scheduled 'Feed breakfast' (Mochi, high priority, 10 min).
  - Scheduled 'Morning walk' (Mochi, high priority, 30 min).
  - Scheduled 'Fetch in the yard' (Mochi, medium priority, 25 min).
  - Skipped 'Grooming' (Mochi, low priority): needs 40 min but only 20 min left.
```

All the high-priority tasks fit, and the low-priority task was the one skipped, with a reason.

### Run 2: A high-priority task that cannot fit

Input: 30 minutes available, including a 90 minute vet visit.

```
=== Run 2: a high-priority task that cannot fit ===
Available: 30 min
Tasks:     Vet visit (90m, high), Feed breakfast (10m, high), Grooming (15m, low)

Time used: 25/30 min | Confidence: 0.90 | Repairs: 0 | Needs review: False
Scheduled: Feed breakfast, Grooming
Skipped:   Vet visit (90m, high)
  - Scheduled 'Feed breakfast' (Mochi, high priority, 10 min).
  - Skipped 'Vet visit' (Mochi, high priority): needs 90 min but only 20 min left.
  - Scheduled 'Grooming' (Mochi, low priority, 15 min).
  issue: [warning] skipped_high: High-priority 'Vet visit' (Mochi) was skipped for lack of time.
```

The vet visit can't fit even if everything else is removed, so the verifier calls it a warning and not an error. There is nothing to repair, but the confidence drops to 0.90 and the owner can see why.

### Run 3: Messy input

Input: 60 minutes available, with an empty title, a negative duration, an unknown priority, a duplicate and a 600 minute task.

```
=== Run 3: messy input ===
Available: 60 min
Tasks:     Morning walk (30m, high), (no title) (10m, low), Nap (-5m, low), Feed breakfast (10m, urgent), morning walk (15m, low), Hike (600m, low)

Time used: 40/60 min | Confidence: 0.75 | Repairs: 0 | Needs review: False
Scheduled: Morning walk, Feed breakfast
Skipped:   -
  - Scheduled 'Morning walk' (Mochi, high priority, 30 min).
  - Scheduled 'Feed breakfast' (Mochi, medium priority, 10 min).
  guardrail: Rejected a task on Mochi: empty title.
  guardrail: Rejected 'Nap' (Mochi): duration must be a positive whole number (got -5).
  guardrail: Fixed 'Feed breakfast' (Mochi): unknown priority 'urgent', set to 'medium'.
  guardrail: Dropped duplicate 'morning walk' on Mochi.
  guardrail: Rejected 'Hike' (Mochi): 600 min exceeds the 480 min limit.
```

The plan still gets built from the valid tasks, and "urgent" was fixed to medium priority. Each fixed or rejected input costs 0.05 confidence, so 5 of them took the score from 1.00 to 0.75.

### Log excerpt (`pawpal.log`)

```
2026-11-22 09:13:11 INFO    Plan verified: 25 min scheduled, 1 skipped, confidence 0.90, 0 repair round(s), 1 issue(s).
2026-11-22 09:13:11 WARNING Input guardrail: Rejected 'Nap' (Mochi): duration must be a positive whole number (got -5).
2026-11-22 09:13:11 WARNING Input guardrail: Dropped duplicate 'morning walk' on Mochi.
2026-11-22 09:04:00 ERROR   Input guardrail blocked planning: Available time must be a positive number of minutes (got 0).
```

## Reliability and Evaluation

`python eval.py` runs 8 labeled scenarios through the system and prints the result of each one:

```
Scenario                       Result  Conf  Repairs  Input warns  Note
-----------------------------------------------------------------------------------------------
1 Normal day                   PASS    1.00        0            0  all 3 tasks scheduled
2 Tight budget                 PASS    1.00        0            0  high-priority kept, low skipped
3 High task too long           PASS    0.80        0            0  skipped high-priority task flagged
4 Flawed: duplicate+budget     PASS    0.95        1            0  duplicate + over-budget repaired
5 Flawed: priority inversion   PASS    0.95        1            0  high-priority swapped in
6 Messy input                  PASS    0.80        0            4  4 inputs fixed/rejected, plan built
7 Zero available time          PASS    0.00        0            0  blocked with error message
8 None as input                PASS    0.00        0            0  caught, no crash
-----------------------------------------------------------------------------------------------
8/8 passed, average confidence 0.69
```

`pytest` result: `19 passed`.

### How the guardrails and verifier behave

| Input | Behavior | Result |
|-------|----------|--------|
| Plan with a duplicated task and total time over budget (scenario 4) | Verifier finds `duplicate` and `over_budget`. Repair removes the duplicate, then drops the lowest-priority task. | Fixed in 1 round, confidence 0.95 |
| Plan that skipped a high-priority task that could fit (scenario 5) | Verifier finds `priority_inversion`. Repair drops lower-priority tasks and swaps the high-priority task in. | Fixed in 1 round, confidence 0.95 |
| Available time of 0 (scenario 7) | Guardrail blocks planning. | Error message, confidence 0.0, no plan |
| `None` passed as the owner (scenario 8) | `plan_safely()` catches the exception and logs the traceback. | Error plan, app does not crash |

**Scoring:** confidence starts at 1.0 and loses 0.3 per unresolved error, 0.1 per warning, 0.05 per repair round and 0.05 per fixed or rejected input. Below 0.7 the plan is flagged for owner review.

One honest note: scenarios 4 and 5 use plans I built by hand to contain mistakes. The greedy scheduler almost never produces a duplicate or an over-budget plan on its own, so this was the only way to show the repair loop actually working.

## Design Decisions

- **Rule-based checks instead of an LLM.** Rules are reproducible, free, need no API key and can be tested with exact expected results. The trade-off is that the system can only catch the kinds of mistakes I thought to write a rule for.
- **Greedy scheduling.** The scheduler takes tasks in priority order and fits what it can. It is simple and easy to explain to the owner, but it is not guaranteed to find the best combination of tasks.
- **A skipped high-priority task is only an error if swapping it in would fit.** Otherwise it is a warning. Without this, normal plans where a big task just doesn't fit would be marked as broken.
- **Guardrails work on a copy.** The owner's original data is never changed, and rejected tasks don't stop the rest of the plan from being built. Only owner-level problems block the whole plan.
- **Hand-picked confidence weights.** The penalties (0.3, 0.1, 0.05) are my own choices and are not calibrated against real data.
- **Human in the loop.** The system never decides a low-confidence plan is fine on its own. The owner accepts it or edits the tasks.

## Testing Summary

- **What worked:** all 8 evaluation scenarios and all 19 unit tests pass. The repair loop fixed both kinds of broken plans, and the guardrails handled every bad input I tried, including `None`.
- **What didn't:** on real inputs the verifier almost never has anything to fix, because the scheduler is already careful. The repair loop is only exercised by hand-built bad plans. I would need a less careful planner, such as an LLM, before the loop earns its place in normal use.
- **What I learned:** a check is only trustworthy if I know when it fires. Writing the "can it fit?" condition for priority inversions taught me that a verifier needs to separate real errors from things that just can't be done.

## Reflection

This project taught me that making an AI system trustworthy is mostly about what happens around the part that makes the decision. The planner itself is simple, but the guardrails, the self-check and the confidence score are what let someone else decide how much to rely on it. The responsible-AI reflection (limitations, misuse, and how I worked with AI) is in [model_card.md](model_card.md).
