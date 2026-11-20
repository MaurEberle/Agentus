import type { TFunction } from 'i18next';

import { formatBytes, formatDuration } from '@/lib/format';
import { modelLabel } from '@/lib/modelName';
import { formatRunLogMessage } from '@/modules/monitoring/model/logMessage';
import type { LogEvent } from '@/modules/monitoring/model/types';

/** U3: what the log shows. "important" leaves out single tool and model calls. */
export type LogView = 'important' | 'all' | 'debug';
export const LOG_VIEWS: LogView[] = ['important', 'all', 'debug'];

export type LogKind = 'decision' | 'agent' | 'tool' | 'llm' | 'limit' | 'run' | 'chat' | 'other';
export type LogStatus = 'ok' | 'fail' | 'warn' | null;

export type LogLine = {
  kind: LogKind;
  actor: string;
  text: string;
  status: LogStatus;
  durationMs: number | null;
};

export type LogContext = {
  t: TFunction;
  locale: string;
  /** Display name of a node id, for lines that carry only an id. */
  names: (id: string) => string | undefined;
};

export type LogFilter = {
  view: LogView;
  query: string;
  nodeId: string | null;
  errorsOnly: boolean;
};

export type LogGroup = {
  id: string;
  agentId: string;
  start: LogEvent;
  done: LogEvent | null;
  children: LogEvent[];
};

export type LogEntry = { type: 'row'; event: LogEvent } | { type: 'group'; group: LogGroup };

type Payload = Record<string, unknown>;

// Lines older runs still hold but the app no longer writes or shows (VRAM/expert split per model call).
const RETIRED = new Set(['run.llm.vram']);

// Same list as backend/app/run/run_stats.py LIMIT_KEYS.
export const LIMIT_KEYS = new Set([
  'run.agent.emptyStops',
  'run.agent.outputLimit',
  'run.agent.thinkLimit',
  'run.agent.thinkLoop',
  'run.agent.toolCap',
  'run.agent.toolFailures',
  'run.agent.window',
  'run.llmBudget',
  'run.orchestrator.orientationCap',
  'run.orchestrator.stepClose',
  'run.orchestrator.stuck',
  'run.orchestrator.thinkLimit',
  'run.orchestrator.thinkLoop',
  'run.orchestrator.toolCap',
  'run.orchestrator.toolFailures',
  'run.orchestrator.toolWithdrawn',
  'run.orchestrator.window',
  'run.stepLimit',
  'run.tool.disabled',
  'run.tool.limitReached',
  'runtime.generationLimit',
]);

const RUN_KEYS = new Set(['run.summary', 'run.succeeded', 'run.failed', 'run.cancelled', 'run.batch.start']);

// Info lines that belong to the "important" view besides decisions, agents and limits.
const IMPORTANT_INFO = new Set([
  'run.orchestrator.takeoverStart',
  'run.orchestrator.takeoverFailures',
  'run.orchestrator.selfTakeover',
  'run.agent.textOnly',
]);

const FILE_ACTIONS = new Set([
  'read',
  'read_many',
  'write',
  'edit',
  'delete',
  'move',
  'list',
  'tree',
  'stat',
  'search',
  'mkdir',
  'exists',
]);

export function payloadOf(event: { payload?: unknown }): Payload {
  const value = event.payload;
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Payload) : {};
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function clip(text: string, limit: number): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length <= limit ? flat : `${flat.slice(0, limit).trimEnd()}…`;
}

