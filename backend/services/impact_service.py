"""
services/impact_service.py

SRS Steps 57-58 / lvii-lviii, Challenge 4 -- Policy Update Detection and
Impact Analysis. Deterministic Python only.

Given a new (or obsolete) document version it answers:
  * What changed?            sentence-level diff between versions, with
                             value changes ("90 days" -> "45 days") and rule
                             changes ("optional" -> "must")
  * Which matrix rows still point at the old version?
  * Which plans / modules / checklist items / tasks / quiz questions are
    affected, and which quiz questions are now outdated?
  * Which employees are affected, and which plans need regeneration?
"""

from sqlalchemy.orm import Session

from database.models import Document, DocumentChunk, Employee, OnboardingPlan, RequirementMatrix
from python_validation.text_utils import (
    fmt_num, normalize, numbers_with_units, plan_items, split_sentences, stem_set,
)
from python_validation.contradiction_detector import _polarity

TOPIC_MATCH = 0.5      # stem overlap for "the same sentence, edited"
ITEM_MATCH = 0.4       # share of a changed sentence's key terms found in an item


class ImpactError(Exception):
    pass


def _sentences(doc: Document, db: Session) -> list[dict]:
    out = []
    for c in db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.id).all():
        for s in split_sentences(c.content or ""):
            out.append({"text": s, "section": c.section, "stems": stem_set(s, drop_polarity=True),
                        "values": numbers_with_units(s), "polarity": _polarity(s)})
    return out


def _similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def diff_versions(old: Document, new: Document, db: Session) -> dict:
    old_s, new_s = _sentences(old, db), _sentences(new, db)
    new_texts = {normalize(s["text"]) for s in new_s}
    old_texts = {normalize(s["text"]) for s in old_s}
    used_new = set()
    changed, removed = [], []

    for o in old_s:
        if normalize(o["text"]) in new_texts:
            continue
        best, best_i = 0.0, None
        for i, n in enumerate(new_s):
            if i in used_new or normalize(n["text"]) in old_texts:
                continue
            sim = _similarity(o["stems"], n["stems"])
            if sim > best:
                best, best_i = sim, i
        if best_i is not None and best >= TOPIC_MATCH:
            n = new_s[best_i]
            used_new.add(best_i)
            value_changes = []
            new_by_unit = {}
            for v, u in n["values"]:
                new_by_unit.setdefault(u, []).append(v)
            for v, u in o["values"]:
                if u in new_by_unit and v not in new_by_unit[u]:
                    value_changes.append(f"{fmt_num(v)} {u}(s) -> {', '.join(fmt_num(x) for x in new_by_unit[u])} {u}(s)")
            rule_change = None
            if o["polarity"] != n["polarity"] and (o["polarity"] or n["polarity"]):
                rule_change = f"{o['polarity'] or 'unspecified'} -> {n['polarity'] or 'unspecified'}"
            changed.append({"section": n["section"] or o["section"], "old": o["text"], "new": n["text"],
                            "value_changes": value_changes, "rule_change": rule_change,
                            "old_values": [f"{fmt_num(v)} {u}" for v, u in o["values"]]})
        else:
            removed.append({"section": o["section"], "text": o["text"]})

    added = [{"section": n["section"], "text": n["text"]}
             for i, n in enumerate(new_s) if i not in used_new and normalize(n["text"]) not in old_texts]
    return {"changed": changed, "added": added, "removed": removed,
            "unchanged": sum(1 for o in old_s if normalize(o["text"]) in new_texts)}


def resolve_versions(document_id: int, db: Session) -> tuple[Document | None, Document]:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ImpactError(f"No document found with id={document_id}")
    if doc.supersedes_document_id:
        old = db.query(Document).filter(Document.id == doc.supersedes_document_id).first()
        return old, doc
    if not doc.is_active_version and doc.family_code:
        active = db.query(Document).filter(Document.family_code == doc.family_code,
                                           Document.is_active_version == True).first()  # noqa: E712
        return doc, (active or doc)
    return None, doc


def _affected_items(plan: OnboardingPlan, old_codes: set, old_ids: set, family_req_codes: set, change_list: list) -> list:
    raw = plan.raw_genai_json if isinstance(plan.raw_genai_json, dict) else {}
    out = []
    change_terms = [(stem_set(c["old"], drop_polarity=True), c) for c in change_list]
    old_values = {(v, u) for c in change_list for v, u in numbers_with_units(c["old"])}
    for it in plan_items(raw):
        rawi = it["raw"]
        reasons = []
        dc = normalize(rawi.get("source_document_code"))
        rc = normalize(rawi.get("source_requirement_code"))
        if dc and dc in old_codes:
            reasons.append(f"cites obsolete version {rawi.get('source_document_code')}")
        item_values = set(numbers_with_units(it["text"]))
        stale_values = item_values & old_values
        if stale_values:
            reasons.append("states old value(s): " + ", ".join(f"{fmt_num(v)} {u}" for v, u in stale_values))
        item_stems = stem_set(it["text"], drop_polarity=True)
        if rc in family_req_codes or dc in old_codes:
            for terms, c in change_terms:
                if terms and len(terms & item_stems) / len(terms) >= ITEM_MATCH:
                    reasons.append(f"covers changed text in section {c.get('section') or '-'}")
                    break
        if reasons:
            out.append({"section": it["section"], "index": it["index"], "label": it["label"],
                        "text": it["text"], "requirement_code": rawi.get("source_requirement_code"),
                        "module_code": rawi.get("module_code"), "reasons": reasons})
    return out


