import React, { useState } from 'react';
import { TriangleAlert } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './primitives';

/* ==========================================================================
   ConfirmDialog + useConfirm — a small "are you sure?" step in front of
   destructive actions. The action itself is the SAME function that used to
   run directly on click; this only asks first.
   ========================================================================== */
export function useConfirm() {
  const [state, setState] = useState(null); // { title, message, confirmLabel, onConfirm }
  const [busy, setBusy] = useState(false);

  const ask = (opts) => setState(opts);
  const close = () => { if (!busy) setState(null); };

  const confirm = async () => {
    if (!state) return;
    setBusy(true);
    try {
      await state.onConfirm();
    } finally {
      setBusy(false);
      setState(null);
    }
  };

  const dialog = (
    <Modal
      open={!!state}
      onClose={close}
      size="sm"
      icon={TriangleAlert}
      title={state?.title || 'Are you sure?'}
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={busy}>Cancel</Button>
          <Button variant="danger" onClick={confirm} loading={busy}>{state?.confirmLabel || 'Delete'}</Button>
        </>
      }
    >
      <p className="text-[13.5px] leading-relaxed text-muted text-break">{state?.message}</p>
    </Modal>
  );

  return { ask, dialog };
}

export default useConfirm;
