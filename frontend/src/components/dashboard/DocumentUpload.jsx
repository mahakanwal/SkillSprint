import React, { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { UploadCloud, FileText, Plus, Eye, GitCompare, History, ShieldAlert } from 'lucide-react';
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, PageHeader, SearchInput } from '../ui/primitives';
import { DocumentDetailModal, NewVersionModal, ImpactModal, DOC_TYPES, DEPARTMENTS } from './documents/DocumentModals';
import { Pagination, usePagination } from '../ui/Pagination';
import { Modal } from '../ui/Modal';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   DocumentUpload Component — REAL backend connection
   Calls: POST /documents/upload , GET /documents/list
   ========================================================================== */
export const DocumentUpload = ({ documents, refreshDocuments, roles = [], refreshRequirements }) => {
  const [formData, setFormData] = useState({
    document_code: '',
    title: '',
    doc_type: 'Policy',
    department: 'HR',
    version: '1.0',
    effective_date: '',
    expiry_date: '',
    file: null,
  });
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResponse, setUploadResponse] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsUploading(true);
    setUploadResponse(null);
    setUploadError(null);

    if (!formData.file) {
      setUploadError('Please select a PDF, DOCX, TXT or Markdown file.');
      setIsUploading(false);
      return false;
    }

    const payload = new FormData();
    payload.append('document_code', formData.document_code);
    payload.append('title', formData.title);
    payload.append('doc_type', formData.doc_type);
    payload.append('department', formData.department);
    payload.append('version', formData.version);
    if (formData.effective_date) payload.append('effective_date', formData.effective_date);
    if (formData.expiry_date) payload.append('expiry_date', formData.expiry_date);
    payload.append('file', formData.file);

    try {
      const res = await apiClient.post('/documents/upload', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setUploadResponse({
        message: res.data.message,
        code: res.data.document_code,
        chunksCreated: res.data.total_chunks_created,
        securityFlags: res.data.security_flags || [],
      });

      setFormData({ document_code: '', title: '', doc_type: 'Policy', department: 'HR', version: '1.0', effective_date: '', expiry_date: '', file: null });
      await refreshDocuments(); // reload real list from backend
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Upload failed. Check backend server.';
      setUploadError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      return false;
    } finally {
      setIsUploading(false);
    }
  };

  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('');
  const [detailDoc, setDetailDoc] = useState(null);
  const [versionDoc, setVersionDoc] = useState(null);
  const [impactDoc, setImpactDoc] = useState(null);
  const [versionNotice, setVersionNotice] = useState(null);

  const filteredDocs = useMemo(() => {
    return documents.filter(
      (d) =>
        (d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.document_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (d.department || '').toLowerCase().includes(searchQuery.toLowerCase())) &&
        (statusFilter === 'all' ||
          (statusFilter === 'active' && d.is_active_version) ||
          (statusFilter === 'obsolete' && !d.is_active_version) ||
          (statusFilter === 'flagged' && d.security_flag_count > 0)) &&
        (!typeFilter || d.doc_type === typeFilter)
    );
  }, [documents, searchQuery, statusFilter, typeFilter]);

  const pager = usePagination(filteredDocs, { pageSize: 10, resetKey: `${searchQuery}|${statusFilter}|${typeFilter}` });
  const [formOpen, setFormOpen] = useState(false);
  const flaggedDocs = documents.filter((d) => d.security_flag_count > 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Document pipeline"
        description="Upload policy manuals, SOPs and handbooks. Extraction and chunking run on the backend."
        actions={<Button variant="primary" icon={Plus} onClick={() => { setUploadError(null); setFormOpen(true); }}>Upload document</Button>}
      />

      {uploadResponse && (
        <Alert tone="success" title={uploadResponse.message} onDismiss={() => setUploadResponse(null)}>
          Code <span className="font-mono font-semibold">{uploadResponse.code}</span> · {uploadResponse.chunksCreated} chunks extracted
          {uploadResponse.securityFlags.length > 0 && (
            <span className="mt-1 block text-amber-200">
              The prompt-injection guard found {uploadResponse.securityFlags.length} suspicious instruction(s); they will be
              redacted before any text is sent to the GenAI model.
            </span>
          )}
        </Alert>
      )}

      {versionNotice && (
        <Alert tone="success" title={versionNotice.message} onDismiss={() => setVersionNotice(null)}>
          <button type="button" className="font-semibold underline underline-offset-2"
            onClick={() => { setImpactDoc(documents.find((d) => d.id === versionNotice.document_id) || { id: versionNotice.document_id, document_code: versionNotice.document_code }); setVersionNotice(null); }}>
            Run impact analysis
          </button>
        </Alert>
      )}

      {flaggedDocs.length > 0 && (
        <Alert tone="warning" title={`${flaggedDocs.length} document(s) contain suspicious instructions`}>
          {flaggedDocs.map((d) => d.document_code).join(', ')} — flagged text is treated as data and redacted before generation.
        </Alert>
      )}

      {uploadError && !formOpen && <Alert tone="danger" onDismiss={() => setUploadError(null)}>{uploadError}</Alert>}

      <div>
        {/* Document table */}
        <Card padded={false} className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <CardHeader icon={FileText} title="Documents" description={`${documents.length} in database`} />
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <select aria-label="Filter by status" className="select !h-9 !text-[13px] sm:w-36" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="all">All versions</option>
                <option value="active">Active only</option>
                <option value="obsolete">Obsolete only</option>
                <option value="flagged">Flagged only</option>
              </select>
              <select aria-label="Filter by type" className="select !h-9 !text-[13px] sm:w-36" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                <option value="">All types</option>
                {DOC_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
              <SearchInput
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search code, title, department"
                className="w-full sm:w-60"
              />
            </div>
          </div>

          <div className="table-wrap border-t border-line">
            <table className="table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th className="hidden md:table-cell">Type</th>
                  <th className="hidden md:table-cell">Department</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th className="hidden lg:table-cell">Chunks</th>
                  <th className="w-32"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <motion.tbody key={pager.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                {pager.pageItems.length === 0 ? (
                  <tr>
                    <td colSpan="7">
                      <EmptyState
                        icon={FileText}
                        title={searchQuery ? 'No matching documents' : 'No documents yet'}
                        description={searchQuery ? 'Try a different search term.' : 'Upload one to get started.'}
                      />
                    </td>
                  </tr>
                ) : (
                  pager.pageItems.map((doc) => (
                    <tr key={doc.id}>
                      <td className="min-w-[200px] max-w-[420px]">
                        <span className="code-tag">{doc.document_code}</span>
                        <p className="mt-0.5 font-medium text-slate-100 text-break">{doc.title}</p>
                        <p className="mt-0.5 text-[12px] text-subtle md:hidden">{doc.doc_type} · {doc.department}</p>
                      </td>
                      <td className="hidden text-muted md:table-cell">{doc.doc_type}</td>
                      <td className="hidden md:table-cell"><Badge>{doc.department}</Badge></td>
                      <td className="font-mono text-[12.5px] text-slate-300">{doc.version}</td>
                      <td>
                        <div className="flex flex-wrap gap-1.5">
                          <Badge tone={doc.is_active_version ? 'success' : 'neutral'} dot>
                            {doc.is_active_version ? 'Active' : 'Obsolete'}
                          </Badge>
                          {doc.security_flag_count > 0 && (
                            <Badge tone="danger" title="Suspicious instructions found"><ShieldAlert size={11} /> {doc.security_flag_count}</Badge>
                          )}
                        </div>
                      </td>
                      <td className="hidden tabular-nums text-muted lg:table-cell">{doc.chunk_count ?? '—'}</td>
                      <td className="whitespace-nowrap text-right">
                        <IconButton label={`View ${doc.document_code}`} icon={Eye} size={15} onClick={() => setDetailDoc(doc)} />
                        {doc.is_active_version && (
                          <IconButton label={`Upload new version of ${doc.document_code}`} icon={History} size={15} onClick={() => setVersionDoc(doc)} />
                        )}
                        {(doc.supersedes_document_id || !doc.is_active_version) && (
                          <IconButton label={`Impact analysis for ${doc.document_code}`} icon={GitCompare} size={15} onClick={() => setImpactDoc(doc)} />
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </motion.tbody>
            </table>
          </div>

          <Pagination {...pager} onPageChange={pager.setPage} noun="documents" />
        </Card>
      </div>

      <Modal
        open={formOpen}
        onClose={() => !isUploading && setFormOpen(false)}
        icon={UploadCloud}
        title="Ingest new document"
        subtitle="PDF, DOCX, TXT or Markdown. Text is extracted, split into traceable chunks and scanned for injected instructions."
        size="sm"
      >
        <form onSubmit={async (e) => { if (await handleSubmit(e)) setFormOpen(false); }} className="space-y-4">
            {uploadError && <Alert tone="danger">{uploadError}</Alert>}
            <Field label="Document code" htmlFor="doc-code">
              <input
                id="doc-code" type="text" required placeholder="e.g. SOP-07"
                value={formData.document_code}
                onChange={(e) => setFormData({ ...formData, document_code: e.target.value })}
                className="input"
              />
            </Field>
            <Field label="Title" htmlFor="doc-title">
              <input
                id="doc-title" type="text" required placeholder="Customer Support Escalation SOP"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="input"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type" htmlFor="doc-type">
                <select
                  id="doc-type"
                  value={formData.doc_type}
                  onChange={(e) => setFormData({ ...formData, doc_type: e.target.value })}
                  className="select"
                >
                  {DOC_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Department" htmlFor="doc-dept">
                <select
                  id="doc-dept"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="select"
                >
                  {DEPARTMENTS.map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Version" htmlFor="doc-version">
                <input
                  id="doc-version" type="text" required placeholder="1.0"
                  value={formData.version}
                  onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                  className="input"
                />
              </Field>
              <Field label="Effective" htmlFor="doc-eff">
                <input id="doc-eff" type="date" className="input" value={formData.effective_date}
                  onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })} />
              </Field>
              <Field label="Expiry" htmlFor="doc-exp">
                <input id="doc-exp" type="date" className="input" value={formData.expiry_date}
                  onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })} />
              </Field>
            </div>

            <Field label="File">
              <input
                type="file" className="sr-only" id="file-upload" accept=".pdf,.docx,.txt,.md"
                onChange={(e) => setFormData({ ...formData, file: e.target.files[0] })}
              />
              <label
                htmlFor="file-upload"
                className="flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-line-strong bg-canvas px-4 py-6 text-center transition-colors hover:border-accent/50 hover:bg-white/[0.015]"
              >
                <UploadCloud size={20} className="mb-2 text-subtle" />
                <span className="text-[13px] font-medium text-slate-200">Click to select a PDF, DOCX, TXT or MD file</span>
                <span className="mt-1 max-w-full text-[12.5px] text-break text-subtle">
                  {formData.file ? <span className="text-accent">{formData.file.name}</span> : 'Max one file per upload'}
                </span>
              </label>
            </Field>

            <div className="flex flex-wrap justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={isUploading}>Cancel</Button>
              <Button type="submit" variant="primary" loading={isUploading} icon={UploadCloud}>
                {isUploading ? 'Uploading & chunking…' : 'Upload & process'}
              </Button>
            </div>
          </form>
      </Modal>
      <DocumentDetailModal doc={detailDoc} roles={roles} onClose={() => setDetailDoc(null)} onRequirementAdded={refreshRequirements} />
      <NewVersionModal
        doc={versionDoc}
        onClose={() => setVersionDoc(null)}
        onUploaded={async (data) => { setVersionDoc(null); setVersionNotice(data); await refreshDocuments(); }}
      />
      <ImpactModal doc={impactDoc} onClose={() => setImpactDoc(null)} onChanged={refreshRequirements} />
    </div>
  );
};

export default DocumentUpload;