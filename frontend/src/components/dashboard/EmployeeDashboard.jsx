import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen, ListTodo, ClipboardCheck, HelpCircle, CheckCircle2, Circle, Sparkles, Link2,
  RefreshCw, XCircle, RotateCcw, Eye, Award, Gauge,
} from 'lucide-react';
import { AssessmentList, ProgressPanel } from './OnboardingManager';
import apiClient from '../../api/apiClient';
import { useAuth } from '../../context/AuthContext';
import { AppShell } from '../ui/AppShell';
import {
  Alert, Badge, Button, Card, EmptyState, LoadingState, PageHeader, ScoreMeter, StatusBadge, Tabs, ease, fadeUp, stagger,
} from '../ui/primitives';

/* ==========================================================================
   EmployeeDashboard — the logged-in employee's OWN onboarding plan.
   employeeId comes from the JWT (see AuthContext), so an employee can only
   ever see their own data.

   FIX: this screen used to call GET /onboarding/plan/{employeeId}, but
   that endpoint takes a PLAN id — so an employee could be shown a plan
   that belongs to someone else (whatever plan happened to share their
   employee id number). It now lists the employee's own plans via
   GET /onboarding/employee/{employeeId} and opens the newest one.

   FIX: scores are already 0–100 from the backend; the old "* 100" showed
   values like 10000%.

   FIX: the quiz used to highlight the correct answer before the employee
   answered. It is now interactive: pick an option, then see the result.
   ========================================================================== */

const MarkButton = ({ done, busy, onClick, doneLabel = 'Completed' }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={busy}
    aria-pressed={done}
    className={`btn btn-sm shrink-0 ${done ? 'btn-success' : 'btn-secondary'}`}
  >
    {busy ? <RefreshCw size={13} className="animate-spin" /> : done ? <CheckCircle2 size={13} /> : <Circle size={13} />}
    <span>{done ? doneLabel : 'Mark done'}</span>
  </button>
);

const correctList = (q) => (q.correct_answers?.length ? q.correct_answers : q.correct_answer ? [q.correct_answer] : []);

