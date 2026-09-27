import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Cpu, LogOut, Menu, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { ease } from './primitives';

/* ==========================================================================
   AppShell — the dashboard frame shared by every role.

   Layout: [ fixed sidebar ][ header + independently scrolling content ]
   - The shell is exactly one viewport tall (h-dvh, overflow hidden), so the
     browser page itself never scrolls; only <main> scrolls vertically.
   - Desktop (>= 1024px): persistent sidebar.
   - Tablet / mobile (< 1024px): sidebar becomes a slide-in drawer.

   Navigation is still plain local state owned by each dashboard (the app
   has no router) — the shell only renders the items it is given and calls
   onNavigate(key), exactly like the old sidebar buttons did.
   ========================================================================== */

const ROLE_LABELS = {
  admin: 'Admin',
  training_manager: 'Training Manager',
  reviewer: 'Reviewer',
  manager: 'Manager',
  employee: 'Employee',
};

const initials = (name = '') =>
  name.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('') || 'U';

const NavList = ({ groups, activeKey, onSelect, layoutId }) => (
  <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
    {groups.map((group) => (
      <div key={group.label || 'main'}>
        {group.label && <p className="eyebrow mb-1.5 px-2.5">{group.label}</p>}
        <ul className="space-y-0.5">
          {group.items.map(({ key, label, icon: Icon, badge }) => {
            const active = key === activeKey;
            return (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => onSelect(key)}
                  aria-current={active ? 'page' : undefined}
                  className={`relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-left text-[13.5px] font-medium transition-colors ${
                    active ? 'text-fg' : 'text-muted hover:bg-white/[0.035] hover:text-slate-200'
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId={layoutId}
                      className="absolute inset-0 rounded-lg border border-line bg-white/[0.055]"
                      transition={{ duration: 0.25, ease }}
                    />
                  )}
                  <Icon size={16} className={`relative shrink-0 ${active ? 'text-accent' : ''}`} />
                  <span className="relative min-w-0 flex-1 truncate">{label}</span>
                  {badge !== undefined && badge !== null && (
                    <span className="relative text-[11.5px] tabular-nums text-subtle">{badge}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    ))}
  </nav>
);

const SidebarBody = ({ portalLabel, groups, activeKey, onSelect, onLogout, layoutId, onClose }) => {
  const { user, role } = useAuth();
  const name = user?.username || user?.email || 'Signed in';
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-line px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-line-strong bg-gradient-to-b from-white/10 to-white/[0.02] text-accent">
            <Cpu size={16} />
          </span>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-[14px] font-semibold text-fg">SkillSprint AI</p>
            <p className="truncate text-[11.5px] text-subtle">{portalLabel}</p>
          </div>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close navigation" className="btn btn-icon">
            <X size={16} />
          </button>
        )}
      </div>

      <NavList groups={groups} activeKey={activeKey} onSelect={onSelect} layoutId={layoutId} />

      <div className="shrink-0 border-t border-line p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <span className="grid size-8 shrink-0 place-items-center rounded-full border border-line-strong bg-surface-3 text-[12px] font-semibold text-slate-200">
            {initials(name)}
          </span>
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-[13px] font-medium text-slate-200">{name}</p>
            <p className="truncate text-[11.5px] text-subtle">{ROLE_LABELS[role] || role || ''}</p>
          </div>
          <button type="button" onClick={onLogout} aria-label="Sign out" title="Sign out" className="btn btn-icon danger">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

export const AppShell = ({ portalLabel, navGroups, activeKey, onNavigate, onLogout, pageTitle, headerRight, children }) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const mainRef = useRef(null);

  // New section -> start at the top of the content area.
  useEffect(() => { mainRef.current?.scrollTo({ top: 0 }); }, [activeKey]);

  // Close the drawer with Esc, and automatically when resized to desktop.
  useEffect(() => {
    if (!drawerOpen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setDrawerOpen(false); };
    const mq = window.matchMedia('(min-width: 1024px)');
    const onMq = () => { if (mq.matches) setDrawerOpen(false); };
    window.addEventListener('keydown', onKey);
    mq.addEventListener?.('change', onMq);
    return () => {
      window.removeEventListener('keydown', onKey);
      mq.removeEventListener?.('change', onMq);
    };
  }, [drawerOpen]);

  const select = (key) => {
    onNavigate(key);
    setDrawerOpen(false);
  };

  return (
    <div className="relative flex h-dvh w-full overflow-hidden text-fg">
      <div className="app-backdrop" aria-hidden="true" />

      {/* Desktop sidebar */}
      <aside className="relative z-10 hidden w-[248px] shrink-0 border-r border-line bg-surface/70 backdrop-blur-sm lg:block">
        <SidebarBody
          portalLabel={portalLabel}
          groups={navGroups}
          activeKey={activeKey}
          onSelect={select}
          onLogout={onLogout}
          layoutId="nav-active-desktop"
        />
      </aside>

      {/* Tablet / mobile drawer */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              key="scrim"
              className="fixed inset-0 z-40 bg-black/60 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={() => setDrawerOpen(false)}
              aria-hidden="true"
            />
            <motion.aside
              key="drawer"
              role="dialog"
              aria-modal="true"
              aria-label="Navigation"
              className="fixed inset-y-0 left-0 z-50 w-[280px] max-w-[85vw] border-r border-line-strong bg-surface shadow-[var(--shadow-pop)] lg:hidden"
              initial={{ x: -24, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -24, opacity: 0 }}
              transition={{ duration: 0.22, ease }}
            >
              <SidebarBody
                portalLabel={portalLabel}
                groups={navGroups}
                activeKey={activeKey}
                onSelect={select}
                onLogout={onLogout}
                layoutId="nav-active-drawer"
                onClose={() => setDrawerOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Header + scrolling content */}
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas/60 px-4 backdrop-blur-sm sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            className="btn btn-icon -ml-1 lg:hidden"
          >
            <Menu size={18} />
          </button>
          <div className="flex min-w-0 flex-1 items-center gap-2 text-[13px]">
            <span className="hidden truncate text-subtle sm:inline">{portalLabel}</span>
            <span className="hidden text-slate-600 sm:inline" aria-hidden="true">/</span>
            <span className="truncate font-medium text-slate-200">{pageTitle}</span>
          </div>
          {headerRight && <div className="flex shrink-0 items-center gap-2">{headerRight}</div>}
        </header>

        <main ref={mainRef} className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeKey}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2, ease }}
              className="mx-auto w-full max-w-[1320px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};

export default AppShell;
