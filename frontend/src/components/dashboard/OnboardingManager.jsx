import React, { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Sparkles, AlertCircle, BookOpen, ListChecks, ClipboardList, HelpCircle, RefreshCw,
  ChevronDown, ShieldCheck, ShieldAlert, Copy, Target, GitBranch, History, UserRound,
  FileJson, ShieldX, Scale, Columns3, Repeat2, GraduationCap, Gauge, Lightbulb, Award,
} from 'lucide-react';
import apiClient from '../../api/apiClient';
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, LoadingState, PageHeader,
  ScoreMeter, StatusBadge, ease, errorMessage,
} from '../ui/primitives';
import { Modal } from '../ui/Modal';
import { Pagination, usePagination } from '../ui/Pagination';

/* ==========================================================================
   OnboardingManager — REAL backend connection
   Calls:
     POST /onboarding/generate/{employee_id}   generate + save a new plan
     GET  /onboarding/employee/{employee_id}   list past plans for employee
     GET  /onboarding/plan/{plan_id}           full plan detail
     POST /validation/revalidate/{plan_id}     run the Python validation
          pipeline on THIS specific plan
   Needs `employees` (from AdminDashboard) to populate the picker.
   ========================================================================== */

/* --- Collapsible section for plan content ------------------------------ */
const Section = ({ title, icon: Icon, count, children, defaultOpen }) => {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <Card padded={false} className="overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-white/[0.02]"
      >
        <span className="flex min-w-0 items-center gap-2.5 text-[14px] font-semibold text-fg">
          <Icon size={16} className="shrink-0 text-subtle" />
          <span className="truncate">{title}</span>
          <Badge>{count}</Badge>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2, ease }} className="text-subtle">
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease }}
            className="overflow-hidden"
          >
            <div className="space-y-2.5 border-t border-line px-5 py-4">
              {count === 0 ? <p className="text-[13px] text-subtle">Nothing in this section.</p> : children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
};

const Reasons = ({ reasons, tone = 'amber' }) => {
  if (!reasons || reasons.length === 0) return null;
  const color = tone === 'rose' ? 'text-rose-300' : 'text-amber-300';
  return (
    <ul className={`mt-2.5 list-disc space-y-1 pl-4 text-[12.5px] ${color}`}>
      {reasons.map((r, i) => <li key={i} className="text-break">{r}</li>)}
    </ul>
  );
};

/* Renders one flagged item, formatted according to which check produced it
   (each checker returns a different shape — see backend python_validation
   files). Older saved results (plain strings / older shapes) still render. */