def analyze_impact(document_id: int, db: Session) -> dict:
    old, new = resolve_versions(document_id, db)
    if old is None:
        return {"document": _doc_info(new), "previous_version": None,
                "message": "This document has no previous version, so nothing is affected.",
                "changes": {"changed": [], "added": [], "removed": [], "unchanged": 0},
                "stale_requirements": [], "affected_plans": [], "affected_employees": [],
                "summary": {"plans_requiring_regeneration": 0}}

    family = new.family_code or old.family_code
    old_versions = (db.query(Document).filter(Document.family_code == family, Document.id != new.id).all()
                    if family else [old])
    old_ids = {d.id for d in old_versions}
    old_codes = {normalize(d.document_code) for d in old_versions}

    changes = diff_versions(old, new, db)
    change_list = changes["changed"] + [{"old": r["text"], "section": r["section"]} for r in changes["removed"]]

    family_reqs = db.query(RequirementMatrix).filter(RequirementMatrix.source_document_id.in_(old_ids | {new.id})).all()
    family_req_codes = {normalize(r.requirement_code) for r in family_reqs}
    stale = [{"id": r.id, "requirement_code": r.requirement_code, "role_id": r.role_id,
              "role_name": r.role.role_name if r.role else None, "linked_document_id": r.source_document_id}
             for r in family_reqs if r.source_document_id in old_ids]

    employees = {e.id: e for e in db.query(Employee).all()}
    affected_plans = []
    for plan in db.query(OnboardingPlan).order_by(OnboardingPlan.id.desc()).all():
        used = {normalize(s.get("document_code")) for s in (plan.source_document_versions or []) if isinstance(s, dict)}
        cites_family = bool(used & old_codes)
        items = _affected_items(plan, old_codes, old_ids, family_req_codes, change_list)
        if not items and not cites_family:
            continue
        emp = employees.get(plan.employee_id)
        by_section = {}
        for it in items:
            by_section[it["section"]] = by_section.get(it["section"], 0) + 1
        affected_plans.append({
            "plan_id": plan.id,
            "employee_id": plan.employee_id,
            "employee_name": emp.full_name if emp else None,
            "role_name": emp.role.role_name if emp and emp.role else None,
            "generated_at": plan.generated_at,
            "verification_status": plan.verification_status,
            "used_old_version": cites_family,
            "affected_items": items,
            "affected_counts": by_section,
            "outdated_quiz_questions": [it for it in items if it["section"] == "quiz"],
            "requires_regeneration": bool(items),
        })

    affected_employee_ids = sorted({p["employee_id"] for p in affected_plans})
    return {
        "document": _doc_info(new),
        "previous_version": _doc_info(old),
        "changes": changes,
        "stale_requirements": stale,
        "affected_plans": affected_plans,
        "affected_employees": [
            {"id": i, "name": employees[i].full_name if i in employees else None} for i in affected_employee_ids
        ],
        "summary": {
            "changed_sentences": len(changes["changed"]),
            "added_sentences": len(changes["added"]),
            "removed_sentences": len(changes["removed"]),
            "stale_requirement_links": len(stale),
            "plans_affected": len(affected_plans),
            "plans_requiring_regeneration": sum(1 for p in affected_plans if p["requires_regeneration"]),
            "affected_modules": sum(p["affected_counts"].get("modules", 0) for p in affected_plans),
            "affected_checklist_items": sum(p["affected_counts"].get("checklist", 0) for p in affected_plans),
            "affected_tasks": sum(p["affected_counts"].get("tasks", 0) for p in affected_plans),
            "outdated_quiz_questions": sum(p["affected_counts"].get("quiz", 0) for p in affected_plans),
            "employees_affected": len(affected_employee_ids),
        },
    }


def relink_requirements(document_id: int, db: Session) -> dict:
    """Moves Requirement Matrix links from obsolete versions to the active one."""
    old, new = resolve_versions(document_id, db)
    if old is None or not new.is_active_version:
        raise ImpactError("No newer active version to relink to.")
    family = new.family_code
    old_ids = {d.id for d in db.query(Document).filter(Document.family_code == family, Document.id != new.id).all()}
    rows = db.query(RequirementMatrix).filter(RequirementMatrix.source_document_id.in_(old_ids)).all()
    for r in rows:
        r.source_document_id = new.id
    db.commit()
    return {"relinked": [r.requirement_code for r in rows], "to_document_code": new.document_code}


def _doc_info(d: Document | None):
    if d is None:
        return None
    return {"id": d.id, "document_code": d.document_code, "title": d.title, "version": d.version,
            "is_active_version": d.is_active_version, "family_code": d.family_code,
            "effective_date": d.effective_date, "uploaded_at": d.uploaded_at}