/** Short name of a limit key: its log text without the values only a log line has. */
export function limitLabel(key: string, t: TFunction): string {
  return formatRunLogMessage(key, t)
    .replace(/\s*\(?\{\{\s*\w+\s*\}\}\)?/g, '')
    .replace(/\s+([,.:;])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/** Translation, or ``fallback`` when the key does not exist. */
function tr(t: TFunction, key: string, vars: Record<string, unknown>, fallback: string): string {
  const out = t(key, { ...vars, defaultValue: '' });
  return typeof out === 'string' && out && out !== key ? out : fallback;
}

export function isRetired(event: LogEvent): boolean {
  return RETIRED.has(event.message);
}

export function logKind(event: LogEvent): LogKind {
  const message = event.message;
  if (LIMIT_KEYS.has(message)) return 'limit';
  if (message.startsWith('run.tool.')) return 'tool';
  if (message.startsWith('run.llm.')) return 'llm';
  if (message === 'run.agent.start' || message === 'run.agent.done') return 'agent';
  if (message === 'run.orchestrator.action' || message === 'run.orchestrator.step') return 'decision';
  if (RUN_KEYS.has(message)) return 'run';
  if (message.startsWith('run.chat.') || message.startsWith('run.wait.')) return 'chat';
  return 'other';
}

export function inView(event: LogEvent, view: LogView): boolean {
  if (view === 'debug') return true;
  if (event.level === 'debug') return false;
  if (view === 'all') return true;
  if (event.level === 'warn' || event.level === 'error') return true;
  const kind = logKind(event);
  if (kind === 'decision' || kind === 'agent' || kind === 'limit' || kind === 'run' || kind === 'chat') return true;
  return IMPORTANT_INFO.has(event.message);
}

/** B4: a line belongs to a node when it ran there or that node made the call. */
export function nodeMatch(event: LogEvent, nodeId: string | null): boolean {
  if (!nodeId) return true;
  const payload = payloadOf(event);
  return event.nodeId === nodeId || payload.caller === nodeId || payload.agentId === nodeId;
}

export function formatMs(ms: number, locale: string): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))} ms`;
  if (ms < 60_000) {
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(ms / 1000)} s`;
  }
  return `${formatDuration(ms)} ${ms >= 3_600_000 ? 'h' : 'min'}`;
}

function formatNumber(value: number, locale: string, digits = 0): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

function parseArgs(raw: unknown): Payload {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Payload;
  if (typeof raw !== 'string' || !raw.trim()) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Payload) : {};
  } catch {
    return {};
  }
}

export function toolArgs(event: LogEvent): Payload {
  return parseArgs(payloadOf(event).arguments);
}

function actorOf(event: LogEvent, ctx: LogContext): string {
  const payload = payloadOf(event);
  const caller = str(payload.caller);
  return str(payload.callerName) || (caller ? ctx.names(caller) : undefined) || event.nodeName || event.nodeId || '';
}

function toolAction(name: string, args: Payload, ctx: LogContext): string {
  const { t } = ctx;
  const leaf = name.includes('__') ? name.split('__').pop() ?? name : name;
  // Older runs logged no arguments; the tool name is all there is.
  if (Object.keys(args).length === 0) return tr(t, 'runLog.view.toolGeneric', { name }, name);
  if (leaf === 'file_access') {
    const action = str(args.action);
    const paths = Array.isArray(args.paths) ? args.paths.filter((item): item is string => typeof item === 'string') : [];
    const path = str(args.path) || paths.slice(0, 3).join(', ') || '.';
    const vars = { path: clip(path, 120), to: clip(str(args.to) || str(args.destination), 120), pattern: clip(str(args.pattern), 60) };
    if (FILE_ACTIONS.has(action)) return tr(t, `runLog.view.file.${action}`, vars, `${action} ${path}`);
    return tr(t, 'runLog.view.file.other', { ...vars, action }, `file_access ${action} ${path}`);
  }
  if (leaf === 'terminal') {
    const command = str(args.command) || [str(args.program), ...(Array.isArray(args.args) ? args.args.map(String) : [])].join(' ');
    return tr(t, 'runLog.view.terminal', { command: clip(command, 160) }, command);
  }
  if (leaf === 'http') {
    return tr(t, 'runLog.view.http', { method: str(args.method) || 'GET', url: clip(str(args.url), 120) }, name);
  }
  if (leaf === 'web_search') return tr(t, 'runLog.view.webSearch', { query: clip(str(args.query), 120) }, name);
  if (leaf === 'calculator') {
    return tr(t, 'runLog.view.calculator', { expression: clip(str(args.expression), 120) }, name);
  }
  if (leaf === 'zip') {
    return tr(t, 'runLog.view.zip', { action: str(args.action), path: clip(str(args.path), 120) }, name);
  }
  return tr(t, 'runLog.view.toolGeneric', { name }, name);
}

