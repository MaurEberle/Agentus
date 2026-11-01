import { useCallback, useState } from 'react';
import type { RangeKey } from '@/modules/history/model/types';

const STORAGE_KEY = 'agentus.history.filters';
const RANGES: RangeKey[] = ['today', '7d', '30d', 'custom'];

export type HistoryListFilter = {
  range: RangeKey;
  from: string;
  to: string;
  networkId: string;
  model: string;
  q: string;
};

const DEFAULTS: HistoryListFilter = {
  range: '7d',
  from: '',
  to: '',
  networkId: '',
  model: '',
  q: '',
};

function normalize(raw: Partial<HistoryListFilter> | null | undefined): HistoryListFilter {
  const range = RANGES.includes(raw?.range as RangeKey) ? (raw?.range as RangeKey) : DEFAULTS.range;
  return {
    range,
    from: range === 'custom' && typeof raw?.from === 'string' ? raw.from : '',
    to: range === 'custom' && typeof raw?.to === 'string' ? raw.to : '',
    networkId: typeof raw?.networkId === 'string' ? raw.networkId : '',
    model: typeof raw?.model === 'string' ? raw.model : '',
    q: typeof raw?.q === 'string' ? raw.q : '',
  };
}

export function loadHistoryFilters(): HistoryListFilter {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return normalize(JSON.parse(raw) as Partial<HistoryListFilter>);
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveHistoryFilters(filter: HistoryListFilter): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalize(filter)));
  } catch {
    // Remembering the filters is optional.
  }
}

export function sameHistoryFilters(a: HistoryListFilter, b: HistoryListFilter): boolean {
  return a.range === b.range && a.from === b.from && a.to === b.to && a.networkId === b.networkId && a.model === b.model && a.q === b.q;
}

export function useHistoryFilters() {
  const [filters, setFilters] = useState(loadHistoryFilters);
  const update = useCallback((next: HistoryListFilter) => {
    const normalized = normalize(next);
    setFilters((current) => {
      if (sameHistoryFilters(current, normalized)) return current;
      saveHistoryFilters(normalized);
      return normalized;
    });
  }, []);
  return [filters, update] as const;
}
