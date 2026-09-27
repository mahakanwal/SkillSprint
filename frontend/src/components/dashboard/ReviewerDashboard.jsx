import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ClipboardList, ShieldCheck, CheckCircle2, XCircle, RotateCcw, History, Edit3, RefreshCw, MessageSquare,
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import apiClient from '../../api/apiClient';
import { useAuth } from '../../context/AuthContext';
import { AppShell } from '../ui/AppShell';
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, LoadingState, PageHeader, ScoreMeter,
  SkeletonRows, StatusBadge, ease,
} from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';

/* ==========================================================================
   ReviewerDashboard — the Manual Review Queue + Reviewer Decision workflow
   (SRS xliv-xlvii). A reviewer can:
     - Approve / Reject / mark "Needs Regeneration" on a whole plan
     - Override a single requirement's validation_status (with a reason) —
       the ORIGINAL result is never overwritten, only layered over
     - See the full audit trail of every decision + override on a plan
   ========================================================================== */
export const ReviewerDashboard = ({ onLogout }) => {
  const { user } = useAuth();

  const [queue, setQueue] = useState([]);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [expandedId, setExpandedId] = useState(null);
  const [planDetail, setPlanDetail] = useState(null); // full detail for the expanded plan
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const [notes, setNotes] = useState('');
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [actionError, setActionError] = useState(null);

  const [overridingId, setOverridingId] = useState(null); // validation_result id being overridden
  const [overrideStatus, setOverrideStatus] = useState('Verified');
  const [overrideReason, setOverrideReason] = useState('');
  const [isOverriding, setIsOverriding] = useState(false);

  const [auditTrail, setAuditTrail] = useState(null);
  const [planContent, setPlanContent] = useState(null); // modules / checklist / tasks / quiz of the plan
  const [editing, setEditing] = useState(null); // { type, item, fields, reason }
  const [comment, setComment] = useState('');
  const [actionNotice, setActionNotice] = useState(null);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const EDITABLE = {
    module: ['title', 'purpose', 'due_stage', 'completion_criteria'],
    checklist: ['activity', 'due_stage', 'responsible_person'],
    task: ['task_description', 'expected_outcome', 'due_stage', 'completion_criteria'],
    quiz: ['question_text', 'correct_answer', 'explanation'],
  };

  const startEdit = (type, item) => {
    const fields = Object.fromEntries(EDITABLE[type].map((f) => [f, item[f] ?? '']));
    setEditing({ type, item, fields, reason: '' });
  };

  const saveEdit = async () => {
    if (!editing?.reason.trim()) { setActionError('A reason for the edit is required.'); return; }
    setActionError(null);
    try {
      const changed = Object.fromEntries(Object.entries(editing.fields).filter(([k, v]) => v !== (editing.item[k] ?? '')));
      if (Object.keys(changed).length === 0) { setEditing(null); return; }
      const r = await apiClient.patch(`/review/plan/${planDetail.id}/item/${editing.type}/${editing.item.id}`, {
        fields: changed, reason: editing.reason,
      });
      setActionNotice(`${r.data.message} New status: ${r.data.verification_status}.`);
      setEditing(null);
      await loadPlanDetail(planDetail.id);
      await loadQueue();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to save the edit.');
    }
  };

  const submitComment = async () => {
    if (!comment.trim()) return;
    try {
      await apiClient.post(`/review/plan/${planDetail.id}/comment`, { comment });
      setComment('');
      setActionNotice('Comment added to the audit trail.');
      setAuditTrail(null);
      if (showAudit) loadAuditTrail();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to add comment.');
    }
  };

  const regenerate = async () => {
    setIsRegenerating(true); setActionError(null);
    try {
      const r = await apiClient.post(`/review/plan/${planDetail.id}/regenerate`);
      setActionNotice(`${r.data.message} Result: ${r.data.verification_status}.`);
      await loadQueue();
      setExpandedId(r.data.new_plan_id);
      await loadPlanDetail(r.data.new_plan_id);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Regeneration failed.');
    } finally {
      setIsRegenerating(false);
    }
  };
  const [showAudit, setShowAudit] = useState(false);

  const loadQueue = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get('/review/queue', { params: { flagged_only: flaggedOnly } });
      setQueue(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load the review queue.');
    } finally {
      setIsLoading(false);
    }
  }, [flaggedOnly]);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  const loadPlanDetail = async (planId) => {
    setIsLoadingDetail(true);
    setActionError(null);
    setShowAudit(false);
    setAuditTrail(null);
    try {
      const [res, content] = await Promise.all([
        apiClient.get(`/review/plan/${planId}`),
        apiClient.get(`/onboarding/plan/${planId}`).catch(() => ({ data: null })),
      ]);
      setPlanDetail(res.data);
      setPlanContent(content.data);
      setNotes(res.data.reviewer_notes || '');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Could not load plan detail.');
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const toggleExpand = (planId) => {
    if (expandedId === planId) {
      setExpandedId(null);
      setPlanDetail(null);
      return;
    }
    setExpandedId(planId);
    setPlanDetail(null);
    loadPlanDetail(planId);
  };

  const handleDecision = async (action) => {
    if (!planDetail) return;
    setIsSubmittingDecision(true);
    setActionError(null);
    try {
      await apiClient.post(`/review/plan/${planDetail.id}/decision`, { action, notes });
      await loadPlanDetail(planDetail.id);
      await loadQueue();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to submit decision.');
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const startOverride = (result) => {
    setOverridingId(result.id);
    setOverrideStatus(result.overridden_status || result.validation_status || 'Verified');
    setOverrideReason('');
  };

  const submitOverride = async () => {
    if (!overrideReason.trim()) {
      setActionError('An override reason is required.');
      return;
    }
    setIsOverriding(true);
    setActionError(null);
    try {
      await apiClient.post(`/review/validation-result/${overridingId}/override`, {
        overridden_status: overrideStatus,
        reason: overrideReason,
      });
      setOverridingId(null);
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to submit override.');
    } finally {
      setIsOverriding(false);
    }
  };

  const loadAuditTrail = async () => {
    if (!planDetail) return;
    setShowAudit(true);
    if (auditTrail) return;
    try {
      const res = await apiClient.get(`/review/audit-trail/${planDetail.id}`);
      setAuditTrail(res.data);
    } catch (err) {
      setAuditTrail([]);
    }
  };

  const pager = usePagination(queue, { pageSize: 8, resetKey: flaggedOnly });
  const detailRef = useRef(null);

  // On small screens the detail panel sits below the queue — bring it into view.
  useEffect(() => {
    if (expandedId && window.matchMedia('(max-width: 1279px)').matches) {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [expandedId]);

  const selectedQueueItem = queue.find((p) => p.id === expandedId);

  return (
    <AppShell
      portalLabel="Reviewer Portal"
      navGroups={[{ label: 'Review', items: [{ key: 'queue', label: 'Review queue', icon: ClipboardList, badge: isLoading ? undefined : queue.length }] }]}
      activeKey="queue"
      onNavigate={() => {}}
      onLogout={onLogout}
      pageTitle="Review queue"
    >
      <PageHeader
        title="Manual review queue"
        description={`Plans awaiting a decision — signed in as ${user?.username || 'reviewer'}.`}
        actions={
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13px] text-slate-300">
            <input
              type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)}
              className="checkbox"
            />
            Flagged only
          </label>
        }
      />

      {error && <Alert tone="danger" className="mb-6" onDismiss={() => setError(null)}>{error}</Alert>}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        {/* Queue */}
        <Card padded={false} className="h-fit overflow-hidden">
          <div className="px-5 pb-3 pt-5">
            <CardHeader
              icon={ClipboardList}
              title="Pending plans"
              description={flaggedOnly ? 'Unsupported, contradictory, incomplete or needing review' : 'All plans pending review'}
            />
          </div>

          {isLoading && <SkeletonRows rows={4} />}

          {!isLoading && !error && queue.length === 0 && (
            <EmptyState icon={ClipboardList} title="Nothing pending review" description="New plans will appear here after generation." />
          )}

          <ul className="space-y-1 px-3 pb-3">
            {pager.pageItems.map((plan) => {
              const active = expandedId === plan.id;
              return (
                <li key={plan.id}>
                  <button
                    type="button"
                    onClick={() => toggleExpand(plan.id)}
                    aria-current={active ? 'true' : undefined}
                    className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                      active ? 'border-accent/30 bg-accent/[0.06]' : 'border-transparent hover:border-line hover:bg-white/[0.02]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[13.5px] font-medium text-slate-100">Plan #{plan.id}</span>
                      <StatusBadge status={plan.verification_status} />
                    </div>
                    <p className="mt-1 truncate text-[12px] text-subtle">
                      {plan.employee_name || `Employee #${plan.employee_id}`}{plan.role_name ? ` · ${plan.role_name}` : ''} · {new Date(plan.generated_at).toLocaleString()}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>

          <Pagination {...pager} onPageChange={pager.setPage} noun="plans" />
        </Card>

        {/* Detail */}
        <div ref={detailRef} className="min-w-0 scroll-mt-4 space-y-4">
          {!expandedId && (
            <Card className="border-dashed">
              <EmptyState
                icon={ShieldCheck}
                title="Select a plan to review"
                description="You'll see its scores, per-requirement validation results, and the decision panel."
              />
            </Card>
          )}

          {expandedId && isLoadingDetail && <Card><LoadingState label="Loading plan…" /></Card>}

          {expandedId && actionError && (
            <Alert tone="danger" onDismiss={() => setActionError(null)}>{actionError}</Alert>
          )}
          {expandedId && actionNotice && (
            <Alert tone="success" onDismiss={() => setActionNotice(null)}>{actionNotice}</Alert>
          )}

          {planDetail && planDetail.id === expandedId && !isLoadingDetail && (
            <motion.div
              key={planDetail.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease }}
              className="space-y-4"
            >
              <Card>
                <CardHeader
                  title={`Plan #${planDetail.id} — Employee #${planDetail.employee_id}`}
                  description={selectedQueueItem ? `Generated ${new Date(selectedQueueItem.generated_at).toLocaleString()}` : undefined}
                  actions={<StatusBadge status={planDetail.verification_status} />}
                />
                <div className="mt-5 grid grid-cols-3 gap-2 max-[379px]:grid-cols-1 sm:gap-3">
                  <ScoreMeter label="Coverage" value={planDetail.coverage_score} />
                  <ScoreMeter label="Traceability" value={planDetail.traceability_score} />
                  <ScoreMeter label="Consistency" value={planDetail.consistency_score} />
                </div>
              </Card>

              {/* Validation results with override control */}
              <Card padded={false} className="overflow-hidden">
                <div className="px-5 pb-3 pt-5">
                  <CardHeader
                    title="Validation results"
                    description={`${(planDetail.validation_results || []).length} requirement(s) — original Python results are never overwritten`}
                  />
                </div>
                <div className="max-h-[440px] overflow-y-auto border-t border-line">
                  {(planDetail.validation_results || []).length === 0 && (
                    <EmptyState
                      title="No validation results for this plan"
                      description="Ask an admin to run validation on it from the Onboarding pipeline."
                    />
                  )}
                  <ul className="divide-y divide-line">
                    {(planDetail.validation_results || []).map((r) => (
                      <li key={r.id} className="px-5 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="code-tag">{r.requirement_code}</span>
                              <StatusBadge status={r.validation_status} />
                              {r.overridden_status && (
                                <>
                                  <span className="text-[12px] text-subtle">overridden to</span>
                                  <StatusBadge status={r.overridden_status} />
                                </>
                              )}
                            </div>
                            {r.explanation && <p className="mt-1.5 text-[13px] text-muted text-break">{r.explanation}</p>}
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {r.source_reference && <Badge title="Source">{r.source_reference}</Badge>}
                              {r.coverage_status && <Badge tone={r.coverage_status === 'Covered' ? 'success' : 'danger'}>{r.coverage_status}</Badge>}
                              {r.traceability_status && <Badge tone={r.traceability_status === 'Traced' ? 'success' : 'warning'}>{r.traceability_status}</Badge>}
                              {(r.field_comparison || []).filter((f) => f.result === 'Mismatch').map((f, i) => (
                                <Badge key={i} tone="danger" title={`GenAI: ${f.genai} · Python: ${f.python}`}>{f.field} mismatch</Badge>
                              ))}
                            </div>
                            {r.overridden_by && (
                              <p className="mt-1.5 text-[12.5px] text-amber-300/90 text-break">
                                Overridden by {r.overridden_by}: &ldquo;{r.override_reason}&rdquo;
                              </p>
                            )}
                          </div>
                          <IconButton label="Override this result" icon={Edit3} size={15} onClick={() => startOverride(r)} />
                        </div>

                        <AnimatePresence initial={false}>
                          {overridingId === r.id && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2, ease }}
                              className="overflow-hidden"
                            >
                              <div className="card-inset mt-3 space-y-3 p-3.5">
                                <Field label="New status" htmlFor={`ov-status-${r.id}`}>
                                  <select
                                    id={`ov-status-${r.id}`}
                                    value={overrideStatus} onChange={(e) => setOverrideStatus(e.target.value)}
                                    className="select"
                                  >
                                    {['Verified', 'Source Support Missing', 'Requirement Missing', 'Unsupported Requirement', 'Outdated Source', 'Contradiction Detected'].map((st) => (
                                      <option key={st} value={st}>{st}</option>
                                    ))}
                                  </select>
                                </Field>
                                <Field label="Reason (required)" htmlFor={`ov-reason-${r.id}`}>
                                  <textarea
                                    id={`ov-reason-${r.id}`}
                                    rows={2} placeholder="Why are you overriding this result?"
                                    value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
                                    className="textarea"
                                  />
                                </Field>
                                <div className="flex flex-wrap justify-end gap-2">
                                  <Button size="sm" variant="ghost" onClick={() => setOverridingId(null)}>Cancel</Button>
                                  <Button size="sm" variant="primary" loading={isOverriding} onClick={submitOverride}>
                                    {isOverriding ? 'Saving…' : 'Save override'}
                                  </Button>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </li>
                    ))}
                  </ul>
                </div>
              </Card>

              {/* Decision panel */}
              <Card>
                <CardHeader
                  title="Reviewer decision"
                  description={planDetail.reviewed_by
                    ? `Last reviewed by ${planDetail.reviewed_by} on ${new Date(planDetail.reviewed_at).toLocaleString()}`
                    : 'Approve, reject, or send back for regeneration.'}
                  actions={<StatusBadge status={planDetail.review_status} />}
                />
                <div className="mt-4 space-y-3">
                  <Field label="Notes (optional)" htmlFor="review-notes">
                    <textarea
                      id="review-notes"
                      rows={3} placeholder="Notes for this decision…"
                      value={notes} onChange={(e) => setNotes(e.target.value)}
                      className="textarea"
                    />
                  </Field>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="success" icon={CheckCircle2} disabled={isSubmittingDecision} onClick={() => handleDecision('Approved')}>
                      Approve
                    </Button>
                    <Button variant="danger" icon={XCircle} disabled={isSubmittingDecision} onClick={() => handleDecision('Rejected')}>
                      Reject
                    </Button>
                    <Button variant="warning" icon={RotateCcw} disabled={isSubmittingDecision} onClick={() => handleDecision('Needs Regeneration')}>
                      Needs regeneration
                    </Button>
                    <Button variant="secondary" icon={RefreshCw} loading={isRegenerating} onClick={regenerate}>
                      Regenerate now
                    </Button>
                    <Button variant="ghost" icon={History} onClick={loadAuditTrail} className="sm:ml-auto">
                      Audit trail
                    </Button>
                  </div>
                  {planDetail.review_status === 'Needs Regeneration' && (
                    <Alert tone="warning">
                      Marked for regeneration. Use &ldquo;Regenerate now&rdquo; to create a new plan for this employee; it is
                      validated automatically and appears in this queue.
                    </Alert>
                  )}
                  <div className="flex flex-col gap-2 border-t border-line pt-3 sm:flex-row">
                    <input className="input" placeholder="Add a comment to the audit trail…" value={comment}
                      onChange={(e) => setComment(e.target.value)} aria-label="Comment" />
                    <Button variant="secondary" icon={MessageSquare} onClick={submitComment} disabled={!comment.trim()}>Comment</Button>
                  </div>
                </div>
              </Card>

              {planContent && (
                <Card padded={false} className="overflow-hidden">
                  <div className="px-5 pb-3 pt-5">
                    <CardHeader title="Plan content" description="Edit a generated item; the change is audited and the plan is re-validated." />
                  </div>
                  <ul className="max-h-[420px] divide-y divide-line overflow-y-auto border-t border-line">
                    {[
                      ...(planContent.modules || []).map((x) => ['module', x, x.title, x.purpose]),
                      ...(planContent.checklist_items || []).map((x) => ['checklist', x, x.activity, x.due_stage]),
                      ...(planContent.tasks || []).map((x) => ['task', x, x.task_description, x.expected_outcome]),
                      ...(planContent.quizzes || []).map((x) => ['quiz', x, x.question_text, `Answer: ${x.correct_answer}`]),
                    ].map(([type, item, title, sub]) => (
                      <li key={`${type}-${item.id}`} className="flex items-start justify-between gap-3 px-5 py-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge>{type}</Badge>
                            <p className="text-[13px] font-medium text-slate-100 text-break">{title}</p>
                          </div>
                          {sub && <p className="mt-1 text-[12.5px] text-muted text-break">{sub}</p>}
                        </div>
                        <IconButton label={`Edit ${type}`} icon={Edit3} size={15} onClick={() => startEdit(type, item)} />
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {showAudit && (
                <Card>
                  <CardHeader icon={ShieldCheck} title="Audit trail" description="Every decision and override on this plan." />
                  <div className="mt-4">
                    {!auditTrail && <LoadingState label="Loading history…" className="!py-4" />}
                    {auditTrail && auditTrail.length === 0 && <p className="text-[13px] text-subtle">No history yet.</p>}
                    {auditTrail && auditTrail.length > 0 && (
                      <ol className="max-h-72 space-y-2 overflow-y-auto">
                        {auditTrail.map((log) => (
                          <li key={log.id} className="card-inset p-3 text-[13px]">
                            <p className="text-slate-300 text-break">
                              <span className="font-semibold text-accent">{log.action}</span> by {log.reviewed_by}
                              <span className="text-subtle"> · {new Date(log.created_at).toLocaleString()}</span>
                            </p>
                            <p className="mt-1 text-muted text-break">
                              {log.original_result} <span className="text-subtle">→</span> <span className="text-slate-200">{log.reviewer_decision}</span>
                            </p>
                            {log.comment && <p className="mt-1 italic text-subtle text-break">&ldquo;{log.comment}&rdquo;</p>}
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                </Card>
              )}
            </motion.div>
          )}
        </div>
      </div>
      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        icon={Edit3}
        title={editing ? `Edit ${editing.type}` : ''}
        subtitle="The original text is kept in the audit trail and the plan is validated again after saving."
        footer={<><Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button><Button variant="primary" onClick={saveEdit}>Save and re-validate</Button></>}
      >
        {editing && (
          <div className="space-y-3">
            {Object.entries(editing.fields).map(([k, v]) => (
              <Field key={k} label={k.replace(/_/g, ' ')} htmlFor={`edit-${k}`}>
                <textarea id={`edit-${k}`} rows={k === 'purpose' || k.includes('description') || k === 'explanation' ? 3 : 1}
                  className="textarea !min-h-0" value={v ?? ''}
                  onChange={(e) => setEditing({ ...editing, fields: { ...editing.fields, [k]: e.target.value } })} />
              </Field>
            ))}
            <Field label="Reason for the edit (required)" htmlFor="edit-reason">
              <input id="edit-reason" className="input" value={editing.reason}
                onChange={(e) => setEditing({ ...editing, reason: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>
    </AppShell>
  );
};

export default ReviewerDashboard;
