import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText, Briefcase, Users, ListChecks, Plus, Sparkles, ShieldCheck, ArrowRight, UploadCloud,
  ClipboardCheck, ShieldAlert, Gauge, GraduationCap,
} from 'lucide-react';
import apiClient from '../../api/apiClient';
import {
  Alert, Button, Card, CardHeader, PageHeader, Skeleton, StatCard, StatusBadge, errorMessage, fadeUp, stagger,
} from '../ui/primitives';

/* ==========================================================================
   AnalyticsDashboard — Administrator dashboard (SRS Step 51 / li).
   Every number comes from GET /dashboard/summary (computed from the
   database); counts passed from AdminDashboard are only used while that
   request is loading.
   ========================================================================== */
const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v)}%`);

export const AnalyticsDashboard = ({ documentsCount, rolesCount, employeesCount, requirementsCount = 0, isLoading = false, onNavigate }) => {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiClient.get('/dashboard/summary').then((r) => setSummary(r.data)).catch((e) => setError(errorMessage(e, 'Could not load dashboard metrics.')));
  }, []);

  const s = summary;
  const loading = isLoading || (!s && !error);

  const stats = [
    { label: 'Employees', value: s ? s.employees : employeesCount, meta: s ? `${s.employees_with_plan} with a plan` : 'Registered', icon: Users, tab: 'employees' },
    { label: 'Onboarding plans', value: s?.plans ?? '—', meta: s ? `${s.flagged_plans} flagged by validation` : '', icon: Sparkles, tab: 'plans' },
    { label: 'Compliance coverage', value: pct(s?.compliance_coverage), meta: 'Mandatory requirements covered', icon: ClipboardCheck, tab: 'role-dashboard' },
    { label: 'Average completion', value: pct(s?.average_completion), meta: 'Latest plan per employee', icon: Gauge, tab: 'plans' },
    { label: 'Manual reviews pending', value: s?.pending_manual_reviews ?? '—', meta: 'Flagged and awaiting a reviewer', icon: ShieldCheck, tab: 'plans' },
    { label: 'Security flags', value: s ? s.security_flags_documents + s.security_flags_outputs : '—', meta: s ? `${s.security_flags_documents} in documents · ${s.security_flags_outputs} in outputs` : '', icon: ShieldAlert, tab: 'documents' },
    { label: 'Assessment scores', value: pct(s?.average_assessment_score), meta: `Quiz average ${pct(s?.average_quiz_score)}`, icon: GraduationCap, tab: 'reports' },
    { label: 'Knowledge base', value: s ? s.active_documents : documentsCount, meta: s ? `${s.obsolete_documents} obsolete · ${s.mandatory_requirements}/${s.requirements} mandatory rows` : `${requirementsCount} requirement rows`, icon: FileText, tab: 'documents' },
  ];

  const statusEntries = s ? Object.entries(s.plans_by_verification_status) : [];
  const statusTotal = statusEntries.reduce((a, [, v]) => a + v, 0);

  const steps = [
    { title: 'Upload source documents', text: 'Policies, SOPs and handbooks are extracted into traceable chunks and scanned for injected instructions.', icon: UploadCloud, tab: 'documents' },
    { title: 'Define the Requirement Matrix', text: 'Mandatory and optional requirements per role, linked to their source document.', icon: ListChecks, tab: 'requirements' },
    { title: 'Generate an onboarding plan', text: 'Pipeline 1 (GenAI) builds modules, checklist, tasks, quiz and assessments.', icon: Sparkles, tab: 'onboarding' },
    { title: 'Validate against ground truth', text: 'Pipeline 2 (Python) checks coverage, traceability, grounding, contradictions and precedence.', icon: ShieldCheck, tab: 'onboarding' },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Live metrics computed from the backend database."
        actions={<Button variant="primary" icon={Plus} onClick={() => onNavigate('documents')}>Upload document</Button>}
      />

      {error && <Alert tone="danger">{error}</Alert>}

      <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ tab, ...st }) => (
          <motion.div key={st.label} variants={fadeUp} className="min-w-0">
            {loading ? (
              <div className="card p-5">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="mt-4 h-7 w-12" />
                <Skeleton className="mt-3 h-3 w-32" />
              </div>
            ) : (
              <StatCard {...st} onClick={() => onNavigate(tab)} />
            )}
          </motion.div>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader title="Plans by verification status" description="Result of the Python validation pipeline" />
          <div className="mt-5 space-y-3">
            {statusTotal === 0 && <p className="text-[13px] text-subtle">No plans generated yet.</p>}
            {statusEntries.map(([status, count]) => (
              <div key={status}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <StatusBadge status={status} />
                  <span className="text-[13px] tabular-nums text-muted">{count}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                  <motion.div className="h-full rounded-full bg-slate-300/70" initial={{ width: 0 }}
                    animate={{ width: `${(count / statusTotal) * 100}%` }} transition={{ duration: 0.5 }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card padded={false} className="overflow-hidden">
          <div className="p-5 pb-3"><CardHeader title="Recent plans" description="Latest generated onboarding plans" /></div>
          <div className="table-wrap border-t border-line">
            <table className="table">
              <thead><tr><th>Plan</th><th>Employee</th><th className="hidden sm:table-cell">Coverage</th><th>Status</th></tr></thead>
              <tbody>
                {(s?.recent_plans || []).length === 0 && (
                  <tr><td colSpan="4" className="text-center text-subtle">No plans yet.</td></tr>
                )}
                {(s?.recent_plans || []).map((p) => (
                  <tr key={p.id} className="cursor-pointer" onClick={() => onNavigate('onboarding')}>
                    <td className="font-mono text-[12.5px]">#{p.id}</td>
                    <td className="text-slate-200">{p.employee_name || `Employee #${p.employee_id}`}</td>
                    <td className="hidden tabular-nums sm:table-cell">{pct(p.coverage_score)}</td>
                    <td><StatusBadge status={p.verification_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Dual-pipeline verification"
          description="Generative AI drafts the onboarding content; an independent Python pipeline verifies it against the Requirement Matrix before it is trusted."
        />
        <ol className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {steps.map(({ title, text, icon: Icon, tab }, i) => (
            <li key={title} className="min-w-0">
              <button type="button" onClick={() => onNavigate(tab)}
                className="card-inset group flex h-full w-full flex-col p-4 text-left transition-colors hover:border-line-strong">
                <div className="flex items-center justify-between">
                  <span className="grid size-7 place-items-center rounded-md border border-line bg-surface-3 text-slate-300"><Icon size={14} /></span>
                  <span className="text-[11.5px] font-medium tabular-nums text-subtle">Step {i + 1}</span>
                </div>
                <p className="mt-3 text-[13.5px] font-semibold text-slate-100">{title}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{text}</p>
                <span className="mt-auto flex items-center gap-1 pt-3 text-[12.5px] font-medium text-subtle transition-colors group-hover:text-accent">
                  Open <ArrowRight size={13} />
                </span>
              </button>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
};

export default AnalyticsDashboard;
