import React, { useEffect, useMemo, useState } from 'react';
import {
  FileText, ListChecks, ShieldAlert, UploadCloud, GitCompare, RefreshCw, Link2, Plus, Check,
} from 'lucide-react';
import apiClient from '../../../api/apiClient';
import { Modal } from '../../ui/Modal';
import {
  Alert, Badge, Button, EmptyState, Field, LoadingState, StatusBadge, Tabs, errorMessage,
} from '../../ui/primitives';

/* ==========================================================================
   Document modals (SRS Steps 6-8, 11, 42-43, 57-59)
     DocumentDetailModal  chunks, extracted requirements, security flags
     NewVersionModal      POST /documents/upload-version/{family}
     ImpactModal          GET  /documents/impact/{id} + relink + selective
                          regeneration of affected plans
   ========================================================================== */

const DOC_TYPES = ['Policy', 'SOP', 'FAQ', 'Handbook', 'Guideline', 'Manual', 'Form', 'Role Description', 'Compliance', 'Informal'];
const DEPARTMENTS = ['All', 'HR', 'Engineering', 'Finance', 'IT', 'Customer Support', 'Sales', 'Marketing', 'Operations'];

export { DOC_TYPES, DEPARTMENTS };

const classTone = (c) => (c?.startsWith('Must') ? 'warning' : c === 'Not Applicable' ? 'neutral' : 'info');

