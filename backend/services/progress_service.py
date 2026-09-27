"""
services/progress_service.py

SRS Steps 50, 53-56 / liii-lvi -- quiz scores, assessment scores, progress
assessment, weak-area identification and adaptive recommendations.
All rule-based and deterministic.

Progress assessment outcomes (Step 54):
  Completed           every item done, quiz passed, no failed assessment
  Behind Schedule     several items are past their due date
  Assessment Required an assessment is due / the quiz is not taken yet
  Requires Attention  low quiz score, failed assessment, or an overdue item
  On Track            everything else

Due dates come from the employee's joining date + the item's stage
(Day 1 = +1 day, Week 1 = +7, Week 2 = +14, First 30/60/90 Days = +30/60/90).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import Assessment, Employee, OnboardingPlan, QuizAttempt, QuizQuestion, RequirementMatrix
from python_validation.sequence_validator import _stage_rank

PASS_MARK = 70.0  # quiz / assessment pass percentage


class ProgressError(Exception):
    pass


# ------------------------------------------------------------------- quiz
def correct_set(q: QuizQuestion) -> set:
    if q.correct_answers:
        return {str(a).strip().lower() for a in q.correct_answers}
    if q.correct_answer is None:
        return set()
    parts = str(q.correct_answer).split(";") if q.question_type == "multiple_response" else [q.correct_answer]
    return {p.strip().lower() for p in parts if p.strip()}


def submit_quiz(plan: OnboardingPlan, employee_id: int, answers: list[dict], db: Session) -> dict:
    questions = {q.id: q for q in plan.quizzes}
    results = []
    for a in answers:
        q = questions.get(a.get("question_id"))
        if not q:
            raise ProgressError(f"Question {a.get('question_id')} is not part of plan {plan.id}.")
        selected = a.get("selected")
        selected = selected if isinstance(selected, list) else [selected]
        selected = [str(s).strip() for s in selected if s is not None and str(s).strip()]
        is_correct = {s.lower() for s in selected} == correct_set(q) and bool(selected)
        db.add(QuizAttempt(plan_id=plan.id, question_id=q.id, employee_id=employee_id,
                           selected=selected, is_correct=is_correct))
        results.append({"question_id": q.id, "selected": selected, "is_correct": is_correct,
                        "correct_answer": q.correct_answers or q.correct_answer, "explanation": q.explanation})
    db.commit()
    summary = quiz_summary(plan, db)
    return {"results": results, **summary}


def quiz_summary(plan: OnboardingPlan, db: Session) -> dict:
    attempts = (db.query(QuizAttempt).filter(QuizAttempt.plan_id == plan.id)
                .order_by(QuizAttempt.attempted_at.asc(), QuizAttempt.id.asc()).all())
    latest, wrong_counts = {}, {}
    for att in attempts:
        latest[att.question_id] = att
        if not att.is_correct:
            wrong_counts[att.question_id] = wrong_counts.get(att.question_id, 0) + 1
    answered = len(latest)
    correct = sum(1 for a in latest.values() if a.is_correct)
    total = len(plan.quizzes)
    return {
        "total_questions": total,
        "answered": answered,
        "correct": correct,
        "score": round(correct / answered * 100, 1) if answered else None,
        "passed": (answered == total and total > 0 and correct / total * 100 >= PASS_MARK),
        "latest": {qid: {"selected": a.selected, "is_correct": a.is_correct} for qid, a in latest.items()},
        "repeated_errors": [qid for qid, n in wrong_counts.items() if n > 1],
        "attempt_count": len(attempts),
    }


# ------------------------------------------------------------- assessment
def score_assessment(assessment: Assessment, score: float, evaluator: str, db: Session) -> Assessment:
    if score is None or not 0 <= float(score) <= 100:
        raise ProgressError("score must be between 0 and 100")
    assessment.score = float(score)
    assessment.status = "Passed" if float(score) >= PASS_MARK else "Failed"
    assessment.evaluated_by = evaluator
    assessment.evaluated_at = datetime.now(timezone.utc)
    db.commit()
    return assessment


# ---------------------------------------------------------------- progress
def _due_date(joining: datetime | None, stage: str | None):
    if joining is None or not stage:
        return None
    days = _stage_rank(stage)
    if days is None:
        return None
    base = joining if joining.tzinfo else joining.replace(tzinfo=timezone.utc)
    return base + timedelta(days=max(int(days), 1))


def assess_progress(plan: OnboardingPlan, db: Session, today: datetime | None = None) -> dict:
    today = today or datetime.now(timezone.utc)
    employee = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    joining = employee.joining_date if employee else None
    requirements = {r.requirement_code: r for r in db.query(RequirementMatrix).filter(
        RequirementMatrix.role_id == (employee.role_id if employee else None)).all()}

    tracked = ([("module", m, m.title) for m in plan.modules] +
               [("checklist", c, c.activity) for c in plan.checklist_items] +
               [("task", t, t.task_description) for t in plan.tasks])
    items = []
    for kind, obj, name in tracked:
        due = _due_date(joining, obj.due_stage)
        done = obj.completion_status == "Completed"
        items.append({"type": kind, "id": obj.id, "name": name, "due_stage": obj.due_stage,
                      "due_date": due.date().isoformat() if due else None,
                      "completed": done, "overdue": bool(due and not done and due < today),
                      "requirement_code": getattr(obj, "source_requirement_code", None)})

    total = len(items)
    completed = sum(1 for i in items if i["completed"])
    overdue = [i for i in items if i["overdue"]]
    due_so_far = [i for i in items if i["due_date"] and datetime.fromisoformat(i["due_date"]).replace(tzinfo=timezone.utc) < today]

    quiz = quiz_summary(plan, db)
    assessments = [{"id": a.id, "title": a.title, "type": a.assessment_type, "status": a.status, "score": a.score,
                    "due_stage": a.due_stage, "requirement_code": a.source_requirement_code,
                    "due_date": (_due_date(joining, a.due_stage).date().isoformat() if _due_date(joining, a.due_stage) else None)}
                   for a in plan.assessments]
    failed_assessments = [a for a in assessments if a["status"] == "Failed"]
    pending_due_assessments = [a for a in assessments if a["status"] == "Pending" and a["due_date"]
                               and datetime.fromisoformat(a["due_date"]).replace(tzinfo=timezone.utc) < today]
    scored = [a["score"] for a in assessments if a["score"] is not None]

    # --- weak areas (Step 56)
    q_by_id = {q.id: q for q in plan.quizzes}
    topic_stats = {}
    for qid, res in quiz["latest"].items():
        q = q_by_id.get(qid)
        code = (q.source_requirement_code if q else None) or "General"
        st = topic_stats.setdefault(code, {"answered": 0, "correct": 0})
        st["answered"] += 1
        st["correct"] += int(res["is_correct"])

    def topic_label(code):
        r = requirements.get(code)
        return (r.competency or r.policy_requirement) if r else code

    weak = []
    for code, st in topic_stats.items():
        acc = st["correct"] / st["answered"] * 100
        if acc < PASS_MARK:
            weak.append({"requirement_code": code, "topic": topic_label(code), "reason": "quiz performance",
                         "detail": f"{st['correct']}/{st['answered']} correct"})
    for a in failed_assessments:
        weak.append({"requirement_code": a["requirement_code"], "topic": topic_label(a["requirement_code"]) if a["requirement_code"] else a["title"],
                     "reason": "assessment result", "detail": f"{a['title']}: {a['score']}%"})
    for i in overdue:
        if i["type"] == "task":
            weak.append({"requirement_code": i["requirement_code"], "topic": i["name"], "reason": "incomplete task",
                         "detail": f"due {i['due_date']}"})
    for qid in quiz["repeated_errors"]:
        q = q_by_id.get(qid)
        if q:
            weak.append({"requirement_code": q.source_requirement_code, "topic": q.question_text,
                         "reason": "repeated errors", "detail": "answered wrong more than once"})

    # --- outcome (Step 54)
    all_done = total > 0 and completed == total
    quiz_ok = quiz["total_questions"] == 0 or quiz["passed"]
    if all_done and quiz_ok and not failed_assessments and not any(a["status"] == "Pending" for a in assessments):
        outcome = "Completed"
    elif len(overdue) >= 3 or (due_so_far and len(overdue) / len(due_so_far) >= 0.3):
        outcome = "Behind Schedule"
    elif pending_due_assessments or (all_done and quiz["answered"] == 0 and quiz["total_questions"] > 0):
        outcome = "Assessment Required"
    elif overdue or failed_assessments or (quiz["score"] is not None and quiz["score"] < PASS_MARK):
        outcome = "Requires Attention"
    else:
        outcome = "On Track"

    # --- adaptive recommendations (Step 55)
    recs = []
    modules_by_req = {}
    for m in plan.modules:
        if m.source_requirement_code:
            modules_by_req.setdefault(m.source_requirement_code, []).append(m)
    for w in weak:
        code = w.get("requirement_code")
        if w["reason"] in ("quiz performance", "repeated errors"):
            for m in modules_by_req.get(code, [])[:1]:
                recs.append({"type": "Revision module", "target": m.title, "reason": f"Weak on {w['topic']} ({w['detail']})"})
            recs.append({"type": "Additional quiz", "target": w["topic"], "reason": "Practice questions on a weak topic"})
        elif w["reason"] == "incomplete task":
            recs.append({"type": "Additional task", "target": w["topic"], "reason": f"Overdue task ({w['detail']})"})
        elif w["reason"] == "assessment result":
            recs.append({"type": "Manager review", "target": w["topic"], "reason": f"Failed assessment ({w['detail']})"})
    if outcome == "Behind Schedule":
        recs.append({"type": "Manager review", "target": employee.full_name if employee else "employee",
                     "reason": f"{len(overdue)} overdue item(s)"})
    if outcome in ("Completed", "On Track") and quiz["score"] is not None and quiz["score"] >= 90 and \
            (not scored or min(scored) >= 90):
        recs.append({"type": "Advanced module", "target": "Next-level role training", "reason": "Consistently high scores"})
    seen, unique_recs = set(), []
    for r in recs:
        key = (r["type"], r["target"])
        if key not in seen:
            seen.add(key)
            unique_recs.append(r)

    upcoming = sorted([i for i in items if not i["completed"] and not i["overdue"] and i["due_date"]],
                      key=lambda i: i["due_date"])[:5]
    stage_names = []
    for i in items:
        if i["due_stage"] and i["due_stage"] not in stage_names:
            stage_names.append(i["due_stage"])
    milestones = []
    for stage in sorted(stage_names, key=lambda s: (_stage_rank(s) is None, _stage_rank(s) or 0)):
        in_stage = [i for i in items if i["due_stage"] == stage]
        milestones.append({"stage": stage, "total": len(in_stage),
                           "completed": sum(1 for i in in_stage if i["completed"]),
                           "due_date": next((i["due_date"] for i in in_stage if i["due_date"]), None)})

    if employee is not None:
        employee.training_status = "Completed" if outcome == "Completed" else ("In Progress" if completed or quiz["answered"] else "Not Started")
        db.commit()

    return {
        "plan_id": plan.id,
        "employee_id": plan.employee_id,
        "outcome": outcome,
        "progress_percent": round(completed / total * 100, 1) if total else 0.0,
        "completed_items": completed,
        "total_items": total,
        "module_completion": _ratio(items, "module"),
        "checklist_completion": _ratio(items, "checklist"),
        "task_completion": _ratio(items, "task"),
        "overdue_items": overdue,
        "upcoming_activities": upcoming,
        "milestones": milestones,
        "quiz": {k: v for k, v in quiz.items() if k != "latest"},
        "assessments": assessments,
        "assessment_average": round(sum(scored) / len(scored), 1) if scored else None,
        "weak_areas": weak,
        "recommendations": unique_recs,
    }


def _ratio(items, kind):
    sub = [i for i in items if i["type"] == kind]
    return {"completed": sum(1 for i in sub if i["completed"]), "total": len(sub)}
