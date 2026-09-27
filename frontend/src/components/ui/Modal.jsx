import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { ease } from './primitives';

/* ==========================================================================
   Modal — accessible dialog.
   - Esc, the close button, or a click on the backdrop closes it
   - focus moves into the dialog and returns to the trigger on close
   - background scrolling is locked while open
   - content taller than the viewport scrolls INSIDE the dialog
   ========================================================================== */
export const Modal = ({ open, onClose, title, subtitle, icon: Icon, size = 'lg', footer, children }) => {
  const panelRef = useRef(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    const t = setTimeout(() => panelRef.current?.focus(), 30);
    return () => {
      clearTimeout(t);
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') previouslyFocused.focus();
    };
  }, [open, onClose]);

  const width = size === 'sm' ? 'max-w-md' : size === 'xl' ? 'max-w-4xl' : 'max-w-3xl';

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="modal"
          className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <div className="absolute inset-0 bg-black/65 backdrop-blur-[2px]" onClick={onClose} aria-hidden="true" />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ opacity: 0, y: 12, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.99 }}
            transition={{ duration: 0.22, ease }}
            className={`relative flex max-h-[calc(100dvh-24px)] w-full ${width} flex-col overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-[var(--shadow-pop)] outline-none sm:max-h-[85dvh]`}
          >
            <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
              <div className="flex min-w-0 items-start gap-3">
                {Icon && (
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-surface-2 text-slate-300">
                    <Icon size={16} />
                  </span>
                )}
                <div className="min-w-0">
                  <h2 id={titleId} className="text-[15px] font-semibold text-fg text-break">{title}</h2>
                  {subtitle && <p className="mt-0.5 text-[13px] leading-relaxed text-muted text-break">{subtitle}</p>}
                </div>
              </div>
              <button type="button" onClick={onClose} aria-label="Close dialog" className="btn btn-icon -mr-1 shrink-0">
                <X size={16} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-5">{children}</div>
            {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default Modal;