const FlaggedItem = ({ item, checkKey }) => {
  const base = 'card-inset p-4 text-[13px] leading-relaxed text-slate-300';
  const label = (text) => (text ? <p className="mb-1.5 text-[12.5px] font-semibold text-slate-100">{text}</p> : null);

  if (checkKey === 'hallucination' && item && typeof item === 'object') {
    return (
      <div className={base}>
        {label(item.label)}
        <p className="whitespace-pre-wrap text-break">{item.text}</p>
        <Reasons reasons={item.reasons} />
        {item.terms_not_in_source?.length > 0 && (
          <p className="mt-2 text-[12px] text-subtle text-break">
            Terms not found in sources: {item.terms_not_in_source.join(', ')}
          </p>
        )}
        <p className="mt-1 text-[12px] text-subtle">
          Key-term overlap with sources: {Math.round((item.overlap_ratio ?? 0) * 100)}%
          {item.source_requirement_code ? ` · Cites ${item.source_requirement_code}` : ''}
          {item.source_document_code ? ` · ${item.source_document_code}` : ''}
        </p>
      </div>
    );
  }

  if (checkKey === 'contradiction' && item && typeof item === 'object') {
    return (
      <div className={base}>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          {label(item.label)}
          <Badge tone="danger">{item.conflict_type}</Badge>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="min-w-0 rounded-lg border border-line p-3">
            <p className="eyebrow mb-1">Generated plan says</p>
            <p className="whitespace-pre-wrap text-break">{item.generated_text}</p>
          </div>
          <div className="min-w-0 rounded-lg border border-line p-3">
            <p className="eyebrow mb-1">Source says{item.source_origin ? ` · ${item.source_origin}` : ''}</p>
            <p className="whitespace-pre-wrap text-break">{item.source_text || '—'}</p>
          </div>
        </div>
        {item.detail && <p className="mt-2.5 text-[12.5px] text-rose-300">{item.detail}</p>}
      </div>
    );
  }

  if (checkKey === 'role_relevance' && item && typeof item === 'object') {
    return (
      <div className={base}>
        {label(item.label)}
        <p className="whitespace-pre-wrap text-break">{item.text}</p>
        {item.reason && <Reasons reasons={[item.reason]} />}
      </div>
    );
  }

  if (checkKey === 'sequence' && item && typeof item === 'object') {
    return (
      <div className={base}>
        <p className="font-medium text-slate-100 text-break">{item.module}</p>
        <p className="mt-1 text-[12.5px] text-amber-300 text-break">{item.issue}</p>
      </div>
    );
  }

  if (checkKey === 'schema' && item && typeof item === 'object') {
    return (
      <div className={base}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="code-tag">{item.path}</span>
          <Badge tone={item.severity === 'error' ? 'danger' : 'warning'}>{item.kind?.replace(/_/g, ' ')}</Badge>
        </div>
        <p className="mt-1.5 text-break">{item.message}</p>
      </div>
    );
  }

  if (checkKey === 'quiz' && item && typeof item === 'object') {
    return (
      <div className={base}>
        {label(item.label)}
        <p className="whitespace-pre-wrap text-break">{item.question}</p>
        {item.correct_answer?.length > 0 && <p className="mt-1 text-[12px] text-subtle">Correct answer: {item.correct_answer.join('; ')}</p>}
        <Reasons reasons={item.problems} />
      </div>
    );
  }

  if (checkKey === 'security' && item && typeof item === 'object') {
    return (
      <div className={base}>
        {label(item.label_item)}
        <Badge tone="danger">{item.label}</Badge>
        <p className="mt-2 text-rose-200/90 text-break">&ldquo;{item.sentence}&rdquo;</p>
      </div>
    );
  }

  if (checkKey === 'outdated' && item && typeof item === 'object') {
    if (item.requirement_codes) {
      return (
        <div className={base}>
          <p className="font-medium text-slate-100">Requirement Matrix link is stale</p>
          <p className="mt-1 text-break">
            {item.requirement_codes.join(', ')} still point at {item.linked_document_code} (v{item.linked_version})
            {item.active_document_code ? `; the active version is ${item.active_document_code} (v${item.active_version}), which was used instead.` : '; no active version exists.'}
          </p>
        </div>
      );
    }
    return (
      <div className={base}>
        {label(item.label)}
        <p className="text-break">{item.text}</p>
        <Reasons reasons={[`Cites obsolete document version ${item.document_code}`]} tone="rose" />
      </div>
    );
  }

  if (checkKey === 'precedence' && item && typeof item === 'object') {
    return (
      <div className={base}>
        {label(item.label)}
        <p className="text-break">{item.generated_text}</p>
        <p className="mt-2 text-[12.5px] text-subtle text-break">Lower-precedence source ({item.source_origin}): &ldquo;{item.source_text}&rdquo;</p>
        <p className="mt-1.5 text-[12.5px] text-emerald-300/90">{item.resolution}</p>
      </div>
    );
  }

  if (typeof item === 'string') {
    return <div className={base}><p className="whitespace-pre-wrap text-break">{item}</p></div>;
  }

  return <div className={base}><pre className="whitespace-pre-wrap text-break font-mono text-[12px]">{JSON.stringify(item, null, 2)}</pre></div>;
};

