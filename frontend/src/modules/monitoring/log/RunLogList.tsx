import { useState, type KeyboardEvent } from 'react';
import {
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Cpu,
  Flag,
  Gauge,
  Info,
  Loader2,
  MessageSquare,
  Route,
  Wrench,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { formatTime } from '@/lib/format';
import { logHasExtra } from '@/modules/monitoring/model/graph';
import {
  formatMs,
  type LogEntry,
  type LogGroup,
  type LogKind,
  type LogLine,
  type LogStatus,
} from '@/modules/monitoring/model/logView';
import type { LogEvent, LogLevel } from '@/modules/monitoring/model/types';

const KIND_ICON: Record<LogKind, LucideIcon> = {
  decision: Route,
  agent: Bot,
  tool: Wrench,
  llm: Cpu,
  limit: Gauge,
  run: Flag,
  chat: MessageSquare,
  other: Info,
};

const LEVEL_ROW: Record<LogLevel, string> = {
  debug: 'border-l-2 border-l-muted-foreground/40 bg-muted/40 text-muted-foreground',
  info: 'border-l-2 border-l-transparent bg-card',
  warn: 'border-l-2 border-l-warning bg-warning/15',
  error: 'border-l-2 border-l-destructive bg-destructive/10',
};

function StatusMark({ status, running }: { status: LogStatus; running?: boolean }) {
  const { t } = useTranslation();
  if (running) {
    return <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-label={t('runLog.status.running')} />;
  }
  if (status === 'ok') return <Check className="size-3.5 text-primary" aria-label={t('runLog.status.ok')} />;
  if (status === 'fail') return <X className="size-3.5 text-destructive" aria-label={t('runLog.status.fail')} />;
  if (status === 'warn') {
    return <AlertTriangle className="size-3.5 text-warning" aria-label={t('runLog.status.warn')} />;
  }
  return <span className="size-3.5" aria-hidden />;
}

function openProps(extra: boolean, onOpen: () => void) {
  if (!extra) return {};
  return {
    role: 'button' as const,
    tabIndex: 0,
    onClick: onOpen,
    onKeyDown: (evt: KeyboardEvent) => {
      if (evt.key === 'Enter' || evt.key === ' ') {
        evt.preventDefault();
        onOpen();
      }
    },
  };
}

function LineRow({
  event,
  line,
  locale,
  onOpen,
  nested,
}: {
  event: LogEvent;
  line: LogLine;
  locale: string;
  onOpen: (id: string) => void;
  nested?: boolean;
}) {
  const { t } = useTranslation();
  const extra = logHasExtra(event);
  const Icon = KIND_ICON[line.kind];
  return (
    <li>
      <div
        {...openProps(extra, () => onOpen(event.id))}
        title={t(`runLog.kind.${line.kind}`)}
        className={cn(
          'grid grid-cols-[auto_auto_auto_minmax(0,1fr)_auto] items-start gap-x-2 border-b border-border/60 px-2 py-1.5',
          LEVEL_ROW[event.level],
          nested && 'pl-8',
          extra && 'cursor-pointer hover:brightness-[0.97] dark:hover:brightness-110',
        )}
      >
        <span className="tabular-nums text-muted-foreground">{formatTime(event.ts, locale)}</span>
        <Icon className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden />
        <span className="mt-0.5">
          <StatusMark status={line.status} />
        </span>
        <span className="min-w-0 whitespace-pre-wrap break-words">
          {line.actor ? <span className="mr-1.5 font-medium">{line.actor}</span> : null}
          <span className={cn(event.level === 'error' && 'text-destructive')}>{line.text}</span>
        </span>
        <span className="tabular-nums text-muted-foreground">
          {line.durationMs !== null ? formatMs(line.durationMs, locale) : ''}
        </span>
      </div>
    </li>
  );
}

function GroupBlock({
  group,
  lineOf,
  locale,
  onOpen,
  expanded,
  onToggle,
  running,
}: {
  group: LogGroup;
  lineOf: (event: LogEvent) => LogLine;
  locale: string;
  onOpen: (id: string) => void;
  expanded: boolean;
  onToggle: () => void;
  running: boolean;
}) {
  const { t } = useTranslation();
  const start = lineOf(group.start);
  const doneEvent = group.done;
  const done = doneEvent ? lineOf(doneEvent) : null;
  const level: LogLevel = group.done?.level === 'warn' || group.done?.level === 'error' ? group.done.level : 'info';
  const Chevron = expanded ? ChevronDown : ChevronRight;
  const children = group.children.slice().reverse();
  return (
    <li className="border-b border-border/60">
      <div
        className={cn(
          'grid grid-cols-[auto_auto_auto_minmax(0,1fr)_auto] items-start gap-x-2 px-2 py-1.5',
          LEVEL_ROW[level],
          'bg-muted/30',
        )}
      >
        <span className="tabular-nums text-muted-foreground">{formatTime(group.start.ts, locale)}</span>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={expanded ? t('runLog.group.collapse') : t('runLog.group.expand')}
          className="mt-0.5 rounded text-muted-foreground hover:text-foreground"
        >
          <Chevron className="size-3.5" />
        </button>
        <span className="mt-0.5">
          <StatusMark status={done?.status ?? null} running={running} />
        </span>
        <span className="min-w-0 whitespace-pre-wrap break-words">
          <button
            type="button"
            className="text-left"
            onClick={() => (logHasExtra(group.start) ? onOpen(group.start.id) : onToggle())}
          >
            <span className="mr-1.5 font-semibold">{start.actor}</span>
            <span>{start.text}</span>
          </button>
          {done && doneEvent ? (
            <button
              type="button"
              className="mt-0.5 block text-left text-muted-foreground"
              onClick={() => onOpen(doneEvent.id)}
            >
              {done.text}
            </button>
          ) : running ? (
            <span className="mt-0.5 block text-muted-foreground">{t('runLog.group.running')}</span>
          ) : (
            <span className="mt-0.5 block text-muted-foreground">{t('runLog.group.noResult')}</span>
          )}
        </span>
        <span className="tabular-nums text-muted-foreground">
          {done?.durationMs != null ? formatMs(done.durationMs, locale) : ''}
          {children.length ? (
            <span className="block text-right text-[10px]">{t('runLog.group.lines', { count: children.length })}</span>
          ) : null}
        </span>
      </div>
      {expanded && children.length ? (
        <ul>
          {children.map((event) => (
            <LineRow key={event.id} event={event} line={lineOf(event)} locale={locale} onOpen={onOpen} nested />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** U2/U4: the log, newest first. Agent calls are groups; a running one is open. */
export function RunLogList({
  entries,
  lineOf,
  locale,
  onOpen,
  live,
  expandAll,
  emptyText,
}: {
  entries: LogEntry[];
  lineOf: (event: LogEvent) => LogLine;
  locale: string;
  onOpen: (id: string) => void;
  live: boolean;
  /** Search hits inside groups: show them without a click. */
  expandAll: boolean;
  emptyText: string;
}) {
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  if (entries.length === 0) {
    return <p className="p-3 font-sans text-sm text-muted-foreground">{emptyText}</p>;
  }
  let lastGroupId: string | null = null;
  for (const entry of entries) if (entry.type === 'group') lastGroupId = entry.group.id;
  const shown = entries.slice().reverse();
  return (
    <ul>
      {shown.map((entry) => {
        if (entry.type === 'row') {
          return (
            <LineRow
              key={entry.event.id}
              event={entry.event}
              line={lineOf(entry.event)}
              locale={locale}
              onOpen={onOpen}
            />
          );
        }
        const { group } = entry;
        const running = live && !group.done && group.id === lastGroupId;
        const expanded = toggled[group.id] ?? (expandAll || running);
        return (
          <GroupBlock
            key={group.id}
            group={group}
            lineOf={lineOf}
            locale={locale}
            onOpen={onOpen}
            running={running}
            expanded={expanded}
            onToggle={() => setToggled((current) => ({ ...current, [group.id]: !expanded }))}
          />
        );
      })}
    </ul>
  );
}
