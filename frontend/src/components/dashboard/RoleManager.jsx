import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, Briefcase, Trash2 } from 'lucide-react';
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, IconButton, PageHeader, SearchInput } from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';
import { useConfirm } from '../ui/ConfirmDialog';
import { Modal } from '../ui/Modal';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   RoleManager Component — REAL backend connection
   Calls: POST /roles/ , GET /roles/ , DELETE /roles/{id}
   ========================================================================== */
export const RoleManager = ({ roles, refreshRoles }) => {
  const [formData, setFormData] = useState({ role_name: '', department: 'Engineering', description: '' });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);

    try {
      await apiClient.post('/roles/', formData);
      setFormData({ role_name: '', department: 'Engineering', description: '' });
      await refreshRoles();
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create role.';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (roleId) => {
    try {
      await apiClient.delete(`/roles/${roleId}`);
      await refreshRoles();
    } catch (err) {
      setError('Failed to delete role — it may still be assigned to employees.');
    }
  };

  const [searchQuery, setSearchQuery] = useState('');
  const { ask, dialog } = useConfirm();
  const [formOpen, setFormOpen] = useState(false);

  const filteredRoles = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return roles.filter(
      (r) =>
        (r.role_name || '').toLowerCase().includes(q) ||
        (r.department || '').toLowerCase().includes(q) ||
        (r.description || '').toLowerCase().includes(q)
    );
  }, [roles, searchQuery]);

  const pager = usePagination(filteredRoles, { pageSize: 8, resetKey: searchQuery });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles"
        description="Job roles used across the Requirement Matrix and onboarding plans."
        actions={<Button variant="primary" icon={Plus} onClick={() => { setError(null); setFormOpen(true); }}>Create role</Button>}
      />

      {error && !formOpen && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}

      <div>
        <Card padded={false} className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <CardHeader icon={Briefcase} title="All roles" description={`${roles.length} in database`} />
            <SearchInput
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search roles"
              className="w-full sm:w-64"
            />
          </div>

          <div className="table-wrap border-t border-line">
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th className="hidden sm:table-cell">Department</th>
                  <th className="hidden lg:table-cell">Description</th>
                  <th className="w-12"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <motion.tbody key={pager.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                {pager.pageItems.length === 0 ? (
                  <tr>
                    <td colSpan="4">
                      <EmptyState
                        icon={Briefcase}
                        title={searchQuery ? 'No matching roles' : 'No roles configured yet'}
                        description={searchQuery ? 'Try a different search term.' : 'Create the first role with the form.'}
                      />
                    </td>
                  </tr>
                ) : (
                  pager.pageItems.map((role) => (
                    <tr key={role.id}>
                      <td className="min-w-[180px]">
                        <p className="font-medium text-slate-100 text-break">{role.role_name}</p>
                        <p className="mt-0.5 text-[12px] text-subtle sm:hidden">{role.department}</p>
                        <p className="mt-0.5 line-clamp-2 text-[12.5px] text-muted lg:hidden">{role.description}</p>
                      </td>
                      <td className="hidden sm:table-cell"><Badge>{role.department}</Badge></td>
                      <td className="hidden max-w-md text-muted lg:table-cell">
                        <p className="line-clamp-2 text-break" title={role.description}>{role.description}</p>
                      </td>
                      <td className="text-right">
                        <IconButton
                          label={`Delete ${role.role_name}`}
                          icon={Trash2}
                          danger
                          size={15}
                          onClick={() => ask({
                            title: 'Delete role?',
                            message: `"${role.role_name}" will be removed. Roles still assigned to employees cannot be deleted.`,
                            confirmLabel: 'Delete role',
                            onConfirm: () => handleDelete(role.id),
                          })}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </motion.tbody>
            </table>
          </div>

          <Pagination {...pager} onPageChange={pager.setPage} noun="roles" />
        </Card>
      </div>

      <Modal
        open={formOpen}
        onClose={() => !isSaving && setFormOpen(false)}
        icon={Briefcase}
        title="Create role"
        size="sm"
      >
        <form onSubmit={async (e) => { if (await handleSubmit(e)) setFormOpen(false); }} className="space-y-4">
            {error && <Alert tone="danger">{error}</Alert>}
            <Field label="Role title" htmlFor="role-name">
              <input
                id="role-name" type="text" required placeholder="e.g. Customer Support Executive"
                value={formData.role_name}
                onChange={(e) => setFormData({ ...formData, role_name: e.target.value })}
                className="input"
              />
            </Field>

            <Field label="Department" htmlFor="role-dept">
              <select
                id="role-dept"
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
                <option>Marketing</option>
                <option>Operations</option>
              </select>
            </Field>

            <Field label="Description" htmlFor="role-desc">
              <textarea
                id="role-desc" required placeholder="Brief responsibilities and scope…" rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="textarea"
              />
            </Field>

            <div className="flex flex-wrap justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={isSaving}>Cancel</Button>
              <Button type="submit" variant="primary" loading={isSaving}>
                {isSaving ? 'Saving…' : 'Save role'}
              </Button>
            </div>
          </form>
      </Modal>

      {dialog}
    </div>
  );
};

export default RoleManager;