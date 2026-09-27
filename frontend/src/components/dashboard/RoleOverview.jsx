import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Briefcase, ChevronDown } from 'lucide-react';
import apiClient from '../../api/apiClient';
import { Alert, Badge, Card, EmptyState, PageHeader, SkeletonRows, ease, errorMessage } from '../ui/primitives';

/* ==========================================================================
   RoleOverview — Role dashboard (SRS Step 52 / lii): onboarding
   requirements and completion statistics per job role, from
   GET /dashboard/roles.
   ========================================================================== */
const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v)}%`);

export const RoleOverview = () => {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    apiClient.get('/dashboard/roles').then((r) => setRows(r.data)).catch((e) => setError(errorMessage(e, 'Could not load role statistics.')));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="Role dashboard" description="Onboarding requirements and completion statistics for every job role." />
      {error && <Alert tone="danger">{error}</Alert>}
      <Card padded={false} className="overflow-hidden">
        {!rows && !error && <SkeletonRows rows={5} />}
        {rows && rows.length === 0 && <EmptyState icon={Briefcase} title="No roles yet" />}
        {rows && rows.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Requirements</th>
                  <th className="hidden md:table-cell">Employees</th>
                  <th className="hidden lg:table-cell">Coverage</th>
                  <th>Completion</th>
                  <th className="hidden md:table-cell">Plans</th>
                  <th className="w-10"><span className="sr-only">Expand</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const expanded = open === r.role_id;
                  return (
                    <React.Fragment key={r.role_id}>
                      <tr className="cursor-pointer" onClick={() => setOpen(expanded ? null : r.role_id)}>
                        <td className="min-w-[180px]">
                          <p className="font-medium text-slate-100">{r.role_name}</p>
                          <p className="text-[12px] text-subtle">{r.department}</p>
                        </td>
                        <td>
                          <p className="tabular-nums text-slate-200">{r.mandatory_requirements} mandatory</p>
                          <p className="text-[12px] text-subtle">{r.optional_requirements} optional · {r.source_documents} source docs</p>
                        </td>
                        <td className="hidden tabular-nums md:table-cell">
                          {r.employees_with_plan}/{r.employees} with plan
                          <p className="text-[12px] text-subtle">{r.completed_employees} completed</p>
                        </td>
                        <td className="hidden tabular-nums lg:table-cell">{pct(r.average_coverage)}</td>
                        <td className="tabular-nums">{pct(r.average_completion)}</td>
                        <td className="hidden md:table-cell">
                          <div className="flex flex-wrap gap-1">
                            {r.verified_plans > 0 && <Badge tone="success">{r.verified_plans} verified</Badge>}
                            {r.flagged_plans > 0 && <Badge tone="warning">{r.flagged_plans} flagged</Badge>}
                            {r.requirements_without_source > 0 && <Badge tone="danger">{r.requirements_without_source} unsourced</Badge>}
                          </div>
                        </td>
                        <td>
                          <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2, ease }} className="inline-block text-subtle">
                            <ChevronDown size={15} />
                          </motion.span>
                        </td>
                      </tr>
                      <AnimatePresence initial={false}>
                        {expanded && (
                          <tr>
                            <td colSpan="7" className="!bg-surface-2/60 !p-0">
                              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.2, ease }} className="overflow-hidden">
                                <div className="flex flex-wrap gap-2 p-4">
                                  {r.requirement_list.length === 0 && <span className="text-[13px] text-subtle">No requirements defined.</span>}
                                  {r.requirement_list.map((q) => (
                                    <Badge key={q.code} tone={q.mandatory ? 'warning' : 'neutral'} title={q.competency || ''}>
                                      {q.code} · {q.due_stage || 'no stage'}
                                    </Badge>
                                  ))}
                                </div>
                              </motion.div>
                            </td>
                          </tr>
                        )}
                      </AnimatePresence>
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

export default RoleOverview;