/* --- Inline validation panel, shown inside the plan detail once run --- */
const ValidationPanel = ({ validation }) => {
  const [openModal, setOpenModal] = useState(null); // which check's modal is open, or null

  if (!validation) return null;

  const duplicateItems = Object.entries(validation.duplicates?.details || {})
    .flatMap(([section, items]) => (items || []).map((text) => `[${section}] ${text}`));

  const checks = [
    {
      key: 'hallucination', label: 'Hallucination check', icon: ShieldAlert,
      description: 'Generated items not supported by the linked source documents or this role\'s Requirement Matrix.',
      items: validation.hallucination?.unsupported_items || [],
      total: validation.hallucination?.total_items,
      insufficientSource: validation.hallucination?.status === 'insufficient_source',
      message: validation.hallucination?.message,
    },
    {
      key: 'contradiction', label: 'Contradiction check', icon: AlertCircle,
      description: 'Statements that conflict with a source sentence on the same topic (opposite rule or a different value).',
      items: validation.contradiction?.contradictions || [],
      total: validation.contradiction?.total_items,
      insufficientSource: validation.contradiction?.status === 'insufficient_source',
      message: validation.contradiction?.message,
    },
    {
      key: 'duplicates', label: 'Duplicate check', icon: Copy,
      description: 'Exact or near-duplicate modules, checklist items, tasks and quiz questions.',
      items: duplicateItems,
      total: validation.duplicates?.total_items,
    },
    {
      key: 'role_relevance', label: 'Role relevance', icon: Target,
      description: 'Items that do not relate to this employee\'s role requirements, or cite another role\'s requirement.',
      items: validation.role_relevance?.irrelevant_items || [],
      total: validation.role_relevance?.total_items,
      insufficientSource: validation.role_relevance?.status === 'insufficient_source',
      message: validation.role_relevance?.message,
    },
    {
      key: 'sequence', label: 'Learning sequence', icon: GitBranch,
      description: 'Stages, prerequisites, advanced-before-basic and assessment-before-learning checks.',
      items: validation.sequence?.issues || [],
      total: validation.sequence?.total_items,
    },
    {
      key: 'quiz', label: 'Quiz validation', icon: HelpCircle,
      description: 'Correct answers must be options and grounded in the source; distractors must not be true.',
      items: validation.quiz?.issues || [],
      total: validation.quiz?.total_items,
    },
    {
      key: 'schema', label: 'JSON schema', icon: FileJson,
      description: 'Structure of the GenAI output plus invalid, obsolete or duplicate IDs.',
      items: [...(validation.schema?.structural_errors || []), ...(validation.schema?.semantic_findings || [])],
    },
    {
      key: 'outdated', label: 'Outdated sources', icon: History,
      description: 'Items citing superseded document versions, and matrix rows still linked to them.',
      items: [...(validation.outdated?.outdated_citations || []), ...(validation.outdated?.stale_requirement_links || [])],
    },
    {
      key: 'security', label: 'Prompt-injection check', icon: ShieldX,
      description: 'Instruction-like text found in the generated output.',
      items: validation.security?.findings || [],
    },
  ];
  if ((validation.contradiction?.resolved_by_precedence || []).length > 0) {
    checks.push({
      key: 'precedence', label: 'Resolved by precedence', icon: Scale,
      description: 'Conflicts with a lower-precedence source (e.g. an FAQ) where the plan correctly followed the higher-precedence source.',
      items: validation.contradiction.resolved_by_precedence,
      info: true,
    });
  }
  const metrics = validation.metrics || {};

  const activeCheck = checks.find((c) => c.key === openModal);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease }}>
      <Card className="border-accent/15">
        <CardHeader
          icon={ShieldCheck}
          title="Python ground-truth validation"
          description={`Overall ${validation.overall_score}% · ${validation.coverage?.covered}/${validation.coverage?.total} requirements covered`}
          actions={<StatusBadge status={validation.validation_status} />}
        />

        <div className="mt-4 space-y-3 empty:hidden">
          {checks.some((c) => c.insufficientSource) && (
            <Alert tone="warning">
              Some checks could not run (see "No source" cards) — this role has no linked source document text
              and no Requirement Matrix text to verify against.
            </Alert>
          )}

          {!checks.some((c) => c.insufficientSource) && validation.hallucination?.message && (
            <Alert tone="info">{validation.hallucination.message}</Alert>
          )}

          {validation.status_reasons?.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-5 text-[12.5px] text-muted">
              {validation.status_reasons.map((r, i) => <li key={i} className="text-break">{r}</li>)}
            </ul>
          )}
        </div>

        {validation.metrics && (
          <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ['Required', metrics.required_requirements], ['Covered', metrics.covered_requirements],
              ['Missing', metrics.missing_requirement_count], ['Unsupported', metrics.unsupported_requirement_count],
              ['Duplicates', metrics.duplicate_requirement_count], ['Contradictions', metrics.contradiction_count],
            ].map(([k, v]) => (
              <div key={k} className="card-inset px-3 py-2">
                <dt className="text-[11.5px] text-subtle">{k}</dt>
                <dd className="text-[16px] font-semibold tabular-nums text-fg">{v ?? 0}</dd>
              </div>
            ))}
          </dl>
        )}

        {validation.consistency?.comparisons?.length > 0 && (
          <div className="mt-3 flex justify-end">
            <Button size="sm" variant="ghost" icon={Columns3} onClick={() => setOpenModal('comparison')}>
              GenAI vs Python field comparison
            </Button>
          </div>
        )}

        <div className="mt-5 grid grid-cols-1 gap-2.5 border-t border-line pt-5 sm:grid-cols-2">
          {checks.map(({ key, label, icon: Icon, items, total, insufficientSource, message, info }) => {
            const problemCount = items.length;
            const clean = !insufficientSource && problemCount === 0;
            const tone = insufficientSource ? 'neutral' : clean ? 'success' : info ? 'info' : 'warning';

            return (
              <button
                key={key}
                type="button"
                onClick={() => (problemCount > 0 || insufficientSource) && setOpenModal(key)}
                disabled={clean}
                className={`card-inset min-w-0 p-3.5 text-left transition-colors ${
                  clean ? 'cursor-default' : 'hover:border-line-strong hover:bg-surface-3'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 text-[13px] font-medium text-slate-100">
                    <Icon size={15} className={clean ? 'text-emerald-400/80' : insufficientSource ? 'text-subtle' : 'text-amber-400/90'} />
                    <span className="truncate">{label}</span>
                  </span>
                  <Badge tone={tone} dot>
                    {insufficientSource
                      ? 'No source'
                      : clean
                      ? (total ? `Clean · ${total}` : 'Clean')
                      : (total ? `${problemCount} of ${total}` : `${problemCount} flagged`)}
                  </Badge>
                </div>
                {insufficientSource && message && (
                  <p className="mt-2 text-[12px] leading-snug text-subtle text-break">{message}</p>
                )}
                {!insufficientSource && !clean && (
                  <p className="mt-1.5 text-[12px] text-subtle">View full details</p>
                )}
              </button>
            );
          })}
        </div>
      </Card>

      <Modal
        open={openModal === 'comparison'}
        onClose={() => setOpenModal(null)}
        size="xl"
        icon={Columns3}
        title="GenAI output vs Python ground truth"
        subtitle="Structured fields of every generated item compared with the Requirement Matrix row it cites (SRS Table 1)."
      >
        <div className="table-wrap card-inset">
          <table className="table">
            <thead><tr><th>Item</th><th>Requirement</th><th>Field</th><th>GenAI output</th><th>Python ground truth</th><th>Result</th></tr></thead>
            <tbody>
              {(validation.consistency?.comparisons || []).map((c, i) => (
                <tr key={i}>
                  <td className="text-[12.5px]">{c.item}</td>
                  <td className="code-tag">{c.requirement_code}</td>
                  <td>{c.field}</td>
                  <td className="text-break">{String(c.genai ?? '—')}</td>
                  <td className="text-break">{String(c.python ?? '—')}</td>
                  <td><Badge tone={c.result === 'Match' ? 'success' : 'danger'} dot>{c.result}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Modal>

      <Modal
        open={!!activeCheck}
        onClose={() => setOpenModal(null)}
        title={activeCheck ? `${activeCheck.label} — ${activeCheck.items.length} item(s)` : ''}
        subtitle={activeCheck ? [activeCheck.description, activeCheck.message].filter(Boolean).join(' ') : ''}
        icon={activeCheck?.icon}
      >
        {activeCheck && (
          <div className="space-y-3">
            {activeCheck.items.length === 0 ? (
              <p className="text-[13px] text-subtle">No items to show.</p>
            ) : (
              activeCheck.items.map((item, i) => (
                <FlaggedItem key={i} item={item} checkKey={activeCheck.key} />
              ))
            )}
          </div>
        )}
      </Modal>
    </motion.div>
  );
};

/* --- Progress assessment (SRS 53-56): outcome, weak areas, recommendations --- */
export const outcomeTone = (o) => ({ 'Completed': 'success', 'On Track': 'success', 'Requires Attention': 'warning',
  'Assessment Required': 'info', 'Behind Schedule': 'danger' }[o] || 'neutral');

export const ProgressPanel = ({ planId, refreshKey }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!planId) return;
    setData(null); setError(null);
    apiClient.get(`/onboarding/plan/${planId}/progress-assessment`).then((r) => setData(r.data))
      .catch((e) => setError(errorMessage(e, 'Could not assess progress.')));
  }, [planId, refreshKey]);

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!data) return <Card><LoadingState label="Assessing progress…" /></Card>;
  return (
    <Card>
      <CardHeader icon={Gauge} title="Progress assessment"
        description={`${data.progress_percent}% complete · quiz ${data.quiz.score ?? '—'}${data.quiz.score != null ? '%' : ''} · assessments ${data.assessment_average ?? '—'}${data.assessment_average != null ? '%' : ''}`}
        actions={<Badge tone={outcomeTone(data.outcome)} dot>{data.outcome}</Badge>} />
      <div className="mt-4 grid grid-cols-3 gap-2">
        {[['Modules', data.module_completion], ['Checklist', data.checklist_completion], ['Tasks', data.task_completion]].map(([k, v]) => (
          <div key={k} className="card-inset px-3 py-2">
            <p className="text-[11.5px] text-subtle">{k}</p>
            <p className="text-[15px] font-semibold tabular-nums">{v.completed}/{v.total}</p>
          </div>
        ))}
      </div>
      {data.overdue_items.length > 0 && (
        <p className="mt-3 text-[12.5px] text-rose-300">{data.overdue_items.length} overdue: {data.overdue_items.slice(0, 3).map((i) => i.name).join('; ')}{data.overdue_items.length > 3 ? '…' : ''}</p>
      )}
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="eyebrow mb-2">Weak areas</p>
          {data.weak_areas.length === 0 ? <p className="text-[13px] text-subtle">None identified yet.</p> : (
            <ul className="space-y-1.5">
              {data.weak_areas.map((w, i) => (
                <li key={i} className="text-[13px] text-slate-200 text-break">
                  <span className="font-medium">{w.topic}</span> <span className="text-subtle">— {w.reason} ({w.detail})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="eyebrow mb-2">Recommendations</p>
          {data.recommendations.length === 0 ? <p className="text-[13px] text-subtle">No action needed.</p> : (
            <ul className="space-y-1.5">
              {data.recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px]">
                  <Lightbulb size={14} className="mt-0.5 shrink-0 text-amber-300/90" />
                  <span className="min-w-0 text-break"><span className="font-medium text-slate-100">{r.type}:</span> <span className="text-muted">{r.target} — {r.reason}</span></span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
};

/* --- Assessments with rubric + score entry (SRS 23-24, 53) --- */
export const AssessmentList = ({ planId, assessments, canScore, onScored }) => {
  const [scores, setScores] = useState({});
  const [saved, setSaved] = useState({}); // assessment id -> {score, status} returned by the backend
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const save = async (a) => {
    setBusy(a.id); setError(null);
    try {
      const r = await apiClient.post(`/onboarding/plan/${planId}/assessment/${a.id}/score`, { score: parseFloat(scores[a.id]) });
      setSaved((prev) => ({ ...prev, [a.id]: r.data }));
      onScored?.();
    } catch (e) { setError(errorMessage(e, 'Could not save score.')); } finally { setBusy(null); }
  };
  return (
    <div className="space-y-2.5">
      {error && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}
      {assessments.map((orig) => { const a = { ...orig, ...(saved[orig.id] || {}) }; return (
        <div key={a.id} className="card-inset p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[13.5px] font-semibold text-slate-100 text-break">{a.title}</p>
              <p className="mt-0.5 text-[12px] text-subtle">{(a.assessment_type || '').replace('_', ' ')} · {a.due_stage || 'no stage'} · {a.difficulty || '—'}{a.source_requirement_code ? ` · ${a.source_requirement_code}` : ''}</p>
            </div>
            <Badge tone={a.status === 'Passed' ? 'success' : a.status === 'Failed' ? 'danger' : 'neutral'} dot>
              {a.status}{a.score != null ? ` · ${a.score}%` : ''}
            </Badge>
          </div>
          {a.description && <p className="mt-2 text-[13px] text-muted text-break">{a.description}</p>}
          {a.rubric?.length > 0 && (
            <div className="table-wrap mt-3 rounded-lg border border-line">
              <table className="table">
                <thead><tr><th>Criterion</th><th>Weight</th><th>Expected performance</th><th>Pass condition</th></tr></thead>
                <tbody>
                  {a.rubric.map((r, i) => (
                    <tr key={i}><td className="text-break">{r.criterion}</td><td className="tabular-nums">{r.weight}</td>
                      <td className="text-break">{r.expected_performance}</td><td className="text-break">{r.pass_condition}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {canScore && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input type="number" min="0" max="100" aria-label={`Score for ${a.title}`} placeholder="Score 0-100"
                className="input !h-8 !w-32 !text-[13px]" value={scores[a.id] ?? ''} onChange={(e) => setScores({ ...scores, [a.id]: e.target.value })} />
              <Button size="sm" variant="secondary" loading={busy === a.id} disabled={scores[a.id] === undefined || scores[a.id] === ''} onClick={() => save(a)}>
                Save score
              </Button>
            </div>
          )}
        </div>
      ); })}
    </div>
  );
};

/* --- GenAI consistency check (SRS 44-45) --- */
const ConsistencyModal = ({ employeeId, open, onClose }) => {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!open || !employeeId) return;
    setResult(null); setError(null);
    apiClient.get(`/validation/consistency/${employeeId}`).then((r) => setHistory(r.data)).catch(() => setHistory([]));
  }, [open, employeeId]);
  const run = async () => {
    setRunning(true); setError(null);
    try {
      const r = await apiClient.post(`/validation/consistency/${employeeId}`, null, { params: { runs: 2 } });
      setResult(r.data); setHistory((h) => [r.data, ...h]);
    } catch (e) { setError(errorMessage(e, 'Consistency check failed.')); } finally { setRunning(false); }
  };
  const shown = result || history[0];
  return (
    <Modal open={open} onClose={() => !running && onClose()} icon={Repeat2} title="GenAI consistency check"
      subtitle="Runs the same generation twice with identical prompt, model settings and sources, then compares mandatory requirements, sources, module categories and assessment topics (not wording). Uses 2 GenAI calls; nothing is saved as a plan."
      footer={<><Button variant="ghost" onClick={onClose} disabled={running}>Close</Button><Button variant="primary" icon={Repeat2} loading={running} onClick={run}>{running ? 'Running 2 generations…' : 'Run check'}</Button></>}>
      {error && <Alert tone="danger" className="mb-3">{error}</Alert>}
      {!shown && !running && <EmptyState icon={Repeat2} title="No consistency runs yet" />}
      {shown && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-[28px] font-semibold tabular-nums">{Math.round(shown.score)}%</p>
            <Badge tone={shown.score >= 80 ? 'success' : shown.score >= 60 ? 'warning' : 'danger'} dot>Consistency score</Badge>
            <span className="text-[12px] text-subtle">{shown.prompt_version} · {shown.model_used}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(shown.per_dimension || {}).map(([k, v]) => (
              <div key={k} className="card-inset px-3 py-2"><p className="text-[11.5px] text-subtle">{k.replace(/_/g, ' ')}</p><p className="text-[15px] font-semibold tabular-nums">{Math.round(v)}%</p></div>
            ))}
          </div>
          {(shown.major_differences || []).length === 0 ? <Alert tone="success">No major differences between runs.</Alert> : (
            (shown.major_differences || []).map((d) => (
              <Alert key={d.dimension} tone="warning" title={`Major difference: ${d.dimension.replace(/_/g, ' ')} (${Math.round(d.score)}%)`}>
                Only in some runs: {d.only_in_some_runs.join(', ') || '—'}
              </Alert>
            ))
          )}
        </div>
      )}
    </Modal>
  );
};

export const OnboardingManager = ({ employees, initialEmployeeId = '' }) => {
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(initialEmployeeId);
  const [plans, setPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState(null);

  const [isValidating, setIsValidating] = useState(false);
  const [validation, setValidation] = useState(null);
  const [consistencyOpen, setConsistencyOpen] = useState(false);
  const [extraQuizBusy, setExtraQuizBusy] = useState(false);
  const [progressKey, setProgressKey] = useState(0);
  const [notice, setNotice] = useState(null);

  const refreshPlans = useCallback(async (employeeId) => {
    if (!employeeId) {
      setPlans([]);
      return;
    }
    setIsLoadingPlans(true);
    try {
      const res = await apiClient.get(`/onboarding/employee/${employeeId}`);
      setPlans(res.data);
    } catch (err) {
      setError('Failed to load past plans for this employee.');
    } finally {
      setIsLoadingPlans(false);
    }
  }, []);

  useEffect(() => {
    setSelectedPlan(null);
    setValidation(null);
    setError(null);
    refreshPlans(selectedEmployeeId);
  }, [selectedEmployeeId, refreshPlans]);

  const handleGenerate = async () => {
    if (!selectedEmployeeId) return;
    setIsGenerating(true);
    setError(null);
    setValidation(null);
    try {
      const res = await apiClient.post(`/onboarding/generate/${selectedEmployeeId}`);
      setSelectedPlan(res.data);
      // Pipeline 2 already ran automatically on the server
      setValidation(res.data.last_validation_report || null);
      await refreshPlans(selectedEmployeeId);
    } catch (err) {
      setError(errorMessage(err, 'Failed to generate onboarding plan.'));
    } finally {
      setIsGenerating(false);
    }
  };

  const openPlan = async (planId) => {
    setIsLoadingDetail(true);
    setError(null);
    setValidation(null);
    try {
      const res = await apiClient.get(`/onboarding/plan/${planId}`);
      setSelectedPlan(res.data);
      setValidation(res.data.last_validation_report || null);
    } catch (err) {
      setError('Failed to load plan detail.');
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleValidate = async () => {
    if (!selectedPlan) return;
    setIsValidating(true);
    setError(null);
    try {
      const res = await apiClient.post(`/validation/revalidate/${selectedPlan.id}`);
      setValidation(res.data.data);
      setSelectedPlan((prev) => prev && ({
        ...prev,
        coverage_score: res.data.data.coverage?.score,
        traceability_score: res.data.data.traceability?.score,
        consistency_score: res.data.data.consistency?.score,
        verification_status: res.data.data.validation_status,
      }));
      await refreshPlans(selectedEmployeeId);
    } catch (err) {
      setError(errorMessage(err, 'Validation failed.'));
    } finally {
      setIsValidating(false);
    }
  };

  const reloadSelected = async () => {
    if (!selectedPlan) return;
    const res = await apiClient.get(`/onboarding/plan/${selectedPlan.id}`);
    setSelectedPlan(res.data);
    setValidation(res.data.last_validation_report || null);
    setProgressKey((k) => k + 1);
  };

  const handleExtraQuiz = async () => {
    if (!selectedPlan) return;
    setExtraQuizBusy(true); setError(null); setNotice(null);
    try {
      const before = selectedPlan.quizzes?.length || 0;
      const res = await apiClient.post(`/onboarding/plan/${selectedPlan.id}/additional-quiz`);
      setSelectedPlan(res.data);
      setValidation(res.data.last_validation_report || null);
      setNotice(`${(res.data.quizzes?.length || 0) - before} practice question(s) added for weak topics and re-validated.`);
      setProgressKey((k) => k + 1);
    } catch (err) {
      setError(errorMessage(err, 'Could not generate an additional quiz.'));
    } finally {
      setExtraQuizBusy(false);
    }
  };

  const selectedEmployee = employees.find((e) => e.id === parseInt(selectedEmployeeId, 10));
  const planPager = usePagination(plans, { pageSize: 5, resetKey: selectedEmployeeId });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Onboarding pipeline"
        description="Generate a personalized onboarding plan, then validate it against the Requirement Matrix from the same screen."
      />

      {error && <Alert tone="danger" onDismiss={() => setError(null)}><span className="whitespace-pre-wrap">{error}</span></Alert>}

      {employees.length === 0 && (
        <Alert tone="warning">No employees exist yet. Register an employee (with a role) in Employees first.</Alert>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        {/* LEFT: picker + history */}
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader icon={UserRound} title="Employee" description="Plans are generated per employee." />
            <div className="mt-4 space-y-3">
              <Field label="Select employee" htmlFor="onb-employee">
                <select
                  id="onb-employee"
                  value={selectedEmployeeId}
                  onChange={(e) => setSelectedEmployeeId(e.target.value)}
                  className="select"
                >
                  <option value="">Choose an employee…</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name} ({emp.employee_code})
                    </option>
                  ))}
                </select>
              </Field>

              <Button
                variant="primary"
                block
                icon={Sparkles}
                loading={isGenerating}
                onClick={handleGenerate}
                disabled={!selectedEmployeeId}
              >
                {isGenerating ? 'Generating (calls Groq)…' : 'Generate new plan'}
              </Button>
            </div>
          </Card>

          <Card padded={false} className="overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-5 pb-3 pt-5">
              <CardHeader icon={History} title="Past plans" />
              <button
                type="button"
                onClick={() => refreshPlans(selectedEmployeeId)}
                className="btn btn-icon"
                aria-label="Refresh plans"
                disabled={!selectedEmployeeId}
              >
                <RefreshCw size={15} className={isLoadingPlans ? 'animate-spin' : ''} />
              </button>
            </div>

            <div className="px-3 pb-3">
              {!selectedEmployeeId && (
                <p className="px-2 pb-3 text-[13px] text-subtle">Select an employee to see their plan history.</p>
              )}
              {selectedEmployeeId && plans.length === 0 && !isLoadingPlans && (
                <p className="px-2 pb-3 text-[13px] text-subtle">No plans generated yet for this employee.</p>
              )}

              <ul className="space-y-1">
                {planPager.pageItems.map((p) => {
                  const active = selectedPlan?.id === p.id;
                  return (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => openPlan(p.id)}
                        aria-current={active ? 'true' : undefined}
                        className={`w-full rounded-lg border px-3 py-2.5 text-left transition-colors ${
                          active
                            ? 'border-accent/30 bg-accent/[0.06]'
                            : 'border-transparent hover:border-line hover:bg-white/[0.02]'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[13px] font-medium text-slate-100">Plan #{p.id}</span>
                          <StatusBadge status={p.verification_status} />
                        </div>
                        <p className="mt-1 truncate text-[12px] text-subtle">
                          {new Date(p.generated_at).toLocaleString()} · {p.model_used || 'unknown model'}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
            {plans.length > planPager.pageSize && (
              <Pagination {...planPager} onPageChange={planPager.setPage} noun="plans" />
            )}
          </Card>
        </div>

        {/* RIGHT: plan detail + inline validation */}
        <div className="min-w-0 space-y-4">
          {isLoadingDetail && <Card><LoadingState label="Loading plan…" /></Card>}

          {!isLoadingDetail && !selectedPlan && (
            <Card className="border-dashed">
              <EmptyState
                icon={Sparkles}
                title="No plan selected"
                description="Generate a new plan or pick one from the history to see its modules, checklist, tasks and quiz — and validate it."
              />
            </Card>
          )}

          {!isLoadingDetail && selectedPlan && (
            <>
              <Card>
                <CardHeader
                  title={`Plan #${selectedPlan.id}${selectedEmployee ? ` — ${selectedEmployee.full_name}` : ''}`}
                  description={
                    <>
                      Generated {new Date(selectedPlan.generated_at).toLocaleString()} with{' '}
                      <span className="text-slate-300">{selectedPlan.model_used}</span> (prompt {selectedPlan.prompt_version})
                    </>
                  }
                  actions={<StatusBadge status={selectedPlan.verification_status} />}
                />

                <div className="mt-5 grid grid-cols-3 gap-2 max-[379px]:grid-cols-1 sm:gap-3">
                  <ScoreMeter label="Coverage" value={selectedPlan.coverage_score} />
                  <ScoreMeter label="Traceability" value={selectedPlan.traceability_score} />
                  <ScoreMeter label="Consistency" value={selectedPlan.consistency_score} />
                </div>

                {(selectedPlan.source_document_versions || []).length > 0 && (
                  <div className="mt-4 flex flex-wrap items-center gap-1.5">
                    <span className="text-[12px] text-subtle">Sources:</span>
                    {selectedPlan.source_document_versions.map((d) => (
                      <Badge key={d.document_code} title={d.title}>{d.document_code} · v{d.version}</Badge>
                    ))}
                    {selectedPlan.generation_attempts > 1 && (
                      <Badge tone="warning" title="Invalid JSON was retried">{selectedPlan.generation_attempts} generation attempts</Badge>
                    )}
                  </div>
                )}

                {(selectedPlan.insufficient_information || []).length > 0 && (
                  <Alert tone="warning" className="mt-4" title="The model reported insufficient source information">
                    {selectedPlan.insufficient_information.join('; ')}
                  </Alert>
                )}
                {(selectedPlan.security_notes || []).length > 0 && (
                  <Alert tone="danger" className="mt-4" title="The model ignored instructions found in the sources">
                    {selectedPlan.security_notes.join('; ')}
                  </Alert>
                )}

                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                  <p className="text-[12.5px] text-subtle">
                    {selectedPlan.validated_at ? `Validated ${new Date(selectedPlan.validated_at).toLocaleString()}` : 'Runs Pipeline 2 (Python) on this exact plan.'}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" icon={Repeat2} onClick={() => setConsistencyOpen(true)}>Consistency check</Button>
                    <Button variant="secondary" icon={GraduationCap} loading={extraQuizBusy} onClick={handleExtraQuiz}>Practice quiz</Button>
                    <Button variant="accent" icon={ShieldCheck} loading={isValidating} onClick={handleValidate}>
                      {isValidating ? 'Running validation…' : 'Run validation'}
                    </Button>
                  </div>
                </div>
              </Card>

              {notice && <Alert tone="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

              <ValidationPanel validation={validation} />

              <ProgressPanel planId={selectedPlan.id} refreshKey={progressKey} />

              <Section title="Learning modules" icon={BookOpen} count={selectedPlan.modules?.length || 0} defaultOpen>
                {(selectedPlan.modules || []).map((m) => (
                  <div key={m.id} className="card-inset p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 text-[13.5px] font-semibold text-slate-100 text-break">
                        {m.module_code && <span className="code-tag mr-2">{m.module_code}</span>}{m.title}
                      </p>
                      {m.due_stage && <Badge>{m.due_stage}</Badge>}
                    </div>
                    <p className="mt-1.5 text-[13px] text-muted text-break">{m.purpose}</p>
                    {m.learning_objectives?.length > 0 && (
                      <ul className="mt-2.5 space-y-1">
                        {m.learning_objectives.map((o, i) => (
                          <li key={i} className="flex items-start gap-2 text-[12.5px] text-slate-300">
                            <span className="mt-[7px] size-1 shrink-0 rounded-full bg-accent/70" />
                            <span className="min-w-0 text-break">{o}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {m.learning_activities?.length > 0 && (
                      <p className="mt-2 text-[12.5px] text-muted text-break"><span className="text-subtle">Activities:</span> {m.learning_activities.join('; ')}</p>
                    )}
                    {m.completion_criteria && (
                      <p className="mt-1 text-[12.5px] text-muted text-break"><span className="text-subtle">Completion:</span> {m.completion_criteria}</p>
                    )}
                    {m.prerequisites?.length > 0 && (
                      <p className="mt-1 text-[12.5px] text-muted"><span className="text-subtle">Prerequisites:</span> {m.prerequisites.join(', ')}</p>
                    )}
                    {(m.source_document_id || m.source_section || m.source_requirement_code) && (
                      <p className="mt-2.5 text-[12px] text-subtle">
                        Source: {m.source_requirement_code ? `${m.source_requirement_code} · ` : ''}doc #{m.source_document_id ?? '—'}, section {m.source_section || '—'}
                      </p>
                    )}
                  </div>
                ))}
              </Section>

              <Section title="Checklist" icon={ListChecks} count={selectedPlan.checklist_items?.length || 0}>
                {(selectedPlan.checklist_items || []).map((c) => (
                  <div key={c.id} className="card-inset flex items-start justify-between gap-3 p-3.5">
                    <div className="min-w-0">
                      <p className="text-[13px] text-slate-100 text-break">{c.activity}</p>
                      <p className="mt-1 text-[12px] text-subtle">{c.due_stage} {c.responsible_person ? `· ${c.responsible_person}` : ''}</p>
                    </div>
                    <Badge tone={c.required ? 'warning' : 'neutral'}>{c.required ? 'Required' : 'Optional'}</Badge>
                  </div>
                ))}
              </Section>

              <Section title="Tasks" icon={ClipboardList} count={selectedPlan.tasks?.length || 0}>
                {(selectedPlan.tasks || []).map((t) => (
                  <div key={t.id} className="card-inset p-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 text-[13px] text-slate-100 text-break">{t.task_description}</p>
                      {t.task_type && <Badge tone={t.task_type === 'scenario' ? 'info' : 'neutral'}>{t.task_type}</Badge>}
                    </div>
                    {t.scenario && <p className="mt-1 text-[12.5px] italic text-muted text-break">Scenario: {t.scenario}</p>}
                    <p className="mt-1 text-[12.5px] text-muted text-break">Expected: {t.expected_outcome}</p>
                    {t.completion_criteria && <p className="mt-1 text-[12.5px] text-muted text-break">Completion: {t.completion_criteria}</p>}
                    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-subtle">
                      <span>{t.difficulty}</span><span aria-hidden="true">·</span><span>{t.due_stage}</span>
                      {t.source_requirement_code && <><span aria-hidden="true">·</span><span className="code-tag !text-[11.5px]">{t.source_requirement_code}</span></>}
                    </div>
                  </div>
                ))}
              </Section>

              <Section title="Quiz (answer key)" icon={HelpCircle} count={selectedPlan.quizzes?.length || 0}>
                {(selectedPlan.quizzes || []).map((q) => (
                  <div key={q.id} className="card-inset p-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 text-[13px] font-medium text-slate-100 text-break">{q.question_text}</p>
                      {q.question_type && <Badge>{q.question_type.replace('_', ' ')}</Badge>}
                    </div>
                    {q.options?.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {q.options.map((o, i) => (
                          <li
                            key={i}
                            className={`rounded-md px-2.5 py-1.5 text-[12.5px] text-break ${
                              (q.correct_answers?.length ? q.correct_answers.includes(o) : o === q.correct_answer) ? 'bg-emerald-500/10 text-emerald-300' : 'text-muted'
                            }`}
                          >
                            {o}
                          </li>
                        ))}
                      </ul>
                    )}
                    {q.explanation && <p className="mt-2 text-[12px] text-subtle text-break">{q.explanation}</p>}
                  </div>
                ))}
              </Section>

              <Section title="Assessments" icon={Award} count={selectedPlan.assessments?.length || 0}>
                <AssessmentList planId={selectedPlan.id} assessments={selectedPlan.assessments || []} canScore onScored={reloadSelected} />
              </Section>
            </>
          )}
        </div>
      </div>
      <ConsistencyModal employeeId={selectedEmployeeId} open={consistencyOpen} onClose={() => setConsistencyOpen(false)} />
    </div>
  );
};

export default OnboardingManager;
