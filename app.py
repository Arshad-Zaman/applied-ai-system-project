"""PawPal+ Streamlit UI: enter pets and tasks, get a verified, explained daily plan."""

import logging

import streamlit as st

from logging_setup import setup_logging
from pawpal_system import Owner, Pet, Scheduler, Task
from verifier import REVIEW_THRESHOLD

setup_logging()
log = logging.getLogger("pawpal")

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption(
    "A pet care planner that builds your day, double-checks its own plan, "
    "and asks you to review it when it isn't confident."
)

# ---------------- State ----------------
if "pets" not in st.session_state:
    st.session_state.pets = []  # [{"name", "species", "tasks": [{"title", "duration", "priority"}]}]
if "plan" not in st.session_state:
    st.session_state.plan = None
if "accepted" not in st.session_state:
    st.session_state.accepted = False


def reset_plan() -> None:
    st.session_state.plan = None
    st.session_state.accepted = False


def load_demo() -> None:
    st.session_state.pets = [
        {
            "name": "Mochi",
            "species": "dog",
            "tasks": [
                {"title": "Morning walk", "duration": 30, "priority": "high"},
                {"title": "Feed breakfast", "duration": 10, "priority": "high"},
                {"title": "Give medication", "duration": 5, "priority": "high"},
                {"title": "Grooming", "duration": 40, "priority": "low"},
                {"title": "Fetch in the yard", "duration": 25, "priority": "medium"},
            ],
        }
    ]
    reset_plan()


# ---------------- Owner ----------------
st.subheader("1. Owner")
c1, c2 = st.columns(2)
owner_name = c1.text_input("Owner name", value="Jordan")
available_min = c2.number_input("Time available today (minutes)", min_value=0, max_value=1440, value=90)

# ---------------- Pets & tasks ----------------
st.subheader("2. Pets and tasks")
st.button("Load demo data", on_click=load_demo)

with st.expander("Add a pet", expanded=not st.session_state.pets):
    p1, p2 = st.columns(2)
    new_pet = p1.text_input("Pet name", value="Mochi", key="new_pet_name")
    new_species = p2.selectbox("Species", ["dog", "cat", "other"], key="new_pet_species")
    if st.button("Add pet"):
        if new_pet.strip():
            st.session_state.pets.append({"name": new_pet.strip(), "species": new_species, "tasks": []})
            reset_plan()
        else:
            st.error("Pet name can't be empty.")

if st.session_state.pets:
    pet_names = [p["name"] for p in st.session_state.pets]
    with st.expander("Add a task", expanded=True):
        target = st.selectbox("For pet", pet_names)
        t1, t2, t3 = st.columns([2, 1, 1])
        title = t1.text_input("Task title", value="Morning walk")
        duration = t2.number_input("Minutes", min_value=0, max_value=600, value=20)
        priority = t3.selectbox("Priority", ["high", "medium", "low"], index=0)
        if st.button("Add task"):
            pet = next(p for p in st.session_state.pets if p["name"] == target)
            pet["tasks"].append({"title": title, "duration": int(duration), "priority": priority})
            reset_plan()

    for pet in st.session_state.pets:
        st.markdown(f"**{pet['name']}** ({pet['species']})")
        if pet["tasks"]:
            st.table(pet["tasks"])
        else:
            st.caption("No tasks yet.")
else:
    st.info("Add a pet, or load the demo data to get started.")

# ---------------- Plan ----------------
st.subheader("3. Build the plan")


def build_owner() -> Owner:
    owner = Owner(owner_name or "Owner", available_min=int(available_min))
    for p in st.session_state.pets:
        pet = Pet(p["name"], p["species"])
        for t in p["tasks"]:
            pet.add_task(Task(t["title"], t["duration"], t["priority"]))
        owner.add_pet(pet)
    return owner


if st.button("Generate plan", type="primary"):
    st.session_state.plan = Scheduler().plan_safely(build_owner())
    st.session_state.accepted = False

plan = st.session_state.plan
if plan is not None:
    if plan.error:
        st.error(f"Couldn't build a plan: {plan.error}")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Time used", f"{plan.total_min} / {int(available_min)} min")
        m2.metric("Confidence", f"{plan.confidence:.2f}")
        m3.metric("Self-check repairs", plan.rounds)

        if plan.needs_review:
            st.warning(
                f"Confidence is below {REVIEW_THRESHOLD}. Please review this plan before relying on it."
            )

        st.markdown("**Scheduled**")
        st.table(
            [
                {"pet": t.pet_name, "task": t.title, "minutes": t.duration_min, "priority": t.priority}
                for t in plan.scheduled
            ]
            or [{"pet": "-", "task": "Nothing scheduled", "minutes": 0, "priority": "-"}]
        )
        if plan.skipped:
            st.markdown("**Skipped**")
            st.table(
                [
                    {"pet": t.pet_name, "task": t.title, "minutes": t.duration_min, "priority": t.priority}
                    for t in plan.skipped
                ]
            )

        with st.expander("Why this plan?", expanded=True):
            for line in plan.explanation:
                st.write("- " + line)
        if plan.issues:
            with st.expander("Verifier findings"):
                for issue in plan.issues:
                    st.write(f"- {issue}")

        # Human in the loop: the owner signs off or goes back to edit.
        if st.session_state.accepted:
            st.success("Plan accepted.")
        else:
            a1, a2 = st.columns(2)
            if a1.button("Accept plan"):
                st.session_state.accepted = True
                log.info(
                    "Owner accepted plan (confidence %.2f, needs_review=%s).",
                    plan.confidence,
                    plan.needs_review,
                )
                st.rerun()
            if a2.button("Edit tasks"):
                log.info("Owner chose to edit tasks after reviewing the plan.")
                reset_plan()
                st.rerun()

    if plan.warnings:
        with st.expander(f"Input guardrail notices ({len(plan.warnings)})", expanded=True):
            for w in plan.warnings:
                st.write("- " + w)
