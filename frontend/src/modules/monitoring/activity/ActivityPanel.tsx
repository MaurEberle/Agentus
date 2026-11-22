import { useState, type ReactNode } from 'react';
import { Check, Copy, MessageCircleQuestion } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { nodeDisplayName, runTokenStats } from '@/modules/monitoring/model/graph';
import type { NodeRuntime, RunGraphNode, RunSnapshot } from '@/modules/monitoring/model/types';
import { moduleCardBodyClass } from '@/modules/moduleCard';

type CurrentRow = { id: string; node: RunGraphNode; runtime?: NodeRuntime };

// Who works on a task: an agent first, then the orchestrator, then any other node with a text.
const TASK_ORDER: Record<string, number> = { agent: 0, orchestrator: 1 };

function taskOwner(current: CurrentRow[]): CurrentRow | undefined {
  return current
    .filter((row) => Boolean(row.runtime?.lastMessage?.trim()))
    .sort((left, right) => (TASK_ORDER[left.node.type] ?? 2) - (TASK_ORDER[right.node.type] ?? 2))[0];
}

/** Context fill of the model at work: the task owner's own numbers first, then any active node. */
function contextOf(owner: CurrentRow | undefined, current: CurrentRow[]): { used: number; max: number } | null {
  for (const row of [owner, ...current]) {
    const tokens = row?.runtime?.tokens;
    if (tokens?.contextUsed != null && tokens.contextMax) return { used: tokens.contextUsed, max: tokens.contextMax };
  }
  return null;
}

function Metric({
  label,
  value,
  unit,
  sub,
  children,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  children?: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="truncate font-mono text-xl font-semibold leading-tight tabular-nums">
        {value}
        {unit ? <span className="ml-0.5 text-sm font-medium text-muted-foreground">{unit}</span> : null}
      </p>
      {children}
      {sub ? <p className="truncate text-[11px] text-muted-foreground" title={sub}>{sub}</p> : null}
    </div>
  );
}

const STATUS_DOT: Record<string, string> = {
  running: 'bg-primary animate-pulse motion-reduce:animate-none',
  waiting: 'bg-warning',
  halted: 'bg-destructive',
};

