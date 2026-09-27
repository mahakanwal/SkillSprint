import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { AdminDashboard } from './components/dashboard/AdminDashboard';
import { ReviewerDashboard } from './components/dashboard/ReviewerDashboard';
import { ManagerDashboard } from './components/dashboard/ManagerDashboard';
import { EmployeeDashboard } from './components/dashboard/EmployeeDashboard';
import { Loader2 } from 'lucide-react';

/* ==========================================================================
   AppContent — routes to one of 5 role-specific dashboards based on the
   logged-in user's real `role` (from the JWT / GET /auth/me), not a guess.

     admin             -> AdminDashboard      (full access)
     training_manager   -> AdminDashboard      (same permissions as admin on
                                                 the backend, minus staff-login
                                                 creation -- AdminDashboard's
                                                 "Team Access" tab is hidden
                                                 for this role, see below)
     reviewer           -> ReviewerDashboard   (read-only: review generated
                                                 plans + validation results)
     manager            -> ManagerDashboard    (read-only: their direct
                                                 reports' onboarding progress)
     employee            -> EmployeeDashboard   (their own onboarding plan)
   ========================================================================== */
function AppContent() {
  const { isAuthenticated, isLoading, role, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center" role="status" aria-label="Loading">
        <div className="app-backdrop" aria-hidden="true" />
        <Loader2 size={22} className="relative animate-spin text-subtle" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  switch (role) {
    case 'admin':
      return <AdminDashboard onLogout={logout} viewerRole="admin" />;
    case 'training_manager':
      return <AdminDashboard onLogout={logout} viewerRole="training_manager" />;
    case 'reviewer':
      return <ReviewerDashboard onLogout={logout} />;
    case 'manager':
      return <ManagerDashboard onLogout={logout} />;
    case 'employee':
      return <EmployeeDashboard onLogout={logout} />;
    default:
      return (
        <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
          <div className="app-backdrop" aria-hidden="true" />
          <p className="relative text-[14px] text-muted">Unrecognized role &ldquo;{role || 'none'}&rdquo; — contact your admin.</p>
          <button type="button" onClick={logout} className="btn btn-secondary relative">Sign out</button>
        </div>
      );
  }
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
