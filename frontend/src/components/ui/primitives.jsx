import React from 'react';
import { motion } from 'framer-motion';
import { AlertCircle, CheckCircle2, Info, Loader2, Search, TriangleAlert, X } from 'lucide-react';
import { SpotlightCard } from './SpotlightCard';

/* ==========================================================================
   Shared UI primitives. Pure presentation — no data fetching, no business
   logic. Styling classes (.btn, .card, .badge, .input …) live in index.css.
   ========================================================================== */

export const ease = [0.22, 1, 0.36, 1];

export const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28, ease } },
};

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

/* ------------------------------------------------------------- Button */
export const Button = React.forwardRef(function Button(
  { variant = 'secondary', size, loading = false, icon: Icon, iconRight: IconRight, block, className = '', children, disabled, type = 'button', ...rest },
  ref
) {
  const cls = [
    'btn',
    `btn-${variant}`,
    size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : '',
    block ? 'btn-block' : '',
    className,
  ].join(' ');
  const iconSize = size === 'sm' ? 14 : 16;
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Loader2 size={iconSize} className="animate-spin" /> : Icon ? <Icon size={iconSize} /> : null}
      {children}
      {!loading && IconRight ? <IconRight size={iconSize} /> : null}
    </button>
  );
});

export const IconButton = ({ label, icon: Icon, danger, className = '', size = 16, ...rest }) => (
  <button type="button" aria-label={label} title={label} className={`btn btn-icon ${danger ? 'danger' : ''} ${className}`} {...rest}>
    <Icon size={size} />
  </button>
);

/* -------------------------------------------------------------- Badge */
export const Badge = ({ tone = 'neutral', dot = false, className = '', children, title }) => (
  <span className={`badge badge-${tone} ${className}`} title={title}>
    {dot && <span className="dot" />}
    <span className="truncate">{children}</span>
  </span>
);

const STATUS_TONES = {
  success: ['Verified', 'Approved', 'Completed', 'Active', 'Match', 'passed', 'online'],
  warning: [
    'Verified with Warning', 'Partially Verified', 'Needs Regeneration', 'Pending', 'In Progress',
    'Manual Review Required', 'Source Support Missing', 'Outdated Source', 'warning', 'Medium',
  ],
  danger: [
    'Unsupported', 'Unsupported Requirement', 'Contradictory', 'Contradiction Detected', 'Rejected',
    'Requirement Missing', 'Incomplete', 'Mismatch', 'Failed', 'failed', 'High', 'offline',
  ],
  info: ['Pending Review'],
};

export const statusTone = (status) => {
  if (!status) return 'neutral';
  for (const [tone, list] of Object.entries(STATUS_TONES)) {
    if (list.includes(status)) return tone;
  }
  return 'neutral';
};

/** Visual only — renders whatever status string the backend sent, unchanged. */
export const StatusBadge = ({ status, fallback = 'Pending', className = '' }) => (
  <Badge tone={statusTone(status)} dot className={className}>{status || fallback}</Badge>
);

/* --------------------------------------------------------------- Card */
export const Card = ({ className = '', padded = true, children, as: Tag = 'section', ...rest }) => (
  <Tag className={`card ${padded ? 'p-5 sm:p-6' : ''} ${className}`} {...rest}>{children}</Tag>
);

export const CardHeader = ({ title, description, icon: Icon, actions, className = '' }) => (
  <div className={`flex flex-wrap items-start justify-between gap-3 ${className}`}>
    <div className="min-w-0 flex items-start gap-3">
      {Icon && (
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-surface-2 text-slate-300">
          <Icon size={16} />
        </span>
      )}
      <div className="min-w-0">
        <h3 className="text-[14.5px] font-semibold text-fg">{title}</h3>
        {description && <p className="mt-0.5 text-[13px] text-muted text-break">{description}</p>}
      </div>
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

/* -------------------------------------------------------- Page header */
export const PageHeader = ({ title, description, actions, eyebrow }) => (
  <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-6 flex flex-wrap items-end justify-between gap-4 sm:mb-8">
    <div className="min-w-0 flex-1 basis-[320px]">
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <h1 className="text-[22px] font-semibold tracking-tight text-fg sm:text-[24px]">{title}</h1>
      {description && <p className="mt-1.5 max-w-3xl text-[14px] leading-relaxed text-muted text-break">{description}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </motion.div>
);

/* -------------------------------------------------------------- Alert */
const ALERT_ICONS = { danger: AlertCircle, success: CheckCircle2, warning: TriangleAlert, info: Info };

export const Alert = ({ tone = 'info', title, children, onDismiss, className = '' }) => {
  const Icon = ALERT_ICONS[tone] || Info;
  return (
    <motion.div
      role={tone === 'danger' ? 'alert' : 'status'}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease }}
      className={`alert alert-${tone} ${className}`}
    >
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 text-break">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div>}
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="-m-1 rounded-md p-1 opacity-70 hover:opacity-100">
          <X size={14} />
        </button>
      )}
    </motion.div>
  );
};