/** Short result of a tool call: lines read, entries, size, exit code with the telling line. */
export function toolResultText(result: unknown, ctx: LogContext): string {
  const { t, locale } = ctx;
  const facts = result && typeof result === 'object' && !Array.isArray(result) ? (result as Payload) : {};
  const parts: string[] = [];
  const exit = num(facts.exitCode);
  if (exit !== null) {
    const output = str(facts.output);
    if (exit !== 0 || facts.timedOut === true) parts.push(t('runLog.view.exit', { code: exit }));
    if (output) parts.push(clip(output, 140));
    return parts.join(': ');
  }
  const lines = num(facts.lines);
  if (lines !== null) parts.push(t('runLog.view.lines', { count: lines }));
  for (const key of ['entries', 'matches', 'files', 'children', 'results', 'items'] as const) {
    const count = num(facts[key]);
    if (count !== null) parts.push(t(`runLog.view.count.${key}`, { count }));
  }
  const replacements = num(facts.replacements);
  if (replacements !== null) parts.push(t('runLog.view.replacements', { count: replacements }));
  const bytes = num(facts.bytes);
  if (bytes !== null && lines === null) parts.push(formatBytes(bytes, locale));
  const chars = num(facts.chars);
  if (chars !== null) parts.push(t('runLog.view.chars', { count: chars }));
  const status = num(facts.status) ?? num(facts.statusCode);
  if (status !== null) parts.push(`HTTP ${status}`);
  if (facts.truncated === true) parts.push(t('runLog.view.truncated'));
  return parts.join(' · ');
}

export function toolErrorText(payload: Payload, t: TFunction): string {
  const key = str(payload.errorKey) || (/^tools?\./.test(str(payload.error)) ? str(payload.error) : '');
  if (key) return tr(t, `runLog.toolError.${key.replace(/^tools?\./, '')}`, {}, key);
  return clip(str(payload.error), 160);
}

function agentName(payload: Payload, event: LogEvent, ctx: LogContext): string {
  const id = str(payload.agentId) || str(payload.agent);
  return str(payload.agentName) || (id ? ctx.names(id) : undefined) || str(payload.requested) || id || event.nodeName || '';
}

function withText(head: string, text: string, limit = 200): string {
  const body = clip(text, limit);
  return body ? `${head}: ${body}` : head;
}

function describeTool(event: LogEvent, ctx: LogContext): LogLine {
  const payload = payloadOf(event);
  const { t } = ctx;
  const line: LogLine = {
    kind: 'tool',
    actor: actorOf(event, ctx),
    text: '',
    status: null,
    durationMs: num(payload.durationMs),
  };
  if (event.message !== 'run.tool.call') {
    line.text = formatRunLogMessage(event.message, t, payload);
    line.status = event.level === 'error' ? 'fail' : event.level === 'warn' ? 'warn' : null;
    return line;
  }
  const action = toolAction(str(payload.name), toolArgs(event), ctx);
  const ok = payload.ok !== false;
  const result = payloadOf({ payload: payload.result });
  const exit = num(result.exitCode);
  const tail = ok ? toolResultText(payload.result, ctx) : toolErrorText(payload, t);
  line.text = tail ? `${action} · ${tail}` : action;
  if (payload.reused === true) line.text = `${line.text} · ${t('runLog.view.reused')}`;
  line.status = !ok ? 'fail' : exit !== null && exit !== 0 ? 'warn' : 'ok';
  return line;
}

