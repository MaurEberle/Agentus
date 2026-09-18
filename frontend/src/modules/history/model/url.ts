import {
  RUN_OUTCOMES,
  type HistoryFilter,
  type HistoryTab,
  type RangeKey,
  type RunOutcome,
} from '@/modules/history/model/types';
import { endOfLocalDay, startOfLocalDay, toDateInput } from '@/modules/history/model/format';

const TABS: HistoryTab[] = ['history', 'model', 'network'];
const RANGES: RangeKey[] = ['today', '7d', '30d', 'custom'];

export function defaultHistoryFilter(now = Date.now()): HistoryFilter {
  const to = new Date(now);
  const from = new Date(now - 7 * 24 * 60 * 60 * 1000);
  return {
    range: '7d',
    from: from.toISOString(),
    to: to.toISOString(),
    networkId: '',
    outcomes: [],
    model: '',
    q: '',
    tab: 'history',
    page: 1,
  };
}

export function resolveBounds(filter: Pick<HistoryFilter, 'range' | 'from' | 'to'>, now = Date.now()): {
  from: Date;
  to: Date;
} {
  if (filter.range === 'custom') {
    const from = startOfLocalDay(filter.from || now);
    const to = endOfLocalDay(filter.to || now);
    return from <= to ? { from, to } : { from: to, to: from };
  }
  const to = new Date(now);
  if (filter.range === 'today') return { from: startOfLocalDay(now), to };
  const days = filter.range === '30d' ? 30 : 7;
  return { from: new Date(now - days * 24 * 60 * 60 * 1000), to };
}

export function parseHistorySearch(params: URLSearchParams, now = Date.now()): HistoryFilter {
  const rangeRaw = params.get('range');
  const range: RangeKey = RANGES.includes(rangeRaw as RangeKey) ? (rangeRaw as RangeKey) : '7d';
  const tabRaw = params.get('tab');
  const tab: HistoryTab = TABS.includes(tabRaw as HistoryTab) ? (tabRaw as HistoryTab) : 'history';
  const outcomes = (params.get('outcome') ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter((item): item is RunOutcome => (RUN_OUTCOMES as string[]).includes(item));
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1);
  const filter: HistoryFilter = {
    ...defaultHistoryFilter(now),
    range,
    networkId: params.get('networkId') ?? '',
    outcomes,
    model: params.get('model') ?? '',
    q: params.get('q') ?? '',
    tab,
    page,
  };
  if (range === 'custom') {
    const fromParam = params.get('from');
    const toParam = params.get('to');
    if (fromParam) filter.from = startOfLocalDay(fromParam).toISOString();
    if (toParam) filter.to = endOfLocalDay(toParam).toISOString();
  } else {
    const bounds = resolveBounds(filter, now);
    filter.from = bounds.from.toISOString();
    filter.to = bounds.to.toISOString();
  }
  return filter;
}

export function historySearchFrom(filter: HistoryFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (filter.range !== '7d') params.set('range', filter.range);
  if (filter.range === 'custom') {
    if (filter.from) params.set('from', toDateInput(filter.from));
    if (filter.to) params.set('to', toDateInput(filter.to));
  }
  if (filter.networkId) params.set('networkId', filter.networkId);
  if (filter.outcomes.length) params.set('outcome', filter.outcomes.join(','));
  if (filter.model) params.set('model', filter.model);
  if (filter.q.trim()) params.set('q', filter.q.trim());
  if (filter.tab !== 'history') params.set('tab', filter.tab);
  if (filter.page > 1) params.set('page', String(filter.page));
  return params;
}

export function sameFilter(a: HistoryFilter, b: HistoryFilter): boolean {
  return (
    a.range === b.range &&
    a.from === b.from &&
    a.to === b.to &&
    a.networkId === b.networkId &&
    a.model === b.model &&
    a.q === b.q &&
    a.tab === b.tab &&
    a.page === b.page &&
    a.outcomes.length === b.outcomes.length &&
    a.outcomes.every((item, index) => item === b.outcomes[index])
  );
}
