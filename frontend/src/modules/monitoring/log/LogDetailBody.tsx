import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { formatTime } from '@/lib/format';
import { modelLabel } from '@/lib/modelName';
import {
  describeLog,
  formatMs,
  payloadOf,
  toolArgs,
  toolErrorText,
  toolResultText,
  type LogContext,
} from '@/modules/monitoring/model/logView';
import { maskSecrets, maskText } from '@/modules/monitoring/model/mask';
import type { LogEvent } from '@/modules/monitoring/model/types';

function str(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-2 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 whitespace-pre-wrap break-words">{children}</dd>
    </div>
  );
}

function TextBlock({ label, text, open = true }: { label: string; text: string; open?: boolean }) {
  if (!text.trim()) return null;
  return (
    <details open={open} className="rounded-md border">
      <summary className="cursor-pointer px-2 py-1 text-xs text-muted-foreground">{label}</summary>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words border-t bg-muted/50 p-2 font-log text-xs">
        {maskText(text)}
      </pre>
    </details>
  );
}

async function copy(value: string) {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    /* ignore */
  }
}

function ToolFields({ event, ctx }: { event: LogEvent; ctx: LogContext }) {
  const { t } = ctx;
  const payload = payloadOf(event);
  const args = toolArgs(event);
  const result = payloadOf({ payload: payload.result });
  const content = str(args.content);
  const plainArgs = Object.fromEntries(Object.entries(args).filter(([key]) => key !== 'content'));
  return (
    <>
      <dl className="space-y-1">
        <Field label={t('runLog.detail.tool')}>{str(payload.name)}</Field>
        {payload.callerName ? <Field label={t('runLog.detail.caller')}>{str(payload.callerName)}</Field> : null}
        {event.nodeName ? <Field label={t('runLog.detail.node')}>{event.nodeName}</Field> : null}
        {str(args.path) ? <Field label={t('runLog.detail.path')}>{str(args.path)}</Field> : null}
        {str(args.command) ? <Field label={t('runLog.detail.command')}>{str(args.command)}</Field> : null}
        {payload.ok === false ? (
          <Field label={t('runLog.detail.error')}>
            <span className="text-destructive">{toolErrorText(payload, t)}</span>
          </Field>
        ) : (
          <Field label={t('runLog.detail.result')}>{toolResultText(payload.result, ctx) || '—'}</Field>
        )}
        {payload.hint ? <Field label={t('runLog.detail.hint')}>{str(payload.hint)}</Field> : null}
        {payload.changed ? <Field label={t('runLog.detail.changed')}>{str(payload.changed)}</Field> : null}
      </dl>
      {str(result.output) ? <TextBlock label={t('runLog.detail.output')} text={str(result.output)} /> : null}
      {Object.keys(plainArgs).length ? (
        <TextBlock label={t('runLog.detail.arguments')} text={JSON.stringify(maskSecrets(plainArgs), null, 2)} />
      ) : null}
      {content ? <TextBlock label={t('runLog.detail.content')} text={content} open={false} /> : null}
    </>
  );
}

function LlmFields({ event, ctx }: { event: LogEvent; ctx: LogContext }) {
  const { t, locale } = ctx;
  const payload = payloadOf(event);
  const model = str(payload.model);
  const label = modelLabel(model);
  const number = (value: unknown) => (typeof value === 'number' ? new Intl.NumberFormat(locale).format(value) : '—');
  return (
    <>
      <dl className="space-y-1">
        {payload.callerName ? <Field label={t('runLog.detail.caller')}>{str(payload.callerName)}</Field> : null}
        <Field label={t('runLog.detail.model')}>
          <span title={model}>{label.name || '—'}</span>
          {label.publisher ? <span className="ml-1 text-muted-foreground">({label.publisher})</span> : null}
        </Field>
        {payload.provider ? <Field label={t('runLog.detail.provider')}>{str(payload.provider)}</Field> : null}
        <Field label={t('runLog.detail.tokens')}>
          {t('runLog.summary.tokens', { tokensIn: number(payload.tokensIn), tokensOut: number(payload.tokensOut) })}
        </Field>
        {typeof payload.durationMs === 'number' ? (
          <Field label={t('runLog.detail.duration')}>{formatMs(payload.durationMs, locale)}</Field>
        ) : null}
        {payload.contextMax ? <Field label={t('runLog.detail.context')}>{number(payload.contextMax)}</Field> : null}
        {payload.finishReason ? <Field label={t('runLog.detail.finish')}>{str(payload.finishReason)}</Field> : null}
      </dl>
      <TextBlock label={t('runLog.detail.answer')} text={str(payload.content)} />
      <TextBlock label={t('runLog.detail.reasoning')} text={str(payload.reasoning)} open={false} />
    </>
  );
}

