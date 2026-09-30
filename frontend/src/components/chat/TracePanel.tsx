// "Agent Trace" panel for reviewers: shows exactly what the backend did for the last
// reply: stage, extracted slots, every tool call, iterations, urgency provenance
// (rules vs LLM) and grounding violations. All values come from the API `trace`.

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Turn } from '../../api/types'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-100 py-1.5 dark:border-slate-800">
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-end font-medium text-slate-900 dark:text-slate-100">{children}</dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-4">
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h3>
      {children}
    </section>
  )
}

const Code = ({ children }: { children: ReactNode }) => (
  <pre dir="ltr" className="overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-100 p-2 text-start font-mono text-[11px] text-slate-800 dark:bg-slate-800 dark:text-slate-200">
    {children}
  </pre>
)

export default function TracePanel({ turn }: { turn: Turn | null }) {
  const { t } = useTranslation()
  if (!turn) return <p className="text-sm text-slate-500 dark:text-slate-400">{t('trace.empty')}</p>
  const { trace } = turn
  const stateEntries = Object.entries(trace.state ?? {})
  return (
    <div className="text-sm" data-testid="trace-panel">
      <p className="text-xs text-slate-500 dark:text-slate-400">{t('trace.subtitle')}</p>
      <dl className="mt-3">
        <Row label={t('trace.stage')}>{t(`stage.${trace.stage}`)}</Row>
        <Row label={t('trace.urgency')}>{t(`urgency.${turn.urgency}`)}</Row>
        <Row label={t('trace.source')}>{t(`trace.source_${turn.urgency_source}`)}</Row>
        <Row label={t('trace.rules')}>
          <span dir="ltr">{trace.rules.matched_flags.length ? trace.rules.matched_flags.join(', ') : t('trace.noFlags')}</span>
        </Row>
        <Row label={t('trace.llm')}>
          <span dir="ltr">{trace.llm_provider}{trace.llm_model ? ` · ${trace.llm_model}` : ''}</span>
        </Row>
        <Row label={t('trace.iterations')}>{trace.iterations}</Row>
        <Row label={t('trace.rounds')}>{trace.clarification_rounds}</Row>
        <Row label={t('trace.latency')}>{trace.latency_ms} ms</Row>
        <Row label={t('trace.outcome')}>
          <span dir="ltr">{trace.outcome}{trace.fallback_reason ? ` (${trace.fallback_reason})` : ''}</span>
        </Row>
      </dl>

      {turn.reasoning_summary && (
        <Section title={t('trace.reasoning')}>
          <p className="text-start text-slate-700 dark:text-slate-300">{turn.reasoning_summary}</p>
        </Section>
      )}

      <Section title={t('trace.state')}>
        {stateEntries.length ? <Code>{JSON.stringify(trace.state, null, 2)}</Code> : <p className="text-slate-500">{t('trace.noState')}</p>}
      </Section>

      <Section title={t('trace.toolCalls')}>
        {trace.tool_calls.length === 0 && <p className="text-slate-500">{t('trace.noToolCalls')}</p>}
        <ol className="space-y-2">
          {trace.tool_calls.map((call, index) => (
            <li key={index} className="rounded border border-slate-200 p-2 dark:border-slate-700">
              <div className="flex items-center justify-between gap-2" dir="ltr">
                <span className="font-mono font-semibold">{call.name}</span>
                <span className={call.success ? 'text-emerald-600' : 'text-red-600'}>
                  {call.success ? t('trace.ok') : t('trace.failed')} · {call.latency_ms} ms
                </span>
              </div>
              <Code>{`${t('trace.args')}: ${JSON.stringify(call.args)}\n${t('trace.resultIds')}: [${call.result_ids.join(', ')}]${call.error ? `\nerror: ${call.error}` : ''}`}</Code>
            </li>
          ))}
        </ol>
      </Section>

      <Section title={t('trace.grounding')}>
        {trace.grounding_violations.length === 0 ? (
          <p className="text-emerald-700 dark:text-emerald-400">{t('trace.noViolations')}</p>
        ) : (
          <Code>{JSON.stringify(trace.grounding_violations, null, 2)}</Code>
        )}
      </Section>
    </div>
  )
}
