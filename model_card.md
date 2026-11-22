# Model Card — PawPal+

## 1. Model Overview

PawPal+ is a pet care planner that builds a daily plan from the owner's available time and a list of tasks. It sorts tasks by priority, fits them into the time budget, checks its own plan, repairs any mistakes it finds and gives the plan a confidence score between 0 and 1. If the score is below 0.7, the owner is asked to review the plan before accepting it.

There is no trained model or LLM in this system. The "AI" is a rule-based reliability harness: input guardrails, a verifier, a repair loop and confidence scoring. It is meant for one owner planning one day of pet care. It is not meant for veterinary or medical decisions.

## 2. Limitations and Biases

- **Greedy scheduling.** The scheduler takes tasks in priority order and fits what it can. It is not guaranteed to find the best combination of tasks, so a better plan can exist that it never considers.
- **Priority labels decide everything.** The owner picks high, medium or low, and the system has no way of knowing if that label is right. A medication marked "low" would be the first thing skipped. The system is only as good as the labels it is given.
- **No time of day.** It fits minutes into a budget, but it does not know that a medication is due at 8am or that two tasks can't happen at once.
- **Same rules for every pet.** A dog, a cat and "other" are treated the same. There are no species-specific care rules.
- **Hand-picked numbers.** The confidence penalties (0.3 per error, 0.1 per warning, 0.05 per repair round and per fixed input), the 0.7 review cutoff and the 480 minute task limit are my own choices. I did not calibrate them against real data.
- **The verifier only catches what I wrote rules for.** A plan can pass every check and still be a bad plan for the owner's day.
- **Confidence is not accuracy.** A score of 1.00 means the plan passed my checks. It does not mean the plan is right.

## 3. Potential Misuse and Prevention

- **Over-trusting the plan.** An owner could rely on it for a pet's medical care, such as medication or vet visits. To reduce this, any skipped high-priority task is always shown with a warning, low-confidence plans get a review banner, and the owner has to accept the plan before it counts as final.
- **Hiding a skipped task.** Someone could mark everything "low" so nothing shows as a warning. The explanation still lists every skipped task and why, so it is visible.
- **Bad or hostile input.** The guardrails reject empty titles, impossible durations (zero, negative or over 480 minutes), unknown priorities and duplicates. A last-resort catch in `plan_safely()` means unexpected input produces an error message and not a crash.
- **What I would add next.** A medical disclaimer in the UI, and a rule that medication tasks can never be skipped without a loud warning.

## 4. Testing Results and Surprises

| Check | Result |
|-------|--------|
| `python eval.py` (8 scenarios) | 8/8 passed, average confidence 0.69 |
| `pytest` (19 unit tests) | 19 passed |
| Guardrails on bad input (empty title, negative duration, 600 min task, unknown priority, duplicate, zero time, `None`) | All handled without crashing |
| Repair loop on hand-built bad plans (duplicate + over budget, priority inversion) | Both fixed in 1 round |

**What surprised me:**

- **The verifier almost never fires on normal input.** The scheduler already respects the budget and the priorities, so there is rarely anything to fix. The only way to show the repair loop working was to build bad plans by hand. This means the loop is more of a safety net than something that changes everyday results.
- **A skipped high-priority task is not always an error.** As first proposed, the rule flagged a skipped high-priority task as an error. That would have marked normal plans as broken whenever a long task simply didn't fit. The rule was refined while building it, so it is only an error if swapping the task in would actually fit, and otherwise it is a warning.
- **Scores add up faster than I expected.** In the "high task too long" scenario the confidence was 0.80, not 0.90. The skipped high-priority task and a low-utilization warning both fired, and each costs 0.1.

## 5. AI Collaboration

**How I used AI.** I used Claude Code for most of this project. Before each build step I asked it for a proposal, reviewed it and then approved or changed it. After that it wrote the code, ran the tests and drafted the docs. I worked one step at a time: scheduler, verifier, guardrails, evaluation, UI, diagrams, README and model card.

**Suggestions I accepted.** I accepted two main things.

- *The weight thresholds.* The verifier proposal gave specific numbers: a 0.3 penalty per error, 0.1 per warning, 0.05 per repair round, and a 0.7 cutoff for asking the owner to review. I approved them as written. They are hand-picked and not calibrated, but they were easy to read and explain, and I could see exactly how a score would change before anything was built.
- *The guardrail suggestions.* I approved the guardrail rules with no changes: reject empty titles and impossible durations, cap a task at 480 minutes, fix unknown priorities to medium, drop duplicates, and return an empty error plan instead of raising an exception when the whole input is unusable. I liked that bad tasks get removed while the rest of the plan still builds, and that the owner's original data is never touched.

**What I did not accept.** Not much was denied outright. What worked for me was breaking the project into small steps. For each step I asked for a proposal first, read it and then approved or changed it before any code was written. That made it easy to catch anything iffy while it was still just a plan. Because each step was small, most revisions were quick changes to a proposal, and not rewrites of finished code.

**Where the AI made mistakes.** These are small, but they are real:

- It appended `pawpal.log` to `.gitignore` without a newline, which glued it onto the `.DS_Store` line. It only caught this by checking the file afterward.
- One long shell command failed to run because of how it was quoted, so the files had to be written another way.
- It left the diagrams unvalidated because the check needed a package download that was denied, so I still have to confirm they render.

## 6. Future Improvements

- Add an LLM-written plan summary, with the verifier checking that it only mentions tasks that are actually in the plan.
- Add time-of-day scheduling and conflict detection.
- Add species-specific care rules and a "never skip medication" guardrail.
- Calibrate the confidence weights against real owner feedback instead of hand-picked numbers.