function AgentFields({ event, ctx }: { event: LogEvent; ctx: LogContext }) {
  const { t, locale } = ctx;
  const payload = payloadOf(event);
  const files = Array.isArray(payload.files) ? payload.files.filter((item): item is string => typeof item === 'string') : [];
  return (
    <>
      <dl className="space-y-1">
        <Field label={t('runLog.detail.agent')}>{str(payload.agentName) || event.nodeName || '—'}</Field>
        {typeof payload.call === 'number' ? <Field label={t('runLog.detail.call')}>{payload.call}</Field> : null}
        {typeof payload.durationMs === 'number' ? (
          <Field label={t('runLog.detail.duration')}>{formatMs(payload.durationMs, locale)}</Field>
        ) : null}
        {typeof payload.tools === 'number' ? (
          <Field label={t('runLog.detail.tools')}>
            {t('runLog.detail.toolsValue', {
              count: payload.tools,
              ok: typeof payload.toolsOk === 'number' ? payload.toolsOk : payload.tools,
              failed: typeof payload.toolsFailed === 'number' ? payload.toolsFailed : 0,
            })}
          </Field>
        ) : null}
        {payload.reason ? <Field label={t('runLog.detail.reason')}>{str(payload.reason)}</Field> : null}
        {files.length ? <Field label={t('runLog.detail.files')}>{files.join('\n')}</Field> : null}
      </dl>
      <TextBlock label={t('runLog.detail.task')} text={str(payload.task)} />
      <TextBlock
        label={
          typeof payload.resultChars === 'number' && payload.resultChars > str(payload.result).length
            ? t('runLog.detail.resultStart', { count: payload.resultChars })
            : t('runLog.detail.resultText')
        }
        text={str(payload.result)}
      />
    </>
  );
}

function ActionFields({ event, ctx }: { event: LogEvent; ctx: LogContext }) {
  const { t } = ctx;
  const payload = payloadOf(event);
  return (
    <>
      <dl className="space-y-1">
        <Field label={t('runLog.detail.action')}>{str(payload.action)}</Field>
        {str(payload.agentName) || str(payload.agent) ? (
          <Field label={t('runLog.detail.agent')}>{str(payload.agentName) || str(payload.agent)}</Field>
        ) : null}
        {payload.via ? (
          <Field label={t('runLog.detail.via')}>{t(`runLog.detail.viaValue.${str(payload.via) === 'tool' ? 'tool' : 'json'}`)}</Field>
        ) : null}
        {payload.source ? <Field label={t('runLog.detail.source')}>{str(payload.source)}</Field> : null}
      </dl>
      <TextBlock label={t('runLog.detail.task')} text={str(payload.task)} />
      <TextBlock label={t('runLog.detail.text')} text={str(payload.text)} />
    </>
  );
}

/** U6: the detail of one log line, by kind. The raw JSON stays one click away. */
export function LogDetailBody({ event, ctx }: { event: LogEvent; ctx: LogContext }) {
  const { t } = useTranslation();
  const line = describeLog(event, ctx);
  const payloadText =
    event.payload === undefined || event.payload === null
      ? ''
      : typeof event.payload === 'string'
        ? maskText(event.payload)
        : JSON.stringify(maskSecrets(event.payload), null, 2);
  const message = `${line.actor ? `${line.actor}: ` : ''}${line.text}`;
  let fields: ReactNode = null;
  if (event.message === 'run.tool.call') fields = <ToolFields event={event} ctx={ctx} />;
  else if (event.message === 'run.llm.done' || event.message === 'run.llm.start') fields = <LlmFields event={event} ctx={ctx} />;
  else if (event.message === 'run.agent.start' || event.message === 'run.agent.done') fields = <AgentFields event={event} ctx={ctx} />;
  else if (event.message === 'run.orchestrator.action') fields = <ActionFields event={event} ctx={ctx} />;
  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">
        {formatTime(event.ts, ctx.locale)} · {t(`monitoring.level.${event.level}`)} · {t(`runLog.kind.${line.kind}`)}
        {event.nodeName ? ` · ${event.nodeName}` : ''}
      </p>
      <div>
        <p className="whitespace-pre-wrap break-words text-sm">{message}</p>
        <Button type="button" size="sm" variant="ghost" className="mt-1 h-7 px-2" onClick={() => void copy(message)}>
          {t('monitoring.log.copyLine')}
        </Button>
      </div>
      {fields}
      {payloadText ? (
        <details className="rounded-md border">
          <summary className="cursor-pointer px-2 py-1 text-xs text-muted-foreground">{t('runLog.detail.raw')}</summary>
          <pre className="max-h-72 overflow-auto border-t bg-muted/50 p-2 font-log text-xs">{payloadText}</pre>
          <Button type="button" size="sm" variant="ghost" className="m-1 h-7 px-2" onClick={() => void copy(payloadText)}>
            {t('monitoring.log.copyPayload')}
          </Button>
        </details>
      ) : null}
      {event.stack ? (
        <details className="rounded-md border">
          <summary className="cursor-pointer px-2 py-1 text-xs text-muted-foreground">{t('monitoring.log.stack')}</summary>
          <pre className="max-h-72 overflow-auto border-t bg-muted/50 p-2 font-log text-xs">{maskText(event.stack)}</pre>
        </details>
      ) : null}
    </div>
  );
}