export function ActivityPanel({ run, dimmed }: { run: RunSnapshot; dimmed?: boolean }) {
  const { t, i18n } = useTranslation();
  const [copied, setCopied] = useState(false);
  const currentIds = new Set(run.activity.currentNodeIds);
  for (const [id, runtime] of Object.entries(run.nodesRuntime)) {
    if (runtime.status === 'running' || runtime.status === 'waiting' || runtime.status === 'halted') {
      currentIds.add(id);
    }
  }
  const current: CurrentRow[] = [];
  for (const id of currentIds) {
    const node = run.graph.nodes.find((item) => item.id === id);
    if (node) current.push({ id, node, runtime: run.nodesRuntime[id] });
  }

  const tokens = runTokenStats(run);
  const stepError = run.activity.stepError;
  const errorNode = stepError ? run.graph.nodes.find((item) => item.id === stepError.nodeId) : null;
  const owner = taskOwner(current);
  const task = owner?.runtime?.lastMessage?.trim() ?? '';
  const context = contextOf(owner, current);
  const share = context ? Math.min(100, Math.round((context.used / context.max) * 100)) : null;
  const producer = current.find((row) => row.node.type === 'llm' && row.runtime?.status === 'running');
  const number = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 0 });
  const compact = new Intl.NumberFormat(i18n.language, { notation: 'compact', maximumFractionDigits: 1 });
  const waitingForUser = Boolean(run.waitAsk) || current.some((row) => row.runtime?.waitReason === 'human');

  async function copyTask() {
    try {
      await navigator.clipboard.writeText(task);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Card className={cn('flex h-full min-h-0 flex-col overflow-hidden', dimmed && 'opacity-60')}>
      <CardHeader className="pb-2">
        <CardTitle>{t('monitoring.activity.title')}</CardTitle>
      </CardHeader>
      <CardContent className={cn(moduleCardBodyClass, 'flex flex-col gap-2.5 text-sm')}>
        {/* Live numbers first, set apart from the rest. */}
        <div className="grid grid-cols-[repeat(auto-fit,minmax(7rem,1fr))] gap-3 rounded-lg border bg-muted/40 px-3 py-2">
          <Metric
            label={t('monitoring.activity.rate')}
            value={tokens.perSecond !== undefined ? number.format(Math.round(tokens.perSecond)) : '—'}
            sub={producer ? nodeDisplayName(producer.node) : undefined}
          />
          <Metric
            label={t('monitoring.activity.contextLabel')}
            value={share != null ? String(share) : '—'}
            unit={share != null ? '%' : undefined}
            sub={context ? `${number.format(context.used)} / ${number.format(context.max)}` : undefined}
          >
            {share != null ? (
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                <div
                  className={cn(
                    'h-full rounded-full',
                    share >= 90 ? 'bg-destructive' : share >= 75 ? 'bg-warning' : 'bg-primary',
                  )}
                  style={{ width: `${Math.max(share, 2)}%` }}
                />
              </div>
            ) : null}
          </Metric>
          <Metric
            label={t('monitoring.activity.runTotal')}
            value={number.format(tokens.out)}
            sub={
              tokens.in
                ? t('monitoring.activity.runTotalIn', { value: compact.format(tokens.in) })
                : t('monitoring.activity.runTotalOut')
            }
          />
        </div>

        {stepError ? (
          <Alert variant="destructive">
            <AlertTitle>{t('monitoring.activity.stepError')}</AlertTitle>
            <AlertDescription>
              {errorNode ? `${nodeDisplayName(errorNode)}: ` : ''}
              {stepError.message}
            </AlertDescription>
          </Alert>
        ) : null}

        {waitingForUser ? (
          <p className="flex items-center gap-2 rounded-md border border-warning/50 bg-warning/10 px-3 py-2 text-sm">
            <MessageCircleQuestion className="size-4 shrink-0" aria-hidden />
            {t('monitoring.chat.waitReply')}
          </p>
        ) : null}

        {/* Who is at work, in one line. */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-xs font-medium text-muted-foreground">{t('monitoring.activity.now')}</p>
          {current.length === 0 ? (
            <p className="text-muted-foreground">{t('monitoring.activity.none')}</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {current.map(({ id, node, runtime }) => (
                <li
                  key={id}
                  className={cn(
                    'flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs',
                    id === owner?.id && 'border-primary/50 bg-primary/10',
                  )}
                >
                  <span className={cn('size-2 shrink-0 rounded-full', STATUS_DOT[runtime?.status ?? ''] ?? 'bg-muted-foreground')} aria-hidden />
                  <span className="font-medium">{nodeDisplayName(node)}</span>
                  {runtime ? (
                    <span className="text-muted-foreground">
                      {runtime.waitReason && runtime.waitReason !== 'none'
                        ? t(`monitoring.wait.${runtime.waitReason}`)
                        : t(`monitoring.nodeStatus.${runtime.status}`)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* The task gets the remaining height, in full and scrollable. */}
        <div className="flex min-h-[6rem] flex-1 flex-col">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-muted-foreground">
              {owner && task
                ? t('monitoring.activity.taskFor', { name: nodeDisplayName(owner.node) })
                : t('monitoring.activity.task')}
            </p>
            {task ? (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-7"
                aria-label={copied ? t('monitoring.copied') : t('monitoring.copy')}
                title={copied ? t('monitoring.copied') : t('monitoring.copy')}
                onClick={() => void copyTask()}
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </Button>
            ) : null}
          </div>
          <div
            className={cn(
              'mt-1 min-h-0 flex-1 overflow-auto rounded-md border bg-background p-3 text-sm leading-relaxed',
              !task && 'flex items-center justify-center text-muted-foreground',
            )}
          >
            {task ? (
              <p className="whitespace-pre-wrap break-words">{task}</p>
            ) : (
              <p>{t('monitoring.activity.noTask')}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
