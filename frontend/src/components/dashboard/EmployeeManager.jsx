import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { UserCheck, Users, Trash2, Copy, Check } from 'lucide-react';
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, PageHeader, SearchInput } from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';
import { useConfirm } from '../ui/ConfirmDialog';
import { Modal } from '../ui/Modal';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   EmployeeManager Component — REAL backend connection
   Calls: POST /employees/ , GET /employees/ , DELETE /employees/{id}
   Needs `roles` (from backend) to populate the role dropdown.
   ========================================================================== */
export const EmployeeManager = ({ employees, roles, refreshEmployees }) => {
  const [formData, setFormData] = useState({
    employee_code: '',
    full_name: '',
    email: '',
    department: 'Engineering',
    role_id: '',
    experience_level: 'Beginner',
    joining_date: '',
    reporting_manager: '',
    location: '',
    required_competencies: '',
    previous_experience: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  // Holds the one-time login credentials just after a successful create --
  // POST /employees/ only ever returns the temporary password in THIS
  // response, so it has to be shown here or it's gone for good.
  const [newCredentials, setNewCredentials] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setNewCredentials(null);

    try {
      const payload = {
        ...formData,
        role_id: parseInt(formData.role_id, 10),
        joining_date: formData.joining_date ? `${formData.joining_date}T00:00:00` : null,
      };
      const res = await apiClient.post('/employees/', payload);
      setNewCredentials({
        email: res.data.login_email,
        password: res.data.temporary_password,
        name: res.data.employee.full_name,
      });
      setFormData({
        employee_code: '', full_name: '', email: '', department: 'Engineering', role_id: '',
        experience_level: 'Beginner', joining_date: '', reporting_manager: '', location: '',
        required_competencies: '', previous_experience: '',
      });
      await refreshEmployees();
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create employee.';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (employeeId) => {
    try {
      await apiClient.delete(`/employees/${employeeId}`);
      await refreshEmployees();
    } catch (err) {
      setError('Failed to delete employee.');
    }
  };

  const getRoleName = (roleId) => {
    const role = roles.find((r) => r.id === roleId);
    return role ? role.role_name : 'Unassigned';
  };

  const [searchQuery, setSearchQuery] = useState('');
  const [copied, setCopied] = useState(false);
  const { ask, dialog } = useConfirm();
  const [formOpen, setFormOpen] = useState(false);

  const filteredEmployees = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return employees.filter(
      (e) =>
        (e.full_name || '').toLowerCase().includes(q) ||
        (e.employee_code || '').toLowerCase().includes(q) ||
        (e.department || '').toLowerCase().includes(q) ||
        getRoleName(e.role_id).toLowerCase().includes(q)
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employees, roles, searchQuery]);

  const pager = usePagination(filteredEmployees, { pageSize: 8, resetKey: searchQuery });

  const copyCredentials = () => {
    if (!newCredentials) return;
    navigator.clipboard?.writeText(`Email: ${newCredentials.email}\nTemporary Password: ${newCredentials.password}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Employees"
        description="Register employees and map them to a role to prepare onboarding plan generation."
        actions={
          <Button variant="primary" icon={UserCheck} disabled={roles.length === 0} onClick={() => { setError(null); setFormOpen(true); }}>
            Register employee
          </Button>
        }
      />

      {error && !formOpen && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}

      {newCredentials && (
        <Alert tone="success" title={`${newCredentials.name}'s login was created`} onDismiss={() => setNewCredentials(null)}>
          <p>Share these now — the password won&apos;t be shown again.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code className="rounded-md border border-line bg-canvas px-2.5 py-1 text-[12.5px] text-slate-200 text-break">{newCredentials.email}</code>
            <code className="rounded-md border border-line bg-canvas px-2.5 py-1 text-[12.5px] text-slate-200">{newCredentials.password}</code>
            <Button size="sm" variant="secondary" icon={copied ? Check : Copy} onClick={copyCredentials}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </Alert>
      )}

      {roles.length === 0 && (
        <Alert tone="warning">No roles exist yet. Create a role in the Roles section before registering employees.</Alert>
      )}

      <div>
        <Card padded={false} className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <CardHeader icon={Users} title="Directory" description={`${employees.length} employees`} />
            <SearchInput
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search name, code, role"
              className="w-full sm:w-64"
            />
          </div>

          <div className="table-wrap border-t border-line">
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th className="hidden md:table-cell">Role</th>
                  <th className="hidden sm:table-cell">Experience</th>
                  <th className="hidden lg:table-cell">Joined</th>
                  <th className="w-12"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <motion.tbody key={pager.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                {pager.pageItems.length === 0 ? (
                  <tr>
                    <td colSpan="5">
                      <EmptyState
                        icon={Users}
                        title={searchQuery ? 'No matching employees' : 'No employees registered yet'}
                        description={searchQuery ? 'Try a different search term.' : 'Register the first employee with the form.'}
                      />
                    </td>
                  </tr>
                ) : (
                  pager.pageItems.map((emp) => (
                    <tr key={emp.id}>
                      <td className="min-w-[180px]">
                        <p className="font-medium text-slate-100 text-break">{emp.full_name}</p>
                        <p className="code-tag mt-0.5 !text-[11.5px]">{emp.employee_code}</p>
                        <p className="mt-0.5 text-[12px] text-subtle md:hidden">{getRoleName(emp.role_id)} · {emp.department}</p>
                      </td>
                      <td className="hidden md:table-cell">
                        <p className="font-medium text-slate-200">{getRoleName(emp.role_id)}</p>
                        <p className="text-[12px] text-subtle">{emp.department}</p>
                      </td>
                      <td className="hidden sm:table-cell"><Badge>{emp.experience_level}</Badge></td>
                      <td className="hidden whitespace-nowrap text-muted lg:table-cell">
                        {emp.joining_date ? new Date(emp.joining_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="text-right">
                        <IconButton
                          label={`Delete ${emp.full_name}`}
                          icon={Trash2}
                          danger
                          size={15}
                          onClick={() => ask({
                            title: 'Delete employee?',
                            message: `${emp.full_name} (${emp.employee_code}) will be removed from the directory.`,
                            confirmLabel: 'Delete employee',
                            onConfirm: () => handleDelete(emp.id),
                          })}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </motion.tbody>
            </table>
          </div>

          <Pagination {...pager} onPageChange={pager.setPage} noun="employees" />
        </Card>
      </div>

      <Modal
        open={formOpen}
        onClose={() => !isSaving && setFormOpen(false)}
        icon={UserCheck}
        title="Register employee"
        subtitle="A login is created automatically; the temporary password is shown once."
      >
        <form onSubmit={async (e) => { if (await handleSubmit(e)) setFormOpen(false); }} className="space-y-4">
            {error && <Alert tone="danger">{error}</Alert>}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Employee ID" htmlFor="emp-code">
                <input
                  id="emp-code" type="text" required placeholder="EMP-001"
                  value={formData.employee_code}
                  onChange={(e) => setFormData({ ...formData, employee_code: e.target.value })}
                  className="input"
                />
              </Field>

              <Field label="Full name" htmlFor="emp-name">
                <input
                  id="emp-name" type="text" required placeholder="John Doe"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="input"
                />
              </Field>
            </div>

            <Field label="Email" htmlFor="emp-email" hint="Also becomes their login.">
              <input
                id="emp-email" type="email" required placeholder="jane.doe@company.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="input"
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Department" htmlFor="emp-dept">
                <select
                  id="emp-dept"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="select"
                >
                  <option>Engineering</option>
                  <option>HR</option>
                  <option>Finance</option>
                  <option>IT</option>
                  <option>Customer Support</option>
                  <option>Sales</option>
                </select>
              </Field>
              <Field label="Experience" htmlFor="emp-exp">
                <select
                  id="emp-exp"
                  value={formData.experience_level}
                  onChange={(e) => setFormData({ ...formData, experience_level: e.target.value })}
                  className="select"
                >
                  <option>Beginner</option>
                  <option>Intermediate</option>
                  <option>Advanced</option>
                </select>
              </Field>
            </div>

            <Field label="Role" htmlFor="emp-role">
              <select
                id="emp-role"
                required value={formData.role_id}
                onChange={(e) => setFormData({ ...formData, role_id: e.target.value })}
                className="select"
              >
                <option value="" disabled>Select a role…</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>{r.role_name}</option>
                ))}
              </select>
            </Field>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Reporting manager" htmlFor="emp-manager">
                <input
                  id="emp-manager" type="text" placeholder="e.g. Sarah Ahmed"
                  value={formData.reporting_manager}
                  onChange={(e) => setFormData({ ...formData, reporting_manager: e.target.value })}
                  className="input"
                />
              </Field>

              <Field label="Joining date" htmlFor="emp-date">
                <input
                  id="emp-date" type="date" required
                  value={formData.joining_date}
                  onChange={(e) => setFormData({ ...formData, joining_date: e.target.value })}
                  className="input"
                />
              </Field>
            </div>

            {/* Optional profile inputs used by the GenAI prompt (SRS employee profile) */}
            <Field label="Required competencies (optional)" htmlFor="emp-comp">
              <textarea
                id="emp-comp" rows={2} placeholder="e.g. Incident triage, customer escalation handling"
                value={formData.required_competencies}
                onChange={(e) => setFormData({ ...formData, required_competencies: e.target.value })}
                className="input !h-auto py-2"
              />
            </Field>
            <Field label="Previous experience (optional)" htmlFor="emp-prev">
              <textarea
                id="emp-prev" rows={2} placeholder="e.g. 2 years in a support desk role"
                value={formData.previous_experience}
                onChange={(e) => setFormData({ ...formData, previous_experience: e.target.value })}
                className="input !h-auto py-2"
              />
            </Field>

            <div className="flex flex-wrap justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={isSaving}>Cancel</Button>
              <Button type="submit" variant="primary" loading={isSaving} disabled={roles.length === 0}>
                {isSaving ? 'Saving…' : 'Register employee'}
              </Button>
            </div>
          </form>
      </Modal>

      {dialog}
    </div>
  );
};

export default EmployeeManager;