import type { ChartBucket, RunSummary } from '@/modules/history/model/types';

/** Stack order, bottom to top and left to right; also the legend order. */
export const OUTCOMES = ['succeeded', 'failed', 'cancelled', 'timeout'] as const;
export type ChartOutcome = (typeof OUTCOMES)[number];

/** Status colours of the app (badges use the same); validated for CVD separation (2026-11-22). */
export const OUTCOME_FILL: Record<ChartOutcome, string> = {
  succeeded: 'hsl(var(--primary))',
  failed: 'hsl(var(--destructive))',
  cancelled: 'hsl(var(--muted-foreground) / 0.55)',
  timeout: 'hsl(var(--warning))',
};

/** Text inside a filled block: the theme's foreground for that fill, never the fill colour. */
export const OUTCOME_INK: Record<ChartOutcome, string> = {
  succeeded: 'hsl(var(--primary-foreground))',
  failed: 'hsl(var(--destructive-foreground))',
  cancelled: 'hsl(var(--background))',
  timeout: 'hsl(var(--warning-foreground))',
};

export type OutcomeCounts = Record<ChartOutcome, number>;

export function bucketTotal(bucket: OutcomeCounts): number {
  return OUTCOMES.reduce((sum, key) => sum + bucket[key], 0);
}

export type TimelineItem =
  | { kind: 'bar'; key: string; bucket: ChartBucket }
  | { kind: 'gap'; key: string; count: number; first: ChartBucket; last: ChartBucket };

/**
 * Columns for the buckets with runs; every stretch of empty buckets becomes one narrow
 * gap. Over 30 days most days had no run and stretched the chart (2026-11-22).
 */
export function compressTimeline(buckets: ChartBucket[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  let gap: ChartBucket[] = [];
  const flush = () => {
    if (gap.length === 0) return;
    items.push({ kind: 'gap', key: `gap-${gap[0].key}`, count: gap.length, first: gap[0], last: gap[gap.length - 1] });
    gap = [];
  };
  for (const bucket of buckets) {
    if (bucketTotal(bucket) === 0) {
      gap.push(bucket);
      continue;
    }
    flush();
    items.push({ kind: 'bar', key: bucket.key, bucket });
  }
  flush();
  return items;
}

/** Clean whole-number ticks from 0 up to at least ``max``: 0/10/20/30/40 for 35. */
export function niceTicks(max: number, target = 4): number[] {
  const top = Math.max(1, max);
  const rough = top / target;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = Math.max(1, [1, 2, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough) ?? power * 10);
  const ticks: number[] = [];
  for (let value = 0; value < top + step; value += step) {
    ticks.push(value);
    if (value >= top) break;
  }
  return ticks;
}

export function outcomeTotals(buckets: ChartBucket[]): OutcomeCounts & { total: number } {
  const counts: OutcomeCounts = { succeeded: 0, failed: 0, cancelled: 0, timeout: 0 };
  for (const bucket of buckets) {
    for (const key of OUTCOMES) counts[key] += bucket[key];
  }
  return { ...counts, total: bucketTotal(counts) };
}

export type NetworkRow = OutcomeCounts & { key: string; name: string; total: number; more?: number };

/** Finished runs per network, most first; beyond ``limit`` the rest share one row. */
export function networkRows(runs: RunSummary[], limit = 8): NetworkRow[] {
  const map = new Map<string, NetworkRow>();
  for (const run of runs) {
    if (!(OUTCOMES as readonly string[]).includes(run.outcome)) continue;
    const key = run.networkId || run.networkName;
    let row = map.get(key);
    if (!row) {
      row = { key, name: run.networkName || key, succeeded: 0, failed: 0, cancelled: 0, timeout: 0, total: 0 };
      map.set(key, row);
    }
    row[run.outcome as ChartOutcome] += 1;
    row.total += 1;
  }
  const rows = [...map.values()].sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  if (rows.length <= limit) return rows;
  const kept = rows.slice(0, limit - 1);
  const rest = rows.slice(limit - 1);
  const other: NetworkRow = { key: 'more', name: '', succeeded: 0, failed: 0, cancelled: 0, timeout: 0, total: 0, more: rest.length };
  for (const row of rest) {
    for (const key of OUTCOMES) other[key] += row[key];
    other.total += row.total;
  }
  return [...kept, other];
}