function describeLlm(event: LogEvent, ctx: LogContext): LogLine {
  const payload = payloadOf(event);
  const { t, locale } = ctx;
  const model = modelLabel(str(payload.model)).name || str(payload.model);
  const durationMs = num(payload.durationMs);
  const line: LogLine = { kind: 'llm', actor: actorOf(event, ctx), text: '', status: null, durationMs };
  if (event.message === 'run.llm.start') {
    line.text = t('runLog.view.llmStart', { model });
    return line;
  }
  if (event.message !== 'run.llm.done') {
    line.text = formatRunLogMessage(event.message, t, payload);
    line.status = event.level === 'error' ? 'fail' : event.level === 'warn' ? 'warn' : null;
    return line;
  }
  const parts = [t('runLog.view.llm', { model })];
  const tokensOut = num(payload.tokensOut);
  if (tokensOut !== null) parts.push(t('runLog.view.tokens', { count: tokensOut }));
  const rate = num(payload.perSecond) ?? (tokensOut && durationMs ? tokensOut / Math.max(durationMs / 1000, 0.05) : null);
  if (rate !== null && rate > 0) parts.push(`${formatNumber(rate, locale, 1)} tok/s`);
  const tools = Array.isArray(payload.toolCalls) ? payload.toolCalls.filter((item): item is string => typeof item === 'string') : [];
  if (tools.length) parts.push(t('runLog.view.llmTools', { names: tools.join(', ') }));
  const finish = str(payload.finishReason);
  if (finish === 'length') parts.push(t('runLog.view.llmCut'));
  line.text = parts.join(' · ');
  line.status = finish === 'length' ? 'warn' : 'ok';
  return line;
}

function describeAction(event: LogEvent, ctx: LogContext): LogLine {
  const payload = payloadOf(event);
  const { t } = ctx;
  const action = str(payload.action);
  const line: LogLine = { kind: 'decision', actor: event.nodeName ?? '', text: '', status: null, durationMs: null };
  if (action === 'call') {
    const head = t('runLog.view.action.call', { agent: agentName(payload, event, ctx) });
    line.text = withText(head, str(payload.task));
    if (payload.retry === true) line.text = `${line.text} (${t('runLog.view.action.retry')})`;
  } else if (action === 'finish' || action === 'reply' || action === 'ask') {
    line.text = withText(t(`runLog.view.action.${action}`), str(payload.text));
  } else {
    line.text = formatRunLogMessage(event.message, t, payload);
  }
  return line;
}

function describeAgent(event: LogEvent, ctx: LogContext): LogLine {
  const payload = payloadOf(event);
  const { t } = ctx;
  const line: LogLine = {
    kind: 'agent',
    actor: agentName(payload, event, ctx),
    text: '',
    status: null,
    durationMs: num(payload.durationMs),
  };
  const call = num(payload.call);
  if (event.message === 'run.agent.start') {
    const head = call !== null ? t('runLog.view.agentStart', { call }) : t('runLog.view.agentStartPlain');
    line.text = withText(head, str(payload.task));
    return line;
  }
  const outcome = str(payload.outcome) || 'done';
  const parts: string[] = [];
  if (outcome === 'anomaly') parts.push(withText(t('runLog.view.outcome.anomaly'), str(payload.reason), 120));
  else parts.push(tr(t, `runLog.view.outcome.${outcome}`, {}, outcome));
  const tools = num(payload.tools);
  if (tools !== null && tools > 0) {
    const failed = num(payload.toolsFailed) ?? 0;
    parts.push(
      failed > 0
        ? t('runLog.view.toolsWithFailed', { count: tools, failed })
        : t('runLog.view.toolsCount', { count: tools }),
    );
  }
  const files = num(payload.filesCount);
  if (files !== null && files > 0) parts.push(t('runLog.view.filesCount', { count: files }));
  if (payload.capped === true) parts.push(t('runLog.view.capped'));
  line.text = parts.join(' · ');
  // Older runs logged no outcome: their done line says the turn ended, not that it worked.
  if (!payload.outcome) line.status = null;
  else line.status = outcome === 'anomaly' ? 'fail' : outcome === 'stopped' || outcome === 'cancelled' ? 'warn' : 'ok';
  return line;
}