const QuizQuestion = ({ q, index, result, onSubmit, busy, revealed, onReveal }) => {
  const hasOptions = q.options?.length > 0;
  const multi = q.question_type === 'multiple_response';
  const [picked, setPicked] = useState([]);
  const answered = !!result;
  const isCorrect = answered && result.is_correct;
  const correct = correctList(q);
  const chosenSet = new Set(result?.selected || []);

  const choose = (opt) => {
    if (answered || busy) return;
    if (multi) setPicked((p) => (p.includes(opt) ? p.filter((x) => x !== opt) : [...p, opt]));
    else onSubmit([opt]);
  };

  return (
    <div className="card-inset p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-[14px] font-medium leading-relaxed text-slate-100 text-break">
          <span className="mr-2 text-subtle tabular-nums">{index + 1}.</span>{q.question_text}
        </p>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {q.question_type && <Badge>{q.question_type.replace('_', ' ')}</Badge>}
          {answered && <Badge tone={isCorrect ? 'success' : 'danger'} dot>{isCorrect ? 'Correct' : 'Incorrect'}</Badge>}
        </div>
      </div>
      {multi && !answered && <p className="mt-1 text-[12px] text-subtle">Select every correct answer, then submit.</p>}

      {hasOptions ? (
        <ul className="mt-3 space-y-2" role={multi ? 'group' : 'radiogroup'} aria-label={`Question ${index + 1}`}>
          {q.options.map((opt, i) => {
            const selectedNow = multi ? picked.includes(opt) : false;
            const showCorrect = answered && correct.includes(opt);
            const showWrong = answered && chosenSet.has(opt) && !correct.includes(opt);
            return (
              <li key={i}>
                <button
                  type="button"
                  role={multi ? 'checkbox' : 'radio'}
                  aria-checked={answered ? chosenSet.has(opt) : selectedNow}
                  disabled={answered || busy}
                  onClick={() => choose(opt)}
                  className={`flex w-full items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left text-[13.5px] transition-colors ${
                    showCorrect
                      ? 'border-emerald-400/30 bg-emerald-500/[0.08] text-emerald-200'
                      : showWrong
                      ? 'border-rose-400/30 bg-rose-500/[0.08] text-rose-200'
                      : answered
                      ? 'border-line text-subtle'
                      : selectedNow
                      ? 'border-accent/40 bg-accent/[0.06] text-slate-100'
                      : 'border-line text-slate-200 hover:border-line-strong hover:bg-white/[0.03]'
                  } disabled:cursor-default`}
                >
                  <span className="mt-0.5 shrink-0">
                    {showCorrect ? <CheckCircle2 size={15} /> : showWrong ? <XCircle size={15} /> : selectedNow ? <CheckCircle2 size={15} className="text-accent" /> : <Circle size={15} className="text-subtle" />}
                  </span>
                  <span className="min-w-0 text-break">{opt}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="mt-3">
          {revealed ? (
            <p className="rounded-lg border border-emerald-400/25 bg-emerald-500/[0.07] px-3 py-2 text-[13.5px] text-emerald-200 text-break">
              {correct.join('; ') || 'No answer provided.'}
            </p>
          ) : (
            <Button size="sm" variant="secondary" icon={Eye} onClick={onReveal}>Show answer</Button>
          )}
        </div>
      )}

      {multi && !answered && hasOptions && (
        <div className="mt-3 flex justify-end">
          <Button size="sm" variant="primary" loading={busy} disabled={picked.length === 0} onClick={() => onSubmit(picked)}>Submit answer</Button>
        </div>
      )}

      {(answered || revealed) && q.explanation && (
        <motion.p
          initial={{ opacity: 0, y: -2 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease }}
          className="mt-3 text-[13px] leading-relaxed text-muted text-break"
        >
          {q.explanation}
        </motion.p>
      )}
    </div>
  );
};

export const EmployeeDashboard = ({ onLogout }) => {
  const { user, employeeId } = useAuth();

  const [plan, setPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSection, setActiveSection] = useState('modules');

  const loadPlan = useCallback(async () => {
    if (!employeeId) {
      setIsLoading(false);
      setError('Your login is not linked to an employee record yet. Contact your admin.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      // The employee's own plans, newest first — then open the latest one.
      const list = await apiClient.get(`/onboarding/employee/${employeeId}`);
      const latest = Array.isArray(list.data) ? list.data[0] : null;
      if (!latest) {
        setPlan(null); // no plan generated yet -- not an error state
        return;
      }
      const res = await apiClient.get(`/onboarding/plan/${latest.id}`);
      setPlan(res.data);
    } catch (err) {
      if (err.response?.status === 404) {
        setPlan(null);
      } else {
        setError(err.response?.data?.detail || 'Could not load your onboarding plan.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [employeeId]);

  useEffect(() => { loadPlan(); }, [loadPlan]);

  // item_id currently being PATCHed, so its toggle can show a spinner and
  // not be double-clicked while the request is in flight.
  const [updatingId, setUpdatingId] = useState(null);

  const toggleComplete = async (itemType, item) => {
    if (!plan) return;
    const nextStatus = item.completion_status === 'Completed'
      ? (itemType === 'module' ? 'Not Started' : 'Pending')
      : 'Completed';

    setUpdatingId(item.id);
    try {
      const res = await apiClient.patch(
        `/onboarding/plan/${plan.id}/progress/${itemType}/${item.id}`,
        { completion_status: nextStatus }
      );
      setPlan(res.data);
      setProgressKey((k) => k + 1);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update progress.');
    } finally {
      setUpdatingId(null);
    }
  };

  // Quiz answers are submitted to the backend (POST /onboarding/plan/{id}/quiz/submit),
  // so scores count towards progress, weak areas and reports (SRS 50, 53, 56).
  const [results, setResults] = useState({});
  const [revealed, setRevealed] = useState({});
  const [quizBusy, setQuizBusy] = useState(null);
  const [progressKey, setProgressKey] = useState(0);
  useEffect(() => {
    setResults({}); setRevealed({});
    if (!plan?.id) return;
    apiClient.get(`/onboarding/plan/${plan.id}/quiz/results`)
      .then((r) => setResults(r.data.latest || {}))
      .catch(() => setResults({}));
  }, [plan?.id]);

  const submitAnswer = async (q, selected) => {
    setQuizBusy(q.id);
    try {
      const r = await apiClient.post(`/onboarding/plan/${plan.id}/quiz/submit`, { answers: [{ question_id: q.id, selected }] });
      const res = r.data.results[0];
      setResults((prev) => ({ ...prev, [q.id]: { selected: res.selected, is_correct: res.is_correct } }));
      setProgressKey((k) => k + 1);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not submit your answer.');
    } finally {
      setQuizBusy(null);
    }
  };

  // Different backend versions have used slightly different key names for
  // these lists (checklist vs checklist_items, quiz vs quizzes) -- read
  // both so this screen keeps working regardless of which is live.
  const modules = plan?.modules || [];
  const checklist = plan?.checklist_items || plan?.checklist || [];
  const tasks = plan?.tasks || [];
  const quiz = plan?.quizzes || plan?.quiz || [];

  const answeredCount = quiz.filter((q) => results[q.id]).length;
  const correctCount = quiz.filter((q) => results[q.id]?.is_correct).length;
  const assessments = plan?.assessments || [];

  const sections = [
    { key: 'modules', label: 'Learning modules', icon: BookOpen, badge: plan ? modules.length : undefined },
    { key: 'checklist', label: 'Checklist', icon: ClipboardCheck, badge: plan ? checklist.length : undefined },
    { key: 'tasks', label: 'Tasks', icon: ListTodo, badge: plan ? tasks.length : undefined },
    { key: 'quiz', label: 'Quiz', icon: HelpCircle, badge: plan ? quiz.length : undefined },
    { key: 'assessments', label: 'Assessments', icon: Award, badge: plan ? assessments.length : undefined },
    { key: 'progress', label: 'My progress', icon: Gauge },
  ];
  const activeLabel = sections.find((s) => s.key === activeSection)?.label || '';

  const doneClass = (done) => (done ? 'border-emerald-400/20 bg-emerald-500/[0.04]' : '');

  return (
    <AppShell
      portalLabel="My Onboarding"
      navGroups={[{ label: 'My plan', items: sections }]}
      activeKey={activeSection}
      onNavigate={setActiveSection}
      onLogout={onLogout}
      pageTitle={activeLabel}
      headerRight={plan ? <StatusBadge status={plan.verification_status} /> : null}
    >
      <PageHeader
        title={`Welcome, ${user?.username || 'there'}`}
        description="Your personalized onboarding plan."
      />

      {isLoading && <Card><LoadingState label="Loading your plan…" /></Card>}

      {error && <Alert tone="danger" className="mb-6" onDismiss={() => setError(null)}>{error}</Alert>}

      {!isLoading && !error && !plan && (
        <Card className="border-dashed">
          <EmptyState
            icon={Sparkles}
            title="No onboarding plan yet"
            description="Ask your Training Manager or Admin to generate one for you."
          />
        </Card>
      )}

      {plan && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
          <motion.div variants={fadeUp} className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,2fr)]">
            <Card>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[13px] font-medium text-muted">Your progress</p>
                <p className="text-[13px] tabular-nums text-slate-300">
                  {plan.completed_items ?? 0} / {plan.total_items ?? 0} done
                </p>
              </div>
              <p className="mt-3 text-[32px] font-semibold leading-none tracking-tight tabular-nums">{plan.progress_percent ?? 0}%</p>
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/5">
                <motion.div
                  className="h-full rounded-full bg-accent"
                  initial={{ width: 0 }}
                  animate={{ width: `${plan.progress_percent ?? 0}%` }}
                  transition={{ duration: 0.6, ease }}
                />
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] font-medium text-muted">Plan verification</p>
                <StatusBadge status={plan.verification_status} />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 max-[379px]:grid-cols-1 sm:gap-3">
                <ScoreMeter label="Coverage" value={plan.coverage_score} />
                <ScoreMeter label="Traceability" value={plan.traceability_score} />
                <ScoreMeter label="Consistency" value={plan.consistency_score} />
              </div>
            </Card>
          </motion.div>

          <motion.div variants={fadeUp}>
            <Card padded={false} className="overflow-hidden">
              <div className="border-b border-line px-3 pt-3 lg:hidden">
                <Tabs
                  tabs={sections.map(({ key, label, badge }) => ({ key, label: label.replace('Learning modules', 'Modules'), count: badge }))}
                  active={activeSection}
                  onChange={setActiveSection}
                  layoutId="employee-tabs"
                  className="mb-3 max-[379px]:grid max-[379px]:grid-cols-2"
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
                <h2 className="text-[15px] font-semibold text-fg">{activeLabel}</h2>
                {activeSection === 'quiz' && quiz.length > 0 && (
                  <div className="flex items-center gap-3">
                    <span className="text-[13px] tabular-nums text-muted">
                      {correctCount} / {answeredCount} correct · {answeredCount} of {quiz.length} answered
                    </span>
                    {answeredCount > 0 && (
                      <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => { setResults({}); setRevealed({}); }}>
                        Retake
                      </Button>
                    )}
                  </div>
                )}
              </div>

              <motion.div
                key={activeSection}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease }}
                className="space-y-3 p-4 sm:p-5"
              >
                {activeSection === 'modules' && (
                  <>
                    {modules.length === 0 && <EmptyState icon={BookOpen} title="No modules yet" />}
                    {modules.map((m, idx) => {
                      const done = m.completion_status === 'Completed';
                      return (
                        <div key={m.id || idx} className={`card-inset p-4 sm:p-5 ${doneClass(done)}`}>
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="text-[14.5px] font-semibold text-slate-100 text-break">
                                {m.module_code && <span className="code-tag mr-2">{m.module_code}</span>}{m.title}
                              </h3>
                              <p className="mt-1 text-[12.5px] text-subtle">
                                {m.due_stage} {m.estimated_duration && `· ${m.estimated_duration}`}
                              </p>
                            </div>
                            <MarkButton done={done} busy={updatingId === m.id} onClick={() => toggleComplete('module', m)} />
                          </div>
                          <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted text-break">{m.purpose}</p>
                          {m.learning_objectives?.length > 0 && (
                            <ul className="mt-3 space-y-1.5">
                              {m.learning_objectives.map((obj, i) => (
                                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                                  <span className="mt-[8px] size-1 shrink-0 rounded-full bg-accent/70" />
                                  <span className="min-w-0 text-break">{obj}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })}
                  </>
                )}

                {activeSection === 'checklist' && (
                  <>
                    {checklist.length === 0 && <EmptyState icon={ClipboardCheck} title="No checklist items yet" />}
                    {checklist.map((c, idx) => {
                      const done = c.completion_status === 'Completed';
                      return (
                        <div key={c.id || idx} className={`card-inset flex items-start gap-3 p-3.5 ${doneClass(done)}`}>
                          <button
                            type="button"
                            onClick={() => toggleComplete('checklist', c)}
                            disabled={updatingId === c.id}
                            aria-pressed={done}
                            aria-label={done ? 'Mark as not done' : 'Mark as done'}
                            className="mt-0.5 shrink-0 rounded-md"
                          >
                            {updatingId === c.id
                              ? <RefreshCw size={17} className="animate-spin text-subtle" />
                              : done
                                ? <CheckCircle2 size={17} className="text-emerald-400" />
                                : <Circle size={17} className="text-slate-500 hover:text-accent" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <p className={`text-[13.5px] text-break ${done ? 'text-subtle line-through' : 'text-slate-100'}`}>{c.activity}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-subtle">
                              {c.due_stage && <span>{c.due_stage}</span>}
                              {c.responsible_person && <span>· {c.responsible_person}</span>}
                              {c.required && <Badge tone="warning">Required</Badge>}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </>
                )}

                {activeSection === 'tasks' && (
                  <>
                    {tasks.length === 0 && <EmptyState icon={ListTodo} title="No tasks yet" />}
                    {tasks.map((t, idx) => {
                      const done = t.completion_status === 'Completed';
                      return (
                        <div key={t.id || idx} className={`card-inset p-4 ${doneClass(done)}`}>
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <p className={`min-w-0 flex-1 text-[13.5px] font-medium text-break ${done ? 'text-subtle line-through' : 'text-slate-100'}`}>{t.task_description}</p>
                            <MarkButton done={done} busy={updatingId === t.id} onClick={() => toggleComplete('task', t)} doneLabel="Done" />
                          </div>
                          <p className="mt-2 text-[13px] text-muted text-break">Expected outcome: {t.expected_outcome}</p>
                          <p className="mt-1.5 text-[12px] text-subtle">{t.difficulty} · {t.due_stage}</p>
                        </div>
                      );
                    })}
                  </>
                )}

                {activeSection === 'quiz' && (
                  <>
                    {quiz.length === 0 && <EmptyState icon={HelpCircle} title="No quiz questions yet" />}
                    {quiz.map((q, idx) => (
                      <QuizQuestion
                        key={q.id ?? idx}
                        q={q}
                        index={idx}
                        result={results[q.id]}
                        busy={quizBusy === q.id}
                        onSubmit={(selected) => submitAnswer(q, selected)}
                        revealed={!!revealed[q.id]}
                        onReveal={() => setRevealed((prev) => ({ ...prev, [q.id]: true }))}
                      />
                    ))}
                  </>
                )}

                {activeSection === 'assessments' && (
                  assessments.length === 0
                    ? <EmptyState icon={Award} title="No assessments yet" />
                    : <AssessmentList planId={plan.id} assessments={assessments} canScore={false} />
                )}

                {activeSection === 'progress' && <ProgressPanel planId={plan.id} refreshKey={progressKey} />}
              </motion.div>
            </Card>
          </motion.div>

          {plan.model_used && (
            <p className="flex items-center gap-1.5 text-[12px] text-subtle">
              <Link2 size={12} />
              <span>Generated by {plan.model_used} on {plan.generated_at ? new Date(plan.generated_at).toLocaleString() : 'n/a'}</span>
            </p>
          )}
        </motion.div>
      )}
    </AppShell>
  );
};

export default EmployeeDashboard;
