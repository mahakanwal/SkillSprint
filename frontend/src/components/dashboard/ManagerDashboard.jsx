import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Users, ChevronDown, Sparkles } from 'lucide-react';
import apiClient from '../../api/apiClient';
import { useAuth } from '../../context/AuthContext';
import { AppShell } from '../ui/AppShell';
import {
  Alert, Badge, Card, CardHeader, EmptyState, PageHeader, ScoreMeter, SearchInput, SkeletonRows, Spinner,
  StatusBadge, ease,
} from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';
import { AssessmentList, ProgressPanel } from './OnboardingManager';

/* ==========================================================================
   ManagerDashboard — read-only view of the manager's direct reports and
   each one's onboarding progress. "Direct report" is matched by
   Employee.reporting_manager == the manager's own username (that's the
   only link between the two in the current schema — there's no
   manager_id foreign key yet, so this is a name match, not a hard link).

   FIX: a report's plan used to be fetched with GET /onboarding/plan/
   {employeeId}, which expects a PLAN id. It now lists that employee's plans
   (GET /onboarding/employee/{id}) and opens the newest one. Scores are
   already 0–100, so the old "* 100" (e.g. 10000%) is removed.
   ========================================================================== */
export const ManagerDashboard = ({ onLogout }) => {
  const { user } = useAuth();

  const [allEmployees, setAllEmployees] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [plans, setPlans] = useState({}); // employee_id -> plan | 'loading' | 'none' | 'error'
  const [searchQuery, setSearchQuery] = useState('');
  const [progressKeys, setProgressKeys] = useState({}); // plan_id -> refresh counter

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get('/employees/');
      setAllEmployees(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load employees. Check backend server.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const myTeam = useMemo(() => {
    if (!user?.username) return [];
    return allEmployees.filter(
      (e) => (e.reporting_manager || '').trim().toLowerCase() === user.username.trim().toLowerCase()
    );
  }, [allEmployees, user]);

  const filteredTeam = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return myTeam.filter(
      (e) =>
        (e.full_name || '').toLowerCase().includes(q) ||
        (e.employee_code || '').toLowerCase().includes(q) ||
        (e.department || '').toLowerCase().includes(q)
    );
  }, [myTeam, searchQuery]);

  const pager = usePagination(filteredTeam, { pageSize: 8, resetKey: searchQuery });

  const toggleExpand = async (employeeId) => {
    if (expandedId === employeeId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(employeeId);
    if (plans[employeeId]) return; // already fetched

    setPlans((prev) => ({ ...prev, [employeeId]: 'loading' }));
    try {
      const list = await apiClient.get(`/onboarding/employee/${employeeId}`);
      const latest = Array.isArray(list.data) ? list.data[0] : null;
      if (!latest) {
        setPlans((prev) => ({ ...prev, [employeeId]: 'none' }));
        return;
      }
      const res = await apiClient.get(`/onboarding/plan/${latest.id}`);
      setPlans((prev) => ({ ...prev, [employeeId]: res.data }));
    } catch (err) {
      setPlans((prev) => ({ ...prev, [employeeId]: err.response?.status === 404 ? 'none' : 'error' }));
    }
  };

  return (
    <AppShell
      portalLabel="Manager Portal"
      navGroups={[{ label: 'Team', items: [{ key: 'team', label: 'My team', icon: Users, badge: isLoading ? undefined : myTeam.length }] }]}
      activeKey="team"
      onNavigate={() => {}}
      onLogout={onLogout}
      pageTitle="My team"
    >
      <PageHeader
        title="My team"
        description={`Onboarding progress for employees reporting to ${user?.username || 'you'}.`}
      />

      {error && <Alert tone="danger" className="mb-6" onDismiss={() => setError(null)}>{error}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <CardHeader icon={Users} title="Direct reports" description={isLoading ? 'Loading…' : `${myTeam.length} people`} />
          {myTeam.length > 0 && (
            <SearchInput
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search name, code, department"
              className="w-full sm:w-64"
            />
          )}
        </div>

        <div className="border-t border-line">
          {isLoading && <SkeletonRows rows={4} />}

          {!isLoading && !error && myTeam.length === 0 && (
            <EmptyState
              icon={Users}
              title="No employees are reporting to you yet"
              description={`This matches the "Reporting Manager" field on each employee record — ask an admin to set it to "${user?.username}" for your team.`}
            />
          )}

          {!isLoading && myTeam.length > 0 && filteredTeam.length === 0 && (
            <EmptyState icon={Users} title="No matching employees" description="Try a different search term." />
          )}

          <ul className="divide-y divide-line">
            {pager.pageItems.map((emp) => {
              const planState = plans[emp.id];
              const isExpanded = expandedId === emp.id;
              return (
                <li key={emp.id}>
                  <button
                    type="button"
                    onClick={() => toggleExpand(emp.id)}
                    aria-expanded={isExpanded}
                    className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-white/[0.02]"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-medium text-slate-100">{emp.full_name}</p>
                      <p className="mt-0.5 truncate text-[12.5px] text-subtle">
                        <span className="font-mono">{emp.employee_code}</span> · {emp.department || 'No department'}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      {emp.training_status && <Badge className="hidden sm:inline-flex">{emp.training_status}</Badge>}
                      <motion.span animate={{ rotate: isExpanded ? 180 : 0 }} transition={{ duration: 0.2, ease }} className="text-subtle">
                        <ChevronDown size={16} />
                      </motion.span>
                    </div>
                  </button>

                  <AnimatePresence initial={false}>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.22, ease }}
                        className="overflow-hidden"
                      >
                        <div className="px-5 pb-5">
                          {planState === 'loading' && (
                            <div className="flex items-center gap-2 text-[13px] text-subtle"><Spinner size={14} /> Loading plan…</div>
                          )}
                          {planState === 'none' && (
                            <div className="flex items-center gap-2 text-[13px] text-subtle">
                              <Sparkles size={14} /> No onboarding plan generated yet for this employee.
                            </div>
                          )}
                          {planState === 'error' && (
                            <p className="text-[13px] text-rose-300">Could not load this employee&apos;s plan.</p>
                          )}
                          {planState && typeof planState === 'object' && (
                            <div className="space-y-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-[12.5px] text-subtle">
                                  Plan #{planState.id}
                                  {planState.progress_percent !== undefined && ` · ${planState.progress_percent}% complete`}
                                </span>
                                <StatusBadge status={planState.verification_status} />
                              </div>
                              <div className="grid grid-cols-3 gap-2 max-[379px]:grid-cols-1 sm:gap-3">
                                <ScoreMeter label="Coverage" value={planState.coverage_score} />
                                <ScoreMeter label="Traceability" value={planState.traceability_score} />
                                <ScoreMeter label="Consistency" value={planState.consistency_score} />
                              </div>
                              {/* Progress outcome, weak areas and recommendations (SRS 53-56) */}
                              <ProgressPanel planId={planState.id} refreshKey={progressKeys[planState.id] || 0} />
                              {planState.assessments?.length > 0 && (
                                <AssessmentList
                                  planId={planState.id}
                                  assessments={planState.assessments}
                                  canScore
                                  onScored={() => setProgressKeys((k) => ({ ...k, [planState.id]: (k[planState.id] || 0) + 1 }))}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </li>
              );
            })}
          </ul>
        </div>

        <Pagination {...pager} onPageChange={pager.setPage} noun="people" />
      </Card>
    </AppShell>
  );
};

export default ManagerDashboard;