function describeStep(event: LogEvent, ctx: LogContext): LogLine {
  const payload = payloadOf(event);
  const { t } = ctx;
  const calls = num(payload.calls) ?? 0;
  const failed = num(payload.failed) ?? 0;
  const parts = [
    failed > 0 ? t('runLog.view.stepWithFailed', { count: calls, failed }) : t('runLog.view.step', { count: calls }),
  ];
  const end = str(payload.end);
  if (end) parts.push(tr(t, `runLog.view.stepEnd.${end}`, {}, end));
  const withdrawn = Array.isArray(payload.withdrawn) ? payload.withdrawn.filter((item): item is string => typeof item === 'string') : [];
  if (payload.capped === true) parts.push(t('runLog.view.stepCapped'));
  if (withdrawn.length) parts.push(t('runLog.view.stepWithdrawn', { names: withdrawn.join(', ') }));
  return {
    kind: 'decision',
    actor: event.nodeName ?? '',
    text: parts.join(' · '),
    status: payload.capped === true || withdrawn.length > 0 ? 'warn' : failed > 0 ? 'warn' : 'ok',
    durationMs: num(payload.durationMs),
  };
}

/** U1: one readable sentence per log line. */
export function describeLog(event: LogEvent, ctx: LogContext): LogLine {
  const kind = logKind(event);
  if (event.message.startsWith('run.tool.')) return { ...describeTool(event, ctx), kind };
  if (event.message.startsWith('run.llm.')) return { ...describeLlm(event, ctx), kind };
  if (event.message === 'run.orchestrator.action') return describeAction(event, ctx);
  if (event.message === 'run.orchestrator.step') return describeStep(event, ctx);
  if (kind === 'agent') return describeAgent(event, ctx);
  const payload = payloadOf(event);
  return {
    kind,
    actor: event.nodeName ?? '',
    text: formatRunLogMessage(event.message, ctx.t, event.payload),
    status: event.level === 'error' ? 'fail' : event.level === 'warn' ? 'warn' : null,
    durationMs: num(payload.durationMs),
  };
}

/** U5: what the search looks at: the shown sentence, the key, and task, result and arguments. */
export function searchText(event: LogEvent, line: LogLine): string {
  const payload = payloadOf(event);
  const extra = ['task', 'result', 'text', 'arguments', 'error', 'hint', 'reason', 'errorKey']
    .map((key) => {
      const value = payload[key];
      if (typeof value === 'string') return value;
      if (value && typeof value === 'object') return JSON.stringify(value);
      return '';
    })
    .join(' ');
  return `${line.actor} ${line.text} ${event.message} ${event.nodeName ?? ''} ${extra}`.toLowerCase();
}

function belongs(event: LogEvent, group: LogGroup): boolean {
  const payload = payloadOf(event);
  const caller = str(payload.caller);
  if (caller) return caller === group.agentId;
  if (event.nodeId === group.agentId) return true;
  // Older runs: tool and model lines had no caller; during an agent call they were its own.
  return event.message.startsWith('run.tool.') || event.message.startsWith('run.llm.');
}