/* --------------------------------------------------------- detail modal */
export const DocumentDetailModal = ({ doc, roles, onClose, onRequirementAdded }) => {
  const [tab, setTab] = useState('chunks');
  const [chunks, setChunks] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [flags, setFlags] = useState(null);
  const [error, setError] = useState(null);
  const [roleId, setRoleId] = useState('');
  const [added, setAdded] = useState({});
  const [addingIdx, setAddingIdx] = useState(null);

  useEffect(() => {
    if (!doc) return;
    setTab('chunks'); setChunks(null); setExtracted(null); setFlags(null); setError(null); setAdded({});
    apiClient.get(`/documents/${doc.id}/chunks`).then((r) => setChunks(r.data.chunks)).catch((e) => setError(errorMessage(e, 'Could not load chunks.')));
  }, [doc]);

  useEffect(() => {
    if (!doc) return;
    if (tab === 'requirements' && !extracted) {
      apiClient.get(`/documents/${doc.id}/requirements`).then((r) => setExtracted(r.data)).catch((e) => setError(errorMessage(e, 'Could not extract requirements.')));
    }
    if (tab === 'security' && !flags) {
      apiClient.get('/documents/security-flags').then((r) => setFlags(r.data.filter((f) => f.document_id === doc.id))).catch((e) => setError(errorMessage(e, 'Could not load flags.')));
    }
  }, [tab, doc, extracted, flags]);

  const addToMatrix = async (item, idx) => {
    if (!roleId) { setError('Choose the role these requirements belong to first.'); return; }
    setAddingIdx(idx); setError(null);
    const code = `${doc.document_code.replace(/[^A-Za-z0-9]/g, '').slice(0, 8).toUpperCase()}-${String(idx + 1).padStart(3, '0')}`;
    try {
      await apiClient.post('/requirements/', {
        requirement_code: code,
        role_id: parseInt(roleId, 10),
        ...item.suggested_row,
        due_stage: item.mandatory ? 'Week 1' : 'First 30 Days',
        assessment_requirement: null,
      });
      setAdded((a) => ({ ...a, [idx]: code }));
      onRequirementAdded?.();
    } catch (e) {
      setError(errorMessage(e, 'Could not add requirement.'));
    } finally {
      setAddingIdx(null);
    }
  };

  return (
    <Modal
      open={!!doc}
      onClose={onClose}
      icon={FileText}
      size="xl"
      title={doc ? `${doc.document_code} · ${doc.title}` : ''}
      subtitle={doc ? `${doc.doc_type} · v${doc.version} · ${doc.is_active_version ? 'Active' : 'Obsolete'} · ${doc.precedence_label || ''}` : ''}
    >
      <Tabs
        layoutId="doc-detail-tabs"
        active={tab}
        onChange={setTab}
        className="mb-4"
        tabs={[
          { key: 'chunks', label: 'Chunks', icon: FileText, count: doc?.chunk_count },
          { key: 'requirements', label: 'Extracted requirements', icon: ListChecks },
          { key: 'security', label: 'Security flags', icon: ShieldAlert, count: doc?.security_flag_count },
        ]}
      />
      {error && <Alert tone="danger" className="mb-3" onDismiss={() => setError(null)}>{error}</Alert>}

      {tab === 'chunks' && (
        !chunks ? <LoadingState /> : chunks.length === 0 ? <EmptyState title="No chunks" /> : (
          <ul className="space-y-2">
            {chunks.map((c) => (
              <li key={c.chunk_code} className="card-inset p-3.5">
                <div className="flex flex-wrap items-center gap-2 text-[12px] text-subtle">
                  <span className="code-tag !text-[11.5px]">{c.chunk_code}</span>
                  <span>{c.section}</span><span aria-hidden="true">·</span><span>{c.location}</span>
                </div>
                <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-relaxed text-slate-200 text-break">{c.content}</p>
              </li>
            ))}
          </ul>
        )
      )}

      {tab === 'requirements' && (
        !extracted ? <LoadingState label="Extracting…" /> : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(extracted.summary.by_class).map(([k, v]) => <Badge key={k} tone={classTone(k)}>{k}: {v}</Badge>)}
              </div>
              <Field label="Add to the matrix for role" htmlFor="extract-role" className="w-full sm:w-64">
                <select id="extract-role" className="select" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
                  <option value="">Choose a role…</option>
                  {roles.map((r) => <option key={r.id} value={r.id}>{r.role_name}</option>)}
                </select>
              </Field>
            </div>
            <p className="text-[12.5px] text-subtle">
              Sentences are classified with deterministic rules (Must Know / Complete / Demonstrate / Acknowledge,
              Recommended, Optional, Not Applicable). Review each one before adding it to the Requirement Matrix.
            </p>
            {extracted.requirements.length === 0 && <EmptyState icon={ListChecks} title="No requirement-like sentences found" />}
            <ul className="space-y-2">
              {extracted.requirements.map((r, i) => (
                <li key={i} className="card-inset flex flex-col gap-2 p-3.5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={classTone(r.classification)} dot>{r.classification}</Badge>
                      <span className="text-[12px] text-subtle">{r.section} · {r.location}</span>
                    </div>
                    <p className="mt-1.5 text-[13px] text-slate-200 text-break">{r.text}</p>
                  </div>
                  {added[i] ? (
                    <Badge tone="success"><Check size={12} /> Added as {added[i]}</Badge>
                  ) : (
                    <Button size="sm" variant="secondary" icon={Plus} loading={addingIdx === i} onClick={() => addToMatrix(r, i)}>
                      Add to matrix
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      )}

      {tab === 'security' && (
        !flags ? <LoadingState /> : flags.length === 0 ? (
          <EmptyState icon={ShieldAlert} title="No suspicious instructions found" description="The prompt-injection guard scanned every chunk and any hidden text." />
        ) : (
          <ul className="space-y-2">
            {flags.map((f) => (
              <li key={f.id} className="card-inset p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={f.severity === 'high' ? 'danger' : 'warning'} dot>{f.severity}</Badge>
                  <span className="text-[13px] font-medium text-slate-100">{f.label}</span>
                  {f.hidden_text && <Badge tone="warning">Hidden text</Badge>}
                  <span className="text-[12px] text-subtle">{f.location}</span>
                </div>
                <p className="mt-1.5 text-[13px] text-rose-200/90 text-break">&ldquo;{f.text}&rdquo;</p>
              </li>
            ))}
          </ul>
        )
      )}
    </Modal>
  );
};

/* --------------------------------------------------- new version modal */
export const NewVersionModal = ({ doc, onClose, onUploaded }) => {
  const empty = { document_code: '', version: '', effective_date: '', file: null };
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (doc) {
      const next = (parseFloat(doc.version) || 1) + 1;
      setForm({ ...empty, document_code: `${doc.family_code || doc.document_code}-v${Math.floor(next)}`, version: `${next.toFixed(1)}` });
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.file) { setError('Choose the new version file.'); return; }
    setBusy(true); setError(null);
    const payload = new FormData();
    payload.append('document_code', form.document_code);
    payload.append('title', doc.title);
    payload.append('doc_type', doc.doc_type);
    payload.append('department', doc.department);
    payload.append('version', form.version);
    if (form.effective_date) payload.append('effective_date', form.effective_date);
    payload.append('file', form.file);
    try {
      const res = await apiClient.post(`/documents/upload-version/${encodeURIComponent(doc.family_code || doc.document_code)}`, payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUploaded(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Version upload failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={!!doc} onClose={() => !busy && onClose()} icon={UploadCloud} size="sm"
      title="Upload a new version"
      subtitle={doc ? `The current active version (${doc.document_code}, v${doc.version}) becomes obsolete.` : ''}>
      {doc && (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="grid grid-cols-2 gap-3">
            <Field label="New document code" htmlFor="nv-code">
              <input id="nv-code" className="input" required value={form.document_code} onChange={(e) => setForm({ ...form, document_code: e.target.value })} />
            </Field>
            <Field label="Version" htmlFor="nv-version">
              <input id="nv-version" className="input" required value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} />
            </Field>
          </div>
          <Field label="Effective date" htmlFor="nv-date" hint="Defaults to today.">
            <input id="nv-date" type="date" className="input" value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} />
          </Field>
          <Field label="File" htmlFor="nv-file">
            <input id="nv-file" type="file" accept=".pdf,.docx,.txt,.md" className="input !h-auto !py-2"
              onChange={(e) => setForm({ ...form, file: e.target.files[0] })} />
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="submit" variant="primary" loading={busy} icon={UploadCloud}>Upload version</Button>
          </div>
        </form>
      )}
    </Modal>
  );
};

/* -------------------------------------------------------- impact modal */
export const ImpactModal = ({ doc, onClose, onChanged }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busyPlan, setBusyPlan] = useState(null);
  const [relinking, setRelinking] = useState(false);

  const load = () => {
    setData(null); setError(null);
    apiClient.get(`/documents/impact/${doc.id}`).then((r) => setData(r.data)).catch((e) => setError(errorMessage(e, 'Impact analysis failed.')));
  };
  useEffect(() => { if (doc) { setNotice(null); load(); } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc]);

  const relink = async () => {
    setRelinking(true); setError(null);
    try {
      const r = await apiClient.post(`/documents/impact/${doc.id}/relink-requirements`);
      setNotice(`Relinked ${r.data.relinked.length} requirement(s) to ${r.data.to_document_code}.`);
      onChanged?.(); load();
    } catch (e) { setError(errorMessage(e, 'Relink failed.')); } finally { setRelinking(false); }
  };

  const regenerate = async (planId) => {
    setBusyPlan(planId); setError(null);
    try {
      const r = await apiClient.post(`/onboarding/plan/${planId}/regenerate-affected`, null, { params: { document_id: data.document.id } });
      setNotice(`Plan #${planId}: affected items regenerated as plan #${r.data.id} (${r.data.verification_status}).`);
      load();
    } catch (e) { setError(errorMessage(e, 'Selective regeneration failed.')); } finally { setBusyPlan(null); }
  };

  const s = data?.summary || {};
  return (
    <Modal open={!!doc} onClose={onClose} icon={GitCompare} size="xl"
      title={doc ? `Impact analysis · ${doc.document_code}` : ''}
      subtitle={data?.previous_version ? `Compared with ${data.previous_version.document_code} (v${data.previous_version.version})` : 'Policy update detection'}>
      {error && <Alert tone="danger" className="mb-3">{error}</Alert>}
      {notice && <Alert tone="success" className="mb-3" onDismiss={() => setNotice(null)}>{notice}</Alert>}
      {!data && !error && <LoadingState label="Analysing…" />}
      {data && !data.previous_version && <EmptyState icon={GitCompare} title="No previous version" description={data.message} />}
      {data && data.previous_version && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              ['Changed sentences', s.changed_sentences], ['Plans to regenerate', s.plans_requiring_regeneration],
              ['Outdated quiz questions', s.outdated_quiz_questions], ['Employees affected', s.employees_affected],
            ].map(([k, v]) => (
              <div key={k} className="card-inset p-3">
                <p className="text-[12px] text-muted">{k}</p>
                <p className="mt-1 text-[20px] font-semibold tabular-nums">{v ?? 0}</p>
              </div>
            ))}
          </div>

          <section>
            <h3 className="mb-2 text-[13.5px] font-semibold">What changed</h3>
            {data.changes.changed.length + data.changes.added.length + data.changes.removed.length === 0 && (
              <p className="text-[13px] text-subtle">No textual differences found.</p>
            )}
            <ul className="space-y-2">
              {data.changes.changed.map((c, i) => (
                <li key={`c${i}`} className="card-inset p-3.5 text-[13px]">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <Badge tone="warning">Changed</Badge>
                    <span className="text-[12px] text-subtle">{c.section}</span>
                    {c.value_changes.map((v) => <Badge key={v} tone="danger">{v}</Badge>)}
                    {c.rule_change && <Badge tone="danger">Rule: {c.rule_change}</Badge>}
                  </div>
                  <p className="text-subtle line-through text-break">{c.old}</p>
                  <p className="mt-1 text-slate-100 text-break">{c.new}</p>
                </li>
              ))}
              {data.changes.added.map((c, i) => (
                <li key={`a${i}`} className="card-inset p-3.5 text-[13px]"><Badge tone="success">Added</Badge> <span className="ml-2 text-slate-200 text-break">{c.text}</span></li>
              ))}
              {data.changes.removed.map((c, i) => (
                <li key={`r${i}`} className="card-inset p-3.5 text-[13px]"><Badge tone="danger">Removed</Badge> <span className="ml-2 text-subtle line-through text-break">{c.text}</span></li>
              ))}
            </ul>
          </section>

          {data.stale_requirements.length > 0 && (
            <section className="card-inset p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-[13.5px] font-semibold">Requirement Matrix rows still linked to the old version</h3>
                  <p className="mt-0.5 text-[12.5px] text-muted">{data.stale_requirements.map((r) => `${r.requirement_code} (${r.role_name})`).join(', ')}</p>
                </div>
                <Button size="sm" variant="secondary" icon={Link2} loading={relinking} onClick={relink}>Relink to active version</Button>
              </div>
            </section>
          )}

          <section>
            <h3 className="mb-2 text-[13.5px] font-semibold">Affected onboarding plans</h3>
            {data.affected_plans.length === 0 && <p className="text-[13px] text-subtle">No plans use this document family.</p>}
            <ul className="space-y-2">
              {data.affected_plans.map((p) => (
                <li key={p.plan_id} className="card-inset p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13.5px] font-medium text-slate-100">Plan #{p.plan_id} · {p.employee_name} <span className="text-subtle">({p.role_name})</span></p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <StatusBadge status={p.verification_status} />
                        {Object.entries(p.affected_counts).map(([k, v]) => <Badge key={k}>{v} {k}</Badge>)}
                        {p.used_old_version && <Badge tone="warning">Used old version</Badge>}
                      </div>
                    </div>
                    {p.requires_regeneration && (
                      <Button size="sm" variant="primary" icon={RefreshCw} loading={busyPlan === p.plan_id} onClick={() => regenerate(p.plan_id)}>
                        Regenerate affected items
                      </Button>
                    )}
                  </div>
                  {p.affected_items.length > 0 && (
                    <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                      {p.affected_items.map((it, i) => (
                        <li key={i} className="text-[12.5px]">
                          <span className="font-medium text-slate-200">{it.label}</span>
                          <span className="text-subtle"> — {it.reasons.join('; ')}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Modal>
  );
};
