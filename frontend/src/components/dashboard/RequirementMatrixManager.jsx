import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Plus, ListChecks, Trash2, UploadCloud, Download } from 'lucide-react';
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, PageHeader, SearchInput, statusTone,
} from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';
import { Modal } from '../ui/Modal';
import { useConfirm } from '../ui/ConfirmDialog';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   RequirementMatrixManager — REAL backend connection
   Calls:
     POST   /requirements/            (create one)
     GET    /requirements/            (list)
     PUT    /requirements/{id}        (update)
     DELETE /requirements/{id}        (delete)
     POST   /requirements/bulk-upload (CSV bulk import)
     GET    /requirements/template/csv (download starter CSV)

   Needs `roles` and `documents` (from AdminDashboard, already fetched from
   backend) to populate the role / source-document dropdowns.
   ========================================================================== */
export const RequirementMatrixManager = ({ requirements, roles, documents, refreshRequirements }) => {
  const emptyForm = {
    requirement_code: '',
    role_id: '',
    policy_requirement: '',
    process_requirement: '',
    competency: '',
    mandatory: true,
    priority: 'Medium',
    due_stage: 'Week 1',
    source_document_id: '',
    source_section: '',
    assessment_requirement: '',
  };

  const [formData, setFormData] = useState(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // --- CSV bulk upload state ---
  const [csvFile, setCsvFile] = useState(null);
  const [isCsvUploading, setIsCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState(null);
  const [csvError, setCsvError] = useState(null);

  const roleNameById = useMemo(() => {
    const map = {};
    roles.forEach((r) => { map[r.id] = r.role_name; });
    return map;
  }, [roles]);

  const docCodeById = useMemo(() => {
    const map = {};
    (documents || []).forEach((d) => { map[d.id] = d.document_code; });
    return map;
  }, [documents]);

  // --- Create requirement ---
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);

    try {
      const payload = {
        ...formData,
        role_id: parseInt(formData.role_id, 10),
        source_document_id: formData.source_document_id ? parseInt(formData.source_document_id, 10) : null,
      };
      await apiClient.post('/requirements/', payload);
      setFormData(emptyForm);
      await refreshRequirements();
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create requirement.';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiClient.delete(`/requirements/${id}`);
      await refreshRequirements();
    } catch (err) {
      setError('Failed to delete requirement.');
    }
  };

  // --- CSV bulk upload ---
  const handleCsvUpload = async (e) => {
    e.preventDefault();
    if (!csvFile) {
      setCsvError('Please select a .csv file first.');
      return;
    }
    setIsCsvUploading(true);
    setCsvResult(null);
    setCsvError(null);

    const payload = new FormData();
    payload.append('file', csvFile);

    try {
      const res = await apiClient.post('/requirements/bulk-upload', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setCsvResult(res.data);
      setCsvFile(null);
      const csvInput = document.getElementById('csv-file-input');
      if (csvInput) csvInput.value = '';
      await refreshRequirements();
    } catch (err) {
      const detail = err.response?.data?.detail || 'CSV upload failed. Check backend server.';
      setCsvError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setIsCsvUploading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await apiClient.get('/requirements/template/csv', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'requirement_matrix_template.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setCsvError('Could not download template. Check backend server.');
    }
  };

  const filteredRequirements = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return requirements.filter(
      (r) =>
        r.requirement_code.toLowerCase().includes(q) ||
        (roleNameById[r.role_id] || '').toLowerCase().includes(q) ||
        (r.policy_requirement || '').toLowerCase().includes(q) ||
        (r.competency || '').toLowerCase().includes(q)
    );
  }, [requirements, searchQuery, roleNameById]);

  const pager = usePagination(filteredRequirements, { pageSize: 10, resetKey: searchQuery });
  const { ask, dialog } = useConfirm();
  const [detail, setDetail] = useState(null); // requirement shown in the read-only detail dialog
  const [formOpen, setFormOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Requirement Matrix"
        description="The ground-truth table: policy, process and competency requirements per role, each traceable to a source document."
        actions={
          <>
            <Button variant="ghost" icon={Download} onClick={handleDownloadTemplate}>
              CSV template
            </Button>
            <Button variant="secondary" icon={UploadCloud} onClick={() => setCsvOpen(true)}>
              Import CSV
            </Button>
            <Button variant="primary" icon={Plus} onClick={() => { setError(null); setFormOpen(true); }}>
              Add requirement
            </Button>
          </>
        }
      />

      {error && !formOpen && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}

      {csvResult && !csvOpen && (
        <Alert tone="success" title={csvResult.message} onDismiss={() => setCsvResult(null)}>
          Created {csvResult.created_count} · Skipped {csvResult.skipped_count}
          {csvResult.errors?.length > 0 && (
            <button type="button" onClick={() => setCsvOpen(true)} className="ml-2 font-semibold underline underline-offset-2">
              View row errors
            </button>
          )}
        </Alert>
      )}
      {csvError && !csvOpen && <Alert tone="danger" onDismiss={() => setCsvError(null)}>{csvError}</Alert>}

      {/* ---------------- Create form + table ---------------- */}
      <div>
        <Card padded={false} className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <CardHeader icon={ListChecks} title="Requirements" description={`${requirements.length} in database · select a row for full text`} />
            <SearchInput
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search code, role, competency"
              className="w-full sm:w-72"
            />
          </div>

          <div className="table-wrap border-t border-line">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th className="hidden md:table-cell">Role</th>
                  <th>Policy / process</th>
                  <th className="hidden sm:table-cell">Priority</th>
                  <th className="hidden xl:table-cell">Due stage</th>
                  <th className="hidden lg:table-cell">Source</th>
                  <th className="w-12"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <motion.tbody key={pager.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                {pager.pageItems.length === 0 ? (
                  <tr>
                    <td colSpan="7">
                      <EmptyState
                        icon={ListChecks}
                        title={searchQuery ? 'No matching requirements' : 'No requirements yet'}
                        description={searchQuery ? 'Try a different search term.' : 'Add one with the form or bulk-upload a CSV.'}
                      />
                    </td>
                  </tr>
                ) : (
                  pager.pageItems.map((req) => (
                    <tr
                      key={req.id}
                      className="cursor-pointer"
                      onClick={() => setDetail(req)}
                    >
                      <td className="whitespace-nowrap align-top">
                        <button
                          type="button"
                          className="code-tag hover:underline"
                          onClick={(e) => { e.stopPropagation(); setDetail(req); }}
                        >
                          {req.requirement_code}
                        </button>
                        {!req.mandatory && <p className="mt-1 text-[11.5px] text-subtle">Optional</p>}
                      </td>
                      <td className="hidden align-top md:table-cell">
                        <Badge>{roleNameById[req.role_id] || `#${req.role_id}`}</Badge>
                      </td>
                      <td className="min-w-[220px] max-w-[420px] align-top">
                        {req.policy_requirement && <p className="line-clamp-2 text-slate-200 text-break">{req.policy_requirement}</p>}
                        {req.process_requirement && <p className="mt-0.5 line-clamp-1 text-[12.5px] text-subtle text-break">{req.process_requirement}</p>}
                        <p className="mt-1 text-[12px] text-subtle md:hidden">{roleNameById[req.role_id] || `#${req.role_id}`}</p>
                      </td>
                      <td className="hidden align-top sm:table-cell">
                        {req.priority ? <Badge tone={statusTone(req.priority)} dot>{req.priority}</Badge> : <span className="text-subtle">—</span>}
                      </td>
                      <td className="hidden whitespace-nowrap align-top text-muted xl:table-cell">{req.due_stage || '—'}</td>
                      <td className="hidden whitespace-nowrap align-top font-mono text-[12.5px] text-muted lg:table-cell">
                        {req.source_document_id ? (docCodeById[req.source_document_id] || `#${req.source_document_id}`) : '—'}
                        {req.source_section && <span className="text-subtle"> §{req.source_section}</span>}
                      </td>
                      <td className="align-top text-right" onClick={(e) => e.stopPropagation()}>
                        <IconButton
                          label={`Delete ${req.requirement_code}`}
                          icon={Trash2}
                          danger
                          size={15}
                          onClick={() => ask({
                            title: 'Delete requirement?',
                            message: `${req.requirement_code} will be removed from the Requirement Matrix.`,
                            confirmLabel: 'Delete requirement',
                            onConfirm: () => handleDelete(req.id),
                          })}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </motion.tbody>
            </table>
          </div>

          <Pagination {...pager} onPageChange={pager.setPage} noun="requirements" />
        </Card>
      </div>

      <Modal
        open={formOpen}
        onClose={() => !isSaving && setFormOpen(false)}
        icon={Plus}
        title="Add requirement"
        subtitle="One row of the Role Requirement Matrix."
      >
        <form onSubmit={async (e) => { if (await handleSubmit(e)) setFormOpen(false); }} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
            <Field label="Requirement code" htmlFor="req-code">
              <input
                id="req-code" type="text" required placeholder="e.g. R001"
                value={formData.requirement_code}
                onChange={(e) => setFormData({ ...formData, requirement_code: e.target.value })}
                className="input"
              />
            </Field>

            <Field
              label="Role" htmlFor="req-role"
              hint={roles.length === 0 ? 'No roles yet — create a role first.' : undefined}
            >
              <select
                id="req-role"
                required
                value={formData.role_id}
                onChange={(e) => setFormData({ ...formData, role_id: e.target.value })}
                className="select"
              >
                <option value="">Select a role…</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>{r.role_name}</option>
                ))}
              </select>
            </Field>

            <Field label="Policy requirement" htmlFor="req-policy">
              <textarea
                id="req-policy" rows={2} placeholder="e.g. Must follow escalation SOP within 24 hours"
                value={formData.policy_requirement}
                onChange={(e) => setFormData({ ...formData, policy_requirement: e.target.value })}
                className="textarea"
              />
            </Field>

            <Field label="Process requirement" htmlFor="req-process">
              <textarea
                id="req-process" rows={2} placeholder="e.g. Log every ticket in CRM before closing"
                value={formData.process_requirement}
                onChange={(e) => setFormData({ ...formData, process_requirement: e.target.value })}
                className="textarea"
              />
            </Field>

            <Field label="Competency" htmlFor="req-competency">
              <input
                id="req-competency" type="text" placeholder="e.g. Conflict de-escalation"
                value={formData.competency}
                onChange={(e) => setFormData({ ...formData, competency: e.target.value })}
                className="input"
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Priority" htmlFor="req-priority">
                <select
                  id="req-priority"
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  className="select"
                >
                  <option>High</option>
                  <option>Medium</option>
                  <option>Low</option>
                </select>
              </Field>
              <Field label="Due stage" htmlFor="req-stage">
                <select
                  id="req-stage"
                  value={formData.due_stage}
                  onChange={(e) => setFormData({ ...formData, due_stage: e.target.value })}
                  className="select"
                >
                  <option>Day 1</option>
                  <option>Week 1</option>
                  <option>First 30 Days</option>
                  <option>First 90 Days</option>
                </select>
              </Field>
            </div>

            <Field label="Source document" htmlFor="req-doc">
              <select
                id="req-doc"
                value={formData.source_document_id}
                onChange={(e) => setFormData({ ...formData, source_document_id: e.target.value })}
                className="select"
              >
                <option value="">None</option>
                {(documents || []).map((d) => (
                  <option key={d.id} value={d.id}>{d.document_code} — {d.title}</option>
                ))}
              </select>
            </Field>

            <Field label="Source section" htmlFor="req-section">
              <input
                id="req-section" type="text" placeholder="e.g. 4.2"
                value={formData.source_section}
                onChange={(e) => setFormData({ ...formData, source_section: e.target.value })}
                className="input"
              />
            </Field>

            <Field label="Assessment requirement" htmlFor="req-assess" className="sm:col-span-2">
              <textarea
                id="req-assess" rows={2} placeholder="e.g. Explain the 3-step escalation process"
                value={formData.assessment_requirement}
                onChange={(e) => setFormData({ ...formData, assessment_requirement: e.target.value })}
                className="textarea"
              />
            </Field>

            <label htmlFor="mandatory-checkbox" className="flex cursor-pointer items-center gap-2.5 text-[13px] font-medium text-slate-300 sm:col-span-2">
              <input
                type="checkbox" id="mandatory-checkbox"
                checked={formData.mandatory}
                onChange={(e) => setFormData({ ...formData, mandatory: e.target.checked })}
                className="checkbox"
              />
              Mandatory requirement
            </label>

            <div className="sm:col-span-2">
              <div className="flex flex-wrap justify-end gap-2 pt-1">
                <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={isSaving}>Cancel</Button>
                <Button type="submit" variant="primary" loading={isSaving} disabled={roles.length === 0}>
                  {isSaving ? 'Saving…' : 'Save requirement'}
                </Button>
              </div>
            </div>
          </form>
      </Modal>

      <Modal
        open={csvOpen}
        onClose={() => !isCsvUploading && setCsvOpen(false)}
        icon={UploadCloud}
        title="Bulk import requirements (CSV)"
        subtitle="Fastest way to load many requirements at once."
      >
        <div>
        <p className="text-[13px] leading-relaxed text-muted text-break">
          Required columns: <code className="text-accent">requirement_code</code>, <code className="text-accent">role_name</code> (must match an existing role).
          Optional: policy_requirement, process_requirement, competency, mandatory, priority, due_stage, source_document_code, source_section, assessment_requirement.
        </p>

        <form onSubmit={handleCsvUpload} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="file" id="csv-file-input" accept=".csv" className="sr-only"
            onChange={(e) => setCsvFile(e.target.files[0])}
          />
          <label
            htmlFor="csv-file-input"
            className="flex h-10 min-w-0 flex-1 cursor-pointer items-center gap-2.5 rounded-[9px] border border-dashed border-line-strong bg-canvas px-3.5 text-[13px] transition-colors hover:border-accent/50"
          >
            <UploadCloud size={16} className="shrink-0 text-subtle" />
            <span className={`truncate ${csvFile ? 'text-slate-200' : 'text-subtle'}`}>
              {csvFile ? csvFile.name : 'Click to select a .csv file'}
            </span>
          </label>
          <Button type="submit" variant="primary" loading={isCsvUploading} icon={UploadCloud} className="shrink-0">
            {isCsvUploading ? 'Importing…' : 'Upload CSV'}
          </Button>
        </form>

        {csvError && <Alert tone="danger" className="mt-4" onDismiss={() => setCsvError(null)}>{csvError}</Alert>}

        {csvResult && (
          <div className="mt-4 space-y-3">
            <Alert tone="success" title={csvResult.message} onDismiss={() => setCsvResult(null)}>
              Rows in file: <strong>{csvResult.total_rows_in_file}</strong> · Created: <strong>{csvResult.created_count}</strong> · Skipped: <strong>{csvResult.skipped_count}</strong>
            </Alert>

            {csvResult.errors && csvResult.errors.length > 0 && (
              <div className="card-inset max-h-60 overflow-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Requirement</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {csvResult.errors.map((err, idx) => (
                      <tr key={idx}>
                        <td className="tabular-nums">{err.row_number}</td>
                        <td className="font-mono text-[12.5px]">{err.requirement_code || '—'}</td>
                        <td className="min-w-[220px] text-rose-300 text-break">{err.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
        </div>
      </Modal>

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        icon={ListChecks}
        title={detail ? `${detail.requirement_code} · ${roleNameById[detail.role_id] || `Role #${detail.role_id}`}` : ''}
        subtitle={detail ? `${detail.mandatory ? 'Mandatory' : 'Optional'} · ${detail.priority || 'No priority'} priority · ${detail.due_stage || 'No due stage'}` : ''}
      >
        {detail && (
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[
              ['Policy requirement', detail.policy_requirement],
              ['Process requirement', detail.process_requirement],
              ['Competency', detail.competency],
              ['Assessment requirement', detail.assessment_requirement],
              ['Source document', detail.source_document_id ? (docCodeById[detail.source_document_id] || `#${detail.source_document_id}`) : null],
              ['Source section', detail.source_section],
            ].map(([k, v]) => (
              <div key={k} className="card-inset min-w-0 p-3.5">
                <dt className="eyebrow">{k}</dt>
                <dd className="mt-1.5 whitespace-pre-wrap text-[13.5px] leading-relaxed text-slate-200 text-break">{v || '—'}</dd>
              </div>
            ))}
          </dl>
        )}
      </Modal>

      {dialog}
    </div>
  );
};

export default RequirementMatrixManager;