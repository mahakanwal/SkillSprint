import React, { useState } from 'react';
import { UserPlus, Copy, Check } from 'lucide-react';
import { Alert, Button, Card, CardHeader, Field, PageHeader } from '../ui/primitives';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   StaffAccessManager — admin-only. Creates logins for non-employee staff
   roles via POST /auth/create-staff-login. The temporary password is shown
   exactly once in the response -- never retrievable again after this.
   ========================================================================== */
export const StaffAccessManager = () => {
  const emptyForm = { username: '', email: '', role: 'training_manager' };
  const [formData, setFormData] = useState(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const roleOptions = [
    { value: 'training_manager', label: 'Training Manager' },
    { value: 'reviewer', label: 'Reviewer' },
    { value: 'manager', label: 'Manager' },
    { value: 'admin', label: 'Admin' },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiClient.post('/auth/create-staff-login', formData);
      setResult(res.data);
      setFormData(emptyForm);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create staff login.';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(
      `Email: ${result.user.email}\nTemporary Password: ${result.temporary_password}`
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Team access"
        description="Create logins for staff — Training Managers, Reviewers, Managers or other Admins. Employee logins are created automatically from Employees."
      />

      <div className="space-y-4">
        {error && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}

        {result && (
          <Alert tone="success" title={`Login created for ${result.user.username} (${result.user.role})`} onDismiss={() => setResult(null)}>
            <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[13px]">
              <dt className="opacity-80">Email</dt>
              <dd className="font-mono text-break">{result.user.email}</dd>
              <dt className="opacity-80">Temporary password</dt>
              <dd className="font-mono font-semibold">{result.temporary_password}</dd>
            </dl>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button size="sm" variant="secondary" icon={copied ? Check : Copy} onClick={handleCopy}>
                {copied ? 'Copied' : 'Copy credentials'}
              </Button>
              <span className="text-[12.5px] text-amber-300/90">It will not be shown again — share it securely.</span>
            </div>
          </Alert>
        )}

        <Card>
          <CardHeader icon={UserPlus} title="New staff login" />
          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Full name" htmlFor="staff-name">
                <input
                  id="staff-name" type="text" required value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="input" placeholder="Sarah Ahmed"
                />
              </Field>
              <Field label="Email" htmlFor="staff-email">
                <input
                  id="staff-email" type="email" required value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="input" placeholder="sarah@company.com"
                />
              </Field>
            </div>
            <Field label="Role" htmlFor="staff-role">
              <select
                id="staff-role"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="select"
              >
                {roleOptions.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </Field>
            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={isSaving} icon={UserPlus}>
                {isSaving ? 'Creating…' : 'Create login'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default StaffAccessManager;