/* ----------------------------------------------- Empty / loading state */
export const EmptyState = ({ icon: Icon, title, description, action, className = '' }) => (
  <div className={`flex flex-col items-center justify-center px-6 py-12 text-center ${className}`}>
    {Icon && (
      <span className="mb-3 grid size-10 place-items-center rounded-xl border border-line bg-surface-2 text-subtle">
        <Icon size={18} />
      </span>
    )}
    <p className="text-[14px] font-medium text-slate-200">{title}</p>
    {description && <p className="mt-1 max-w-sm text-[13px] text-subtle text-break">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const Spinner = ({ size = 16, className = '' }) => (
  <Loader2 size={size} className={`animate-spin text-subtle ${className}`} aria-hidden="true" />
);

export const LoadingState = ({ label = 'Loading…', className = '' }) => (
  <div role="status" className={`flex items-center justify-center gap-2 py-10 text-[13px] text-subtle ${className}`}>
    <Spinner /> <span>{label}</span>
  </div>
);

export const Skeleton = ({ className = '' }) => <div className={`skeleton ${className}`} aria-hidden="true" />;

export const SkeletonRows = ({ rows = 4 }) => (
  <div className="space-y-3 p-5" aria-hidden="true">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex items-center gap-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 flex-1" />
        <Skeleton className="h-4 w-16" />
      </div>
    ))}
  </div>
);

/* --------------------------------------------------------------- Form */
export const Field = ({ label, htmlFor, hint, children, className = '' }) => (
  <div className={`min-w-0 ${className}`}>
    {label && <label htmlFor={htmlFor} className="field-label">{label}</label>}
    {children}
    {hint && <p className="field-hint">{hint}</p>}
  </div>
);

export const SearchInput = ({ value, onChange, placeholder = 'Search…', label = 'Search', className = '' }) => (
  <div className={`relative min-w-0 ${className}`}>
    <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
    <input
      type="search"
      aria-label={label}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="input !h-9 !pl-9 !text-[13px]"
    />
    {value && (
      <button
        type="button"
        onClick={() => onChange({ target: { value: '' } })}
        aria-label="Clear search"
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-subtle hover:text-fg"
      >
        <X size={13} />
      </button>
    )}
  </div>
);

/* ---------------------------------------------------------- Stat card */
export const StatCard = ({ label, value, meta, icon: Icon, onClick }) => {
  const interactive = typeof onClick === 'function';
  const body = (
    <>
      <div className="relative flex items-center justify-between">
        <span className="text-[12.5px] font-medium text-muted">{label}</span>
        {Icon && <Icon size={16} className="text-subtle" />}
      </div>
      <div className="relative mt-3 text-[28px] font-semibold leading-none tracking-tight text-fg tabular-nums">{value}</div>
      {meta && <p className="relative mt-2 text-[12.5px] text-subtle">{meta}</p>}
    </>
  );
  if (!interactive) return <div className="card p-5">{body}</div>;
  return (
    <SpotlightCard
      as="button"
      type="button"
      onClick={onClick}
      className="card w-full p-5 text-left transition-colors hover:border-line-strong"
    >
      {body}
    </SpotlightCard>
  );
};

/* ---------------------------------------------------- Segmented tabs */
export const Tabs = ({ tabs, active, onChange, layoutId = 'tabs', className = '' }) => (
  <div role="tablist" className={`flex min-w-0 gap-1 overflow-x-auto rounded-xl border border-line bg-surface-2 p-1 ${className}`}>
    {tabs.map(({ key, label, icon: Icon, count }) => {
      const isActive = active === key;
      return (
        <button
          key={key}
          role="tab"
          type="button"
          aria-selected={isActive}
          onClick={() => onChange(key)}
          className={`relative flex shrink-0 grow items-center justify-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors sm:px-3 ${
            isActive ? 'text-fg' : 'text-muted hover:text-slate-200'
          }`}
        >
          {isActive && (
            <motion.span
              layoutId={layoutId}
              className="absolute inset-0 rounded-lg border border-line-strong bg-surface-3"
              transition={{ duration: 0.25, ease }}
            />
          )}
          <span className="relative flex items-center gap-2">
            {Icon && <Icon size={14} />}
            {label}
            {count !== undefined && <span className="hidden text-[11.5px] tabular-nums text-subtle min-[360px]:inline">{count}</span>}
          </span>
        </button>
      );
    })}
  </div>
);

/* ---------------------------------------------------- Score / meter */
export const ScoreMeter = ({ label, value }) => {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const color = pct >= 80 ? 'bg-emerald-400/80' : pct >= 60 ? 'bg-amber-400/80' : 'bg-rose-400/80';
  return (
    <div className="card-inset min-w-0 px-3 py-3 sm:px-3.5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-2">
        <span className="truncate text-[12px] font-medium text-muted">{label}</span>
        <span className="text-[15px] font-semibold tabular-nums text-fg">{pct}%</span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/5" role="meter" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease }}
        />
      </div>
    </div>
  );
};

/** Parses an axios error into the backend's own message (never hides it). */
export const errorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail || fallback;
  return typeof detail === 'string' ? detail : JSON.stringify(detail);
};
