import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText, Briefcase, Users, Settings, BarChart3, ListChecks, Sparkles, UserCog, Search, FileBarChart, PieChart,
} from 'lucide-react';

import apiClient from '../../api/apiClient';

import { AnalyticsDashboard } from './AnalyticsDashboard';
import { DocumentUpload } from './DocumentUpload';
import { RoleManager } from './RoleManager';
import { EmployeeManager } from './EmployeeManager';
import { RequirementMatrixManager } from './RequirementMatrixManager';
import { OnboardingManager } from './OnboardingManager';
import { StaffAccessManager } from './StaffAccessManager';
import { SettingsView } from './SettingsView';
import { RoleOverview } from './RoleOverview';
import { PlansExplorer } from './PlansExplorer';
import { ReportsView } from './ReportsView';
import { AppShell } from '../ui/AppShell';
import { Alert, Badge } from '../ui/primitives';

/* ==========================================================================
   AdminDashboard — shared shell for BOTH "admin" and "training_manager"
   roles (the backend gives them near-identical permissions already). The
   `viewerRole` prop only controls which NAV ITEMS are shown client-side —
   the backend independently enforces the real access control on every
   request regardless of what the UI displays, so this is a UX convenience,
   not the security boundary.
   ========================================================================== */
export const AdminDashboard = ({ onLogout, viewerRole = 'admin' }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [documents, setDocuments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [apiStatus, setApiStatus] = useState('checking');
  const [loadError, setLoadError] = useState(null);
  const [focusEmployeeId, setFocusEmployeeId] = useState('');

  const refreshDocuments = useCallback(async () => {
    const res = await apiClient.get('/documents/list');
    setDocuments(res.data);
  }, []);

  const refreshRoles = useCallback(async () => {
    const res = await apiClient.get('/roles/');
    setRoles(res.data);
  }, []);

  const refreshEmployees = useCallback(async () => {
    const res = await apiClient.get('/employees/');
    setEmployees(res.data);
  }, []);

  const refreshRequirements = useCallback(async () => {
    const res = await apiClient.get('/requirements/');
    setRequirements(res.data);
  }, []);

  const loadAll = useCallback(async () => {
    setLoadError(null);
    try {
      await Promise.all([refreshDocuments(), refreshRoles(), refreshEmployees(), refreshRequirements()]);
      setApiStatus('online');
    } catch (error) {
      console.error(error);
      setApiStatus('offline');
      setLoadError('Could not connect to backend.');
    }
  }, [refreshDocuments, refreshRoles, refreshEmployees, refreshRequirements]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <AnalyticsDashboard
            documentsCount={documents.length}
            rolesCount={roles.length}
            employeesCount={employees.length}
            requirementsCount={requirements.length}
            isLoading={apiStatus === 'checking'}
            onNavigate={setActiveTab}
          />
        );
      case 'documents':
        return <DocumentUpload documents={documents} refreshDocuments={refreshDocuments} roles={roles} refreshRequirements={refreshRequirements} />;
      case 'roles':
        return <RoleManager roles={roles} refreshRoles={refreshRoles} />;
      case 'employees':
        return <EmployeeManager employees={employees} roles={roles} refreshEmployees={refreshEmployees} />;
      case 'requirements':
        return (
          <RequirementMatrixManager
            requirements={requirements} roles={roles} documents={documents}
            refreshRequirements={refreshRequirements}
          />
        );
      case 'onboarding':
        return <OnboardingManager employees={employees} initialEmployeeId={focusEmployeeId} />;
      case 'plans':
        return (
          <PlansExplorer
            roles={roles}
            onOpenPlan={(row) => { setFocusEmployeeId(String(row.employee_id)); setActiveTab('onboarding'); }}
          />
        );
      case 'role-dashboard':
        return <RoleOverview />;
      case 'reports':
        return <ReportsView />;
      case 'team-access':
        return <StaffAccessManager />;
      case 'settings':
        return <SettingsView />;
      default:
        return null;
    }
  };

  const allNavItems = [
    { key: 'overview', label: 'Overview', icon: BarChart3, roles: ['admin', 'training_manager'], group: 'Workspace' },
    { key: 'documents', label: 'Document Pipeline', icon: FileText, roles: ['admin', 'training_manager'], group: 'Knowledge', badge: documents.length },
    { key: 'requirements', label: 'Requirement Matrix', icon: ListChecks, roles: ['admin', 'training_manager'], group: 'Knowledge', badge: requirements.length },
    { key: 'roles', label: 'Roles', icon: Briefcase, roles: ['admin', 'training_manager'], group: 'People', badge: roles.length },
    { key: 'employees', label: 'Employees', icon: Users, roles: ['admin', 'training_manager'], group: 'People', badge: employees.length },
    { key: 'onboarding', label: 'Onboarding Pipeline', icon: Sparkles, roles: ['admin', 'training_manager'], group: 'Onboarding' },
    { key: 'plans', label: 'Plans & Search', icon: Search, roles: ['admin', 'training_manager'], group: 'Onboarding' },
    { key: 'role-dashboard', label: 'Role Dashboard', icon: PieChart, roles: ['admin', 'training_manager'], group: 'Insights' },
    { key: 'reports', label: 'Reports', icon: FileBarChart, roles: ['admin', 'training_manager'], group: 'Insights' },
    { key: 'team-access', label: 'Team Access', icon: UserCog, roles: ['admin'], group: 'Administration' },
    { key: 'settings', label: 'System Settings', icon: Settings, roles: ['admin', 'training_manager'], group: 'Administration' },
  ];

  const navItems = allNavItems.filter((item) => item.roles.includes(viewerRole));

  // Group nav items for the sidebar, keeping their original order.
  const navGroups = navItems.reduce((groups, item) => {
    const last = groups[groups.length - 1];
    if (last && last.label === item.group) last.items.push(item);
    else groups.push({ label: item.group, items: [item] });
    return groups;
  }, []);

  const activeLabel = navItems.find((n) => n.key === activeTab)?.label || '';

  const statusBadge = (
    <Badge
      tone={apiStatus === 'online' ? 'success' : apiStatus === 'offline' ? 'danger' : 'neutral'}
      dot
      title="FastAPI backend connection"
    >
      {apiStatus === 'online' ? 'API online' : apiStatus === 'offline' ? 'API offline' : 'Connecting'}
    </Badge>
  );

  return (
    <AppShell
      portalLabel={viewerRole === 'admin' ? 'Admin Portal' : 'Training Manager Portal'}
      navGroups={navGroups}
      activeKey={activeTab}
      onNavigate={setActiveTab}
      onLogout={onLogout}
      pageTitle={activeLabel}
      headerRight={statusBadge}
    >
      {loadError && (
        <Alert
          tone="danger"
          className="mb-6"
          title={loadError}
          onDismiss={() => setLoadError(null)}
        >
          <button type="button" onClick={loadAll} className="mt-1 text-[12.5px] font-semibold underline underline-offset-2">
            Retry
          </button>
        </Alert>
      )}
      {renderContent()}
    </AppShell>
  );
};

export default AdminDashboard;