/** U2: lines of one agent call under its start line, closed by its result line. */
export function groupLogs(logs: LogEvent[]): LogEntry[] {
  const out: LogEntry[] = [];
  let open: LogGroup | null = null;
  for (const event of logs) {
    if (isRetired(event)) continue;
    const payload = payloadOf(event);
    if (event.message === 'run.agent.start') {
      open = { id: event.id, agentId: str(payload.agentId) || event.nodeId || '', start: event, done: null, children: [] };
      out.push({ type: 'group', group: open });
      continue;
    }
    if (open && event.message === 'run.agent.done' && (str(payload.agentId) || event.nodeId || '') === open.agentId) {
      open.done = event;
      open = null;
      continue;
    }
    if (open && belongs(event, open)) {
      open.children.push(event);
      continue;
    }
    out.push({ type: 'row', event });
  }
  return out;
}

function isProblem(event: LogEvent | null): boolean {
  return Boolean(event && (event.level === 'warn' || event.level === 'error'));
}

/** View, node, error and search filters over rows and groups. A group stays when a line in it matches. */
export function filterEntries(
  entries: LogEntry[],
  filter: LogFilter,
  textOf: (event: LogEvent) => string,
): LogEntry[] {
  const query = filter.query.trim().toLowerCase();
  const pass = (event: LogEvent) =>
    inView(event, filter.view) &&
    (!filter.errorsOnly || isProblem(event)) &&
    nodeMatch(event, filter.nodeId) &&
    (!query || textOf(event).includes(query));
  const out: LogEntry[] = [];
  for (const entry of entries) {
    if (entry.type === 'row') {
      if (entry.event.message !== 'run.summary' && pass(entry.event)) out.push(entry);
      continue;
    }
    const { group } = entry;
    const children = group.children.filter(pass);
    const heads = group.done ? [group.start, group.done] : [group.start];
    const head =
      (!filter.nodeId || group.agentId === filter.nodeId) &&
      (!filter.errorsOnly || isProblem(group.done)) &&
      (!query || heads.some((event) => textOf(event).includes(query)));
    if (head || children.length > 0) out.push({ type: 'group', group: { ...group, children } });
  }
  return out;
}

/** The lines of the shown entries, oldest first (JSON export). */
export function entryEvents(entries: LogEntry[]): LogEvent[] {
  const out: LogEvent[] = [];
  for (const entry of entries) {
    if (entry.type === 'row') {
      out.push(entry.event);
      continue;
    }
    out.push(entry.group.start, ...entry.group.children);
    if (entry.group.done) out.push(entry.group.done);
  }
  return out;
}

export function findSummary(logs: LogEvent[]): LogEvent | null {
  for (let index = logs.length - 1; index >= 0; index -= 1) {
    if (logs[index].message === 'run.summary') return logs[index];
  }
  return null;
}

const STATUS_MARK: Record<Exclude<LogStatus, null>, string> = { ok: '✓', fail: '✗', warn: '⚠' };

function textRow(event: LogEvent, ctx: LogContext, indent: string): string {
  const line = describeLog(event, ctx);
  const time = formatClock(event.ts, ctx.locale);
  const mark = line.status ? `${STATUS_MARK[line.status]} ` : '';
  const actor = line.actor ? `${line.actor}: ` : '';
  const duration = line.durationMs !== null ? ` (${formatMs(line.durationMs, ctx.locale)})` : '';
  return `${indent}- ${time} ${mark}${actor}${line.text}${duration}`;
}

