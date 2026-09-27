import React, { useState } from 'react';
import { Mail, Lock, ChevronRight, RefreshCw, Cpu, AlertCircle } from 'lucide-react';
import apiClient from '../../api/apiClient';

/* ==========================================================================
   AuthPage — LOGIN ONLY. No public self-registration.
   This matches how a real company portal works: HR/Admin creates every
   account (an employee's login is created automatically when an admin
   registers them in Employee Manager; a training_manager/reviewer/manager/
   admin login is created by an existing admin via
   POST /auth/create-staff-login). Nobody signs themselves up, and nobody
   can pick their own role from a dropdown -- that was the security hole in
   the old version of this page.

   First-time setup: if NO account exists at all yet, call
   POST /auth/bootstrap-first-admin once (e.g. from Swagger at /docs) to
   create account #1 as admin. After that this endpoint refuses forever.
   ========================================================================== */
export const AuthPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const res = await apiClient.post('/auth/login', { email, password });
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('role', res.data.user.role);
      localStorage.setItem('user_id', String(res.data.user.id));
      onLogin(res.data.user.role);
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check your email and password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="p-8">
          <div className="flex justify-center mb-6">
            <div className="w-14 h-14 bg-teal-500/10 border border-teal-500/30 rounded-2xl flex items-center justify-center text-teal-400 shadow-inner">
              <Cpu size={28} />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-center text-slate-100 tracking-tight">SkillSprint AI</h2>
          <p className="text-center text-slate-400 text-sm mt-1 mb-6">Sign in with the email &amp; password your admin gave you</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Email Address</label>
              <div className="relative">
                <Mail size={18} className="absolute left-3.5 top-3 text-slate-500" />
                <input
                  type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-colors"
                  placeholder="you@company.com"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Password</label>
              <div className="relative">
                <Lock size={18} className="absolute left-3.5 top-3 text-slate-500" />
                <input
                  type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-colors"
                  placeholder="••••••••"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-start space-x-2 bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 text-rose-400 text-xs">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit" disabled={isLoading}
              className="w-full bg-teal-600 hover:bg-teal-500 text-white font-medium py-2.5 rounded-xl transition-all shadow-lg shadow-teal-950/50 flex items-center justify-center space-x-2 mt-2"
            >
              {isLoading ? <RefreshCw size={18} className="animate-spin" /> : (
                <>
                  <span>Sign In</span>
                  <ChevronRight size={18} />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-slate-600 text-[11px] mt-6">
            Don't have an account? Ask your admin to create one — accounts aren't self-registered.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AuthPage;
