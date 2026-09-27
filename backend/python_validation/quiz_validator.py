"""
python_validation/quiz_validator.py

SRS Steps 20-22 / xxiv-xxv -- quiz traceability, answer validation and
distractor validation. Deterministic Python only.

For every question:
  * Traceability: has source requirement / document / section, a correct
    answer, an explanation and a difficulty (Step 21).
  * Structure: options exist for choice questions, no duplicate options,
    every correct answer is one of the options, true/false has exactly
    True and False, multiple_response has 2+ correct answers.
  * Answer grounding: the correct answer (with the question) must be
    supported by the approved source text / Requirement Matrix, and any
    value it states (e.g. "45 days") must exist in the sources.
  * Distractor check: a wrong option must not be something the source
    states as true -- e.g. a distractor "Every 45 days" when the policy
    says 45 days would make the question misleading.
"""

from typing import Dict, List

from python_validation.text_utils import fmt_num, numbers_with_units, stem_set, stems

MIN_ANSWER_SUPPORT = 0.5
_BOOLEAN = {"true", "false"}


def _answers(q: dict) -> List[str]:
    a = q.get("correct_answer")
    items = a if isinstance(a, list) else [a]
    out = []
    for x in items:
        if x is None:
            continue
        # stored plans keep multiple answers joined by "; "
        out += [p.strip() for p in str(x).split(";")] if isinstance(a, str) and q.get("question_type") == "multiple_response" else [str(x).strip()]
    return [x for x in out if x]


def validate_quiz(generated_plan: Dict, corpus_text: str) -> Dict:
    questions = generated_plan.get("quiz", []) or []
    corpus_stems = stem_set(corpus_text)
    corpus_values = set(numbers_with_units(corpus_text))

    issues = []
    for i, q in enumerate(questions, 1):
        label = f"Quiz question {i}"
        problems = []
        qtype = q.get("question_type") or ""
        options = [str(o).strip() for o in q.get("options") or []]
        answers = _answers(q)

        # --- traceability (Step 21)
        missing = [f for f, v in (("source requirement", q.get("source_requirement_code")),
                                  ("source document", q.get("source_document_code")),
                                  ("source section", q.get("source_section")),
                                  ("explanation", q.get("explanation")),
                                  ("difficulty", q.get("difficulty"))) if not v]
        if not answers:
            problems.append("No correct answer given.")
        if missing:
            problems.append("Missing traceability fields: " + ", ".join(missing) + ".")

        # --- structure
        if qtype in ("multiple_choice", "multiple_response", "true_false") and not options:
            problems.append("Choice question has no options.")
        if len(set(o.lower() for o in options)) != len(options):
            problems.append("Duplicate answer options.")
        if options and any(a not in options for a in answers):
            problems.append("Correct answer is not one of the options.")
        if qtype == "true_false" and options and {o.lower() for o in options} != _BOOLEAN:
            problems.append("True/false question must have exactly the options True and False.")
        if qtype == "multiple_response" and len(answers) < 2:
            problems.append("Multiple-response question has fewer than two correct answers.")

        # --- correct answer grounded in the source (Step 22 / xxv)
        if answers and corpus_stems:
            basis = " ".join(answers) if not {a.lower() for a in answers} <= _BOOLEAN else ""
            basis = f"{q.get('question_text', '')} {basis}"
            terms = list(dict.fromkeys(stems(basis)))
            if terms:
                support = sum(1 for t in terms if t in corpus_stems) / len(terms)
                if support < MIN_ANSWER_SUPPORT:
                    problems.append(f"Correct answer is weakly supported by the sources ({round(support * 100)}% of key terms found).")
            for v, u in numbers_with_units(" ".join(answers)):
                if (v, u) not in corpus_values:
                    problems.append(f"Correct answer states '{fmt_num(v)} {u}(s)', which is not in any source.")

        # --- distractors must not be true according to the source
        wrong = [o for o in options if o not in answers and o.lower() not in _BOOLEAN]
        for d in wrong:
            d_vals = numbers_with_units(d)
            if d_vals and all(val in corpus_values for val in d_vals):
                ans_vals = set(numbers_with_units(" ".join(answers)))
                shared_units = {u for _, u in d_vals} & {u for _, u in ans_vals}
                if shared_units:
                    problems.append(f"Distractor '{d}' states a value that the source also states; it may be misleading.")

        if problems:
            issues.append({
                "label": label,
                "question": q.get("question_text"),
                "question_type": qtype,
                "correct_answer": answers,
                "problems": problems,
            })

    total = len(questions)
    score = 100.0 if total == 0 else round(((total - len(issues)) / total) * 100, 2)
    types = sorted({q.get("question_type") for q in questions if q.get("question_type")})
    return {
        "score": score,
        "total_items": total,
        "issues": issues,
        "question_types": types,
        "status": "passed" if not issues else ("warning" if score >= 80 else "failed"),
    }