function formatClock(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** U7: the shown log as Markdown, oldest line first, groups as sections. */
export function logsToMarkdown(
  entries: LogEntry[],
  ctx: LogContext,
  head: { title: string; summary: LogEvent | null },
): string {
  const out: string[] = [`# ${head.title}`, ''];
  if (head.summary) {
    out.push(...summaryLines(head.summary, ctx), '');
  }
  for (const entry of entries) {
    if (entry.type === 'row') {
      out.push(textRow(entry.event, ctx, ''));
      continue;
    }
    const { group } = entry;
    out.push('', textRow(group.start, ctx, '').replace(/^- /, '### '));
    for (const child of group.children) out.push(textRow(child, ctx, '  '));
    if (group.done) out.push(textRow(group.done, ctx, ''));
    out.push('');
  }
  return `${out.join('\n').replace(/\n{3,}/g, '\n\n').trim()}\n`;
}

export type SummaryAgent = { id: string; name: string; calls: number; failed: number; durationMs: number; tools: number };

export type RunSummary = {
  outcome: string;
  durationMs: number;
  agentCalls: number;
  agents: SummaryAgent[];
  llmCalls: number;
  llmMs: number;
  tokensIn: number;
  tokensOut: number;
  toolCalls: number;
  toolsOk: number;
  toolsFailed: number;
  files: string[];
  filesCount: number;
  limits: Record<string, number>;
  warnings: number;
  errors: number;
  error: string;
};

export function readSummary(event: LogEvent): RunSummary {
  const payload = payloadOf(event);
  const agents = Array.isArray(payload.agents) ? payload.agents : [];
  const limits = payloadOf({ payload: payload.limits });
  return {
    outcome: str(payload.outcome),
    durationMs: num(payload.durationMs) ?? 0,
    agentCalls: num(payload.agentCalls) ?? 0,
    agents: agents
      .map((item) => payloadOf({ payload: item }))
      .map((item) => ({
        id: str(item.id),
        name: str(item.name) || str(item.id),
        calls: num(item.calls) ?? 0,
        failed: num(item.failed) ?? 0,
        durationMs: num(item.durationMs) ?? 0,
        tools: num(item.tools) ?? 0,
      })),
    llmCalls: num(payload.llmCalls) ?? 0,
    llmMs: num(payload.llmMs) ?? 0,
    tokensIn: num(payload.tokensIn) ?? 0,
    tokensOut: num(payload.tokensOut) ?? 0,
    toolCalls: num(payload.toolCalls) ?? 0,
    toolsOk: num(payload.toolsOk) ?? 0,
    toolsFailed: num(payload.toolsFailed) ?? 0,
    files: Array.isArray(payload.files) ? payload.files.filter((item): item is string => typeof item === 'string') : [],
    filesCount: num(payload.filesCount) ?? 0,
    limits: Object.fromEntries(
      Object.entries(limits).filter((item): item is [string, number] => typeof item[1] === 'number'),
    ),
    warnings: num(payload.warnings) ?? 0,
    errors: num(payload.errors) ?? 0,
    error: str(payload.error),
  };
}

export function summaryLines(event: LogEvent, ctx: LogContext): string[] {
  const { t, locale } = ctx;
  const summary = readSummary(event);
  const lines = [
    `- ${t('runLog.summary.outcome')}: ${tr(t, `runLog.summary.outcomes.${summary.outcome}`, {}, summary.outcome)} · ${formatMs(summary.durationMs, locale)}`,
    `- ${t('runLog.summary.agentCalls')}: ${summary.agentCalls}${
      summary.agents.length ? ` (${summary.agents.map((item) => `${item.name} ${item.calls}`).join(', ')})` : ''
    }`,
    `- ${t('runLog.summary.llmCalls')}: ${summary.llmCalls} · ${t('runLog.summary.tokens', {
      tokensIn: formatNumber(summary.tokensIn, locale),
      tokensOut: formatNumber(summary.tokensOut, locale),
    })}`,
    `- ${t('runLog.summary.toolCalls')}: ${summary.toolCalls} (✓ ${summary.toolsOk}, ✗ ${summary.toolsFailed})`,
    `- ${t('runLog.summary.files')}: ${summary.filesCount}${summary.files.length ? ` (${summary.files.join(', ')})` : ''}`,
  ];
  const limits = Object.entries(summary.limits);
  if (limits.length) {
    lines.push(
      `- ${t('runLog.summary.limits')}: ${limits
        .map(([key, count]) => `${limitLabel(key, t)} ×${count}`)
        .join('; ')}`,
    );
  }
  if (summary.error) lines.push(`- ${t('runLog.summary.error')}: ${formatRunLogMessage(summary.error, t)}`);
  return lines;
}
