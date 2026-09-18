import { durationMs, median, percentile } from '@/modules/history/model/format';
import type {
  ChartBucket,
  ErrorTopRow,
  HistoryKpis,
  LlmCall,
  ModelAggRow,
  NetworkAggRow,
  RunSummary,
} from '@/modules/history/model/types';
import { P95_MIN } from '@/modules/history/model/types';

const TERMINAL: Array<RunSummary['outcome']> = ['succeeded', 'failed', 'cancelled', 'timeout'];

export function isTerminal(outcome: RunSummary['outcome']): boolean {
  return TERMINAL.includes(outcome);
}

export function computeKpis(runs: RunSummary[]): HistoryKpis {
  const terminal = runs.filter((run) => isTerminal(run.outcome));
  const durations = terminal
    .map((run) => durationMs(run.startedAt, run.endedAt))
    .filter((value): value is number => value !== null);
  const succeeded = terminal.filter((run) => run.outcome === 'succeeded').length;
  const failed = terminal.filter((run) => run.outcome === 'failed').length;
  const cancelled = terminal.filter((run) => run.outcome === 'cancelled').length;
  const timeout = terminal.filter((run) => run.outcome === 'timeout').length;
  return {
    total: terminal.length,
    succeeded,
    failed,
    cancelled,
    timeout,
    medianMs: median(durations),
    p95Ms: terminal.length >= P95_MIN ? percentile(durations, 95) : null,
  };
}

function pad(value: number) {
  return value.toString().padStart(2, '0');
}

function dayKey(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function hourKey(date: Date) {
  return `${dayKey(date)}T${pad(date.getHours())}`;
}

export function computeChart(runs: RunSummary[], from: Date, to: Date, locale: string): ChartBucket[] {
  const spanMs = to.getTime() - from.getTime();
  const hourly = spanMs < 2 * 24 * 60 * 60 * 1000;
  const buckets = new Map<string, ChartBucket>();
  const cursor = new Date(from);
  if (hourly) cursor.setMinutes(0, 0, 0);
  else cursor.setHours(0, 0, 0, 0);

  while (cursor.getTime() <= to.getTime()) {
    const key = hourly ? hourKey(cursor) : dayKey(cursor);
    const label = hourly
      ? `${cursor.toLocaleDateString(locale, { month: 'short', day: 'numeric' })} ${pad(cursor.getHours())}:00`
      : cursor.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
    buckets.set(key, { key, label, succeeded: 0, failed: 0, cancelled: 0, timeout: 0 });
    if (hourly) cursor.setHours(cursor.getHours() + 1);
    else cursor.setDate(cursor.getDate() + 1);
  }

  for (const run of runs) {
    if (!isTerminal(run.outcome)) continue;
    const started = new Date(run.startedAt);
    const key = hourly ? hourKey(started) : dayKey(started);
    const bucket = buckets.get(key);
    if (!bucket) continue;
    if (run.outcome === 'succeeded') bucket.succeeded += 1;
    if (run.outcome === 'failed') bucket.failed += 1;
    if (run.outcome === 'cancelled') bucket.cancelled += 1;
    if (run.outcome === 'timeout') bucket.timeout += 1;
  }

  return [...buckets.values()];
}

export function computeErrorTop(runs: RunSummary[], limit = 8): ErrorTopRow[] {
  const map = new Map<string, ErrorTopRow>();
  for (const run of runs) {
    if (run.outcome !== 'failed' && run.outcome !== 'timeout') continue;
    const errorClass = run.errorClass ?? (run.outcome === 'timeout' ? 'timeout' : 'unknown');
    const message = run.errorMessage ?? errorClass;
    const id = `${errorClass}|${run.errorNodeName ?? ''}|${message}`;
    const current = map.get(id);
    if (current) {
      current.count += 1;
    } else {
      map.set(id, {
        id,
        nodeName: run.errorNodeName,
        errorClass,
        message,
        count: 1,
      });
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count).slice(0, limit);
}

export function aggregateModels(calls: LlmCall[]): ModelAggRow[] {
  const map = new Map<string, { row: ModelAggRow; durations: number[] }>();
  for (const call of calls) {
    const key = `${call.provider}|${call.model}`;
    let entry = map.get(key);
    if (!entry) {
      entry = {
        row: {
          provider: call.provider,
          model: call.model,
          calls: 0,
          ok: 0,
          error: 0,
          errorRate: 0,
          medianMs: null,
          tokensIn: 0,
          tokensOut: 0,
        },
        durations: [],
      };
      map.set(key, entry);
    }
    entry.row.calls += 1;
    if (call.ok) entry.row.ok += 1;
    else entry.row.error += 1;
    if (call.durationMs !== undefined) entry.durations.push(call.durationMs);
    if (call.tokensIn !== undefined) entry.row.tokensIn = (entry.row.tokensIn ?? 0) + call.tokensIn;
    if (call.tokensOut !== undefined) entry.row.tokensOut = (entry.row.tokensOut ?? 0) + call.tokensOut;
  }
  return [...map.values()]
    .map(({ row, durations }) => ({
      ...row,
      errorRate: row.calls === 0 ? 0 : row.error / row.calls,
      medianMs: median(durations),
      tokensIn: row.tokensIn === 0 && !calls.some((call) => call.provider === row.provider && call.model === row.model && call.tokensIn !== undefined)
        ? null
        : row.tokensIn,
      tokensOut: row.tokensOut === 0 && !calls.some((call) => call.provider === row.provider && call.model === row.model && call.tokensOut !== undefined)
        ? null
        : row.tokensOut,
    }))
    .sort((a, b) => b.calls - a.calls);
}

export function aggregateNetworks(runs: RunSummary[]): NetworkAggRow[] {
  const map = new Map<string, { row: NetworkAggRow; durations: number[]; errors: Map<string, number> }>();
  for (const run of runs) {
    if (!isTerminal(run.outcome)) continue;
    let entry = map.get(run.networkId);
    if (!entry) {
      entry = {
        row: {
          networkId: run.networkId,
          networkName: run.networkName,
          runs: 0,
          succeeded: 0,
          failed: 0,
          cancelled: 0,
          timeout: 0,
          medianMs: null,
        },
        durations: [],
        errors: new Map(),
      };
      map.set(run.networkId, entry);
    }
    entry.row.runs += 1;
    if (run.outcome === 'succeeded') entry.row.succeeded += 1;
    if (run.outcome === 'failed') entry.row.failed += 1;
    if (run.outcome === 'cancelled') entry.row.cancelled += 1;
    if (run.outcome === 'timeout') entry.row.timeout += 1;
    const duration = durationMs(run.startedAt, run.endedAt);
    if (duration !== null) entry.durations.push(duration);
    if (run.errorNodeName) {
      entry.errors.set(run.errorNodeName, (entry.errors.get(run.errorNodeName) ?? 0) + 1);
    }
  }
  return [...map.values()]
    .map(({ row, durations, errors }) => {
      let topErrorNode: string | undefined;
      let top = 0;
      for (const [name, count] of errors) {
        if (count > top) {
          top = count;
          topErrorNode = name;
        }
      }
      return { ...row, medianMs: median(durations), topErrorNode };
    })
    .sort((a, b) => b.runs - a.runs);
}
