import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, SlidersHorizontal, Layers, RotateCcw } from 'lucide-react';
import apiClient from '../../api/apiClient';
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, PageHeader, SkeletonRows, StatusBadge, Tabs, errorMessage,
} from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';

/* ==========================================================================
   PlansExplorer — Search & filtering (SRS Step 61 / lx) and Training Plan
   Comparison (SRS Step 60). Filters are sent to GET /dashboard/plans;
   comparison groups come from GET /dashboard/compare.
   ========================================================================== */
const STATUSES = ['Verified', 'Verified with Warning', 'Partially Verified', 'Incomplete', 'Unsupported', 'Contradictory', 'Manual Review Required'];
const REVIEW = ['Pending Review', 'Approved', 'Rejected', 'Needs Regeneration'];
const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v)}%`);
const EMPTY = { search: '', role_id: '', department: '', status: '', review_status: '', experience_level: '', module: '', policy: '', min_progress: '' };

export const PlansExplorer = ({ roles = [], onOpenPlan }) => {
  const [tab, setTab] = useState('search');
  const [filters, setFilters] = useState(EMPTY);
  const [applied, setApplied] = useState(EMPTY);
  const [rows, setRows] = useState(null);
  const [groupBy, setGroupBy] = useState('role');
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRows(null);
    const params = Object.fromEntries(Object.entries(applied).filter(([, v]) => v !== ''));
    apiClient.get('/dashboard/plans', { params }).then((r) => setRows(r.data)).catch((e) => setError(errorMessage(e, 'Could not load plans.')));
  }, [applied]);

  useEffect(() => {
    if (tab !== 'compare') return;
    setGroups(null);
    apiClient.get('/dashboard/compare', { params: { group_by: groupBy } }).then((r) => setGroups(r.data)).catch((e) => setError(errorMessage(e, 'Could not compare plans.')));
  }, [tab, groupBy]);

  const departments = useMemo(() => [...new Set((rows || []).map((r) => r.department).filter(Boolean))], [rows]);
  const pager = usePagination(rows || [], { pageSize: 10, resetKey: JSON.stringify(applied) });
  const activeCount = Object.values(applied).filter((v) => v !== '').length;
  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <PageHeader title="Plans" description="Search, filter and compare the latest onboarding plan of every employee." />
      {error && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}
      <Tabs layoutId="plans-tabs" active={tab} onChange={setTab} className="w-full sm:w-fit"
        tabs={[{ key: 'search', label: 'Search & filter', icon: Search }, { key: 'compare', label: 'Compare', icon: Layers }]} />

      {tab === 'search' && (
        <>
          <Card>
            <CardHeader icon={SlidersHorizontal} title="Filters" description={activeCount ? `${activeCount} filter(s) active` : 'No filters applied'} />
            <form className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
              onSubmit={(e) => { e.preventDefault(); setApplied(filters); }}>
              <Field label="Employee" htmlFor="f-search"><input id="f-search" className="input" placeholder="Name or code" value={filters.search} onChange={set('search')} /></Field>
              <Field label="Role" htmlFor="f-role">
                <select id="f-role" className="select" value={filters.role_id} onChange={set('role_id')}>
                  <option value="">All roles</option>{roles.map((r) => <option key={r.id} value={r.id}>{r.role_name}</option>)}
                </select>
              </Field>
              <Field label="Department" htmlFor="f-dept">
                <select id="f-dept" className="select" value={filters.department} onChange={set('department')}>
                  <option value="">All departments</option>{departments.map((d) => <option key={d}>{d}</option>)}
                </select>
              </Field>
              <Field label="Verification result" htmlFor="f-status">
                <select id="f-status" className="select" value={filters.status} onChange={set('status')}>
                  <option value="">Any result</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="Review status" htmlFor="f-review">
                <select id="f-review" className="select" value={filters.review_status} onChange={set('review_status')}>
                  <option value="">Any</option>{REVIEW.map((s) => <option key={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="Module" htmlFor="f-module"><input id="f-module" className="input" placeholder="Module title contains" value={filters.module} onChange={set('module')} /></Field>
              <Field label="Policy / document" htmlFor="f-policy"><input id="f-policy" className="input" placeholder="e.g. SOP-07" value={filters.policy} onChange={set('policy')} /></Field>
              <Field label="Minimum progress %" htmlFor="f-prog"><input id="f-prog" type="number" min="0" max="100" className="input" value={filters.min_progress} onChange={set('min_progress')} /></Field>
              <div className="flex flex-wrap justify-end gap-2 sm:col-span-2 xl:col-span-4">
                <Button variant="ghost" icon={RotateCcw} onClick={() => { setFilters(EMPTY); setApplied(EMPTY); }} disabled={!activeCount}>Reset</Button>
                <Button type="submit" variant="primary" icon={Search}>Apply filters</Button>
              </div>
            </form>
          </Card>

          <Card padded={false} className="overflow-hidden">
            {!rows && <SkeletonRows rows={5} />}
            {rows && rows.length === 0 && <EmptyState icon={Search} title="No plans match these filters" />}
            {rows && rows.length > 0 && (
              <>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Employee</th><th className="hidden md:table-cell">Role</th><th>Result</th>
                        <th className="hidden lg:table-cell">Coverage</th><th className="hidden lg:table-cell">Trace</th>
                        <th>Progress</th><th className="hidden xl:table-cell">Sources</th>
                      </tr>
                    </thead>
                    <motion.tbody key={pager.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                      {pager.pageItems.map((r) => (
                        <tr key={r.plan_id} className={onOpenPlan ? 'cursor-pointer' : ''} onClick={() => onOpenPlan?.(r)}>
                          <td className="min-w-[160px]">
                            <p className="font-medium text-slate-100">{r.employee_name}</p>
                            <p className="text-[12px] text-subtle">{r.employee_code} · plan #{r.plan_id}</p>
                          </td>
                          <td className="hidden md:table-cell">{r.role_name}<p className="text-[12px] text-subtle">{r.department} · {r.experience_level}</p></td>
                          <td><StatusBadge status={r.verification_status} /><p className="mt-1 text-[12px] text-subtle">{r.review_status}</p></td>
                          <td className="hidden tabular-nums lg:table-cell">{pct(r.coverage_score)}</td>
                          <td className="hidden tabular-nums lg:table-cell">{pct(r.traceability_score)}</td>
                          <td className="tabular-nums">{pct(r.progress_percent)}</td>
                          <td className="hidden max-w-[220px] xl:table-cell">
                            <div className="flex flex-wrap gap-1">{r.document_versions.map((d) => <Badge key={d}>{d}</Badge>)}</div>
                          </td>
                        </tr>
                      ))}
                    </motion.tbody>
                  </table>
                </div>
                <Pagination {...pager} onPageChange={pager.setPage} noun="plans" />
              </>
            )}
          </Card>
        </>
      )}

      {tab === 'compare' && (
        <Card padded={false} className="overflow-hidden">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <CardHeader icon={Layers} title="Training plan comparison" description="Which requirements every plan in a group shares, and which only some plans include." />
            <select aria-label="Group plans by" className="select !h-9 sm:w-56" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
              <option value="role">By role</option>
              <option value="department">By department</option>
              <option value="experience_level">By experience level</option>
              <option value="document_version">By document version</option>
            </select>
          </div>
          {!groups && <SkeletonRows rows={4} />}
          {groups && groups.length === 0 && <EmptyState icon={Layers} title="No plans to compare yet" />}
          {groups && groups.length > 0 && (
            <div className="table-wrap border-t border-line">
              <table className="table">
                <thead>
                  <tr><th>Group</th><th>Plans</th><th className="hidden md:table-cell">Avg modules</th><th>Coverage</th><th className="hidden md:table-cell">Progress</th><th>Requirements</th></tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={g.group} className="align-top">
                      <td className="min-w-[150px] font-medium text-slate-100">{g.group}<p className="text-[12px] font-normal text-subtle">{g.employees.join(', ')}</p></td>
                      <td className="tabular-nums">{g.plans}</td>
                      <td className="hidden tabular-nums md:table-cell">{g.average_modules ?? '—'}</td>
                      <td className="tabular-nums">{pct(g.average_coverage)}</td>
                      <td className="hidden tabular-nums md:table-cell">{pct(g.average_progress)}</td>
                      <td className="min-w-[220px]">
                        <div className="flex flex-wrap gap-1">
                          {g.requirements_in_every_plan.map((c) => <Badge key={c} tone="success">{c}</Badge>)}
                          {g.requirements_in_some_plans.map((c) => <Badge key={c} tone="warning" title="Only in some plans">{c}</Badge>)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default PlansExplorer;
