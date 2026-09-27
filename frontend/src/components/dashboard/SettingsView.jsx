import React, { useEffect, useState } from 'react';
import { Server, Scale, FileCode2 } from 'lucide-react';
import apiClient from '../../api/apiClient';
import { Alert, Badge, Card, CardHeader, Field, LoadingState, PageHeader, errorMessage } from '../ui/primitives';

/* ==========================================================================
   SettingsView — read-only view of the configuration that drives the
   pipelines:
     - source precedence hierarchy  (config/policy_precedence.json, SRS 34)
     - versioned prompt templates    (prompt_templates/, SRS 40-41)
   Both are edited as files on the server, not from the browser.
   ========================================================================== */
export const SettingsView = () => {
  const [precedence, setPrecedence] = useState(null);
  const [prompts, setPrompts] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiClient.get('/documents/precedence').then((r) => setPrecedence(r.data.hierarchy)).catch((e) => setError(errorMessage(e, 'Could not load precedence rules.')));
    apiClient.get('/validation/prompt-versions').then((r) => setPrompts(r.data)).catch((e) => setError(errorMessage(e, 'Could not load prompt versions.')));
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader
        title="System settings"
        description={<>Backend and GenAI configuration is managed in the server&apos;s <code className="text-accent">.env</code> and configuration files.</>}
      />
      {error && <Alert tone="danger">{error}</Alert>}

      <Card>
        <CardHeader icon={Scale} title="Source precedence" description="When two sources disagree, the lower rank wins. Obsolete versions never win. Edit config/policy_precedence.json to change it." />
        {!precedence ? <LoadingState /> : (
          <ol className="mt-4 space-y-2">
            {precedence.map((h) => (
              <li key={h.rank} className="card-inset flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
                <span className="flex items-center gap-3 text-[13.5px] text-slate-100">
                  <span className="grid size-6 place-items-center rounded-md border border-line bg-surface-3 text-[12px] tabular-nums">{h.rank}</span>
                  {h.label}
                </span>
                <span className="flex flex-wrap gap-1">{(h.doc_types || []).map((t) => <Badge key={t}>{t}</Badge>)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card>
        <CardHeader icon={FileCode2} title="Prompt templates" description="Prompts live in prompt_templates/ and every plan records the version it was generated with." />
        {!prompts ? <LoadingState /> : (
          <div className="mt-4 space-y-3">
            {Object.entries(prompts.templates).map(([name, versions]) => (
              <div key={name} className="card-inset p-3.5">
                <p className="text-[13.5px] font-medium text-slate-100">{name}</p>
                <ul className="mt-2 space-y-1.5">
                  {Object.entries(versions).map(([v, meta]) => (
                    <li key={v} className="flex flex-wrap items-start gap-2 text-[12.5px]">
                      <Badge tone={prompts.active[name] === v ? 'success' : 'neutral'} dot>{v}{prompts.active[name] === v ? ' · active' : ''}</Badge>
                      <span className="min-w-0 flex-1 text-muted text-break">{meta.notes}</span>
                      <span className="font-mono text-[11.5px] text-subtle">{meta.system}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader icon={Server} title="Backend connection" description="The API this frontend talks to." />
        <div className="mt-5 space-y-3">
          <Field label="FastAPI backend URL" htmlFor="backend-url">
            <input id="backend-url" type="text" readOnly value="http://localhost:8000" className="input font-mono" />
          </Field>
          <p className="text-[13px] text-subtle">To change it, edit <code className="text-accent">src/api/apiClient.js</code> in the frontend project.</p>
        </div>
      </Card>
    </div>
  );
};

export default SettingsView;
