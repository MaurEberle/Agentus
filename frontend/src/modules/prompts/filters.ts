import { useCallback, useState } from 'react';
import type { TagMatch } from '@/lib/tags';

const STORAGE_KEY = 'agentus.prompts.filters';

export type PromptSortKey = 'name' | 'updated';
export type PromptSortDir = 'asc' | 'desc';

export type PromptFilters = {
  search: string;
  sortKey: PromptSortKey;
  sortDir: PromptSortDir;
  tagFilter: string[];
  tagMode: TagMatch;
};

const DEFAULTS: PromptFilters = {
  search: '',
  sortKey: 'updated',
  sortDir: 'desc',
  tagFilter: [],
  tagMode: 'or',
};

function normalize(raw: Partial<PromptFilters> | null | undefined): PromptFilters {
  const sortKey = raw?.sortKey === 'name' || raw?.sortKey === 'updated' ? raw.sortKey : DEFAULTS.sortKey;
  const sortDir = raw?.sortDir === 'asc' || raw?.sortDir === 'desc' ? raw.sortDir : DEFAULTS.sortDir;
  const tagMode = raw?.tagMode === 'and' || raw?.tagMode === 'or' ? raw.tagMode : DEFAULTS.tagMode;
  const tagFilter = Array.isArray(raw?.tagFilter) ? raw.tagFilter.filter((tag) => typeof tag === 'string' && tag.trim()) : [];
  return {
    search: typeof raw?.search === 'string' ? raw.search : '',
    sortKey,
    sortDir,
    tagFilter,
    tagMode,
  };
}

export function loadPromptFilters(): PromptFilters {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS, tagFilter: [] };
    return normalize(JSON.parse(raw) as Partial<PromptFilters>);
  } catch {
    return { ...DEFAULTS, tagFilter: [] };
  }
}

export function savePromptFilters(filters: PromptFilters): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalize(filters)));
  } catch {
    // Remembering the filters is optional.
  }
}

export function usePromptFilters() {
  const [filters, setFilters] = useState(loadPromptFilters);
  const update = useCallback((patch: Partial<PromptFilters> | ((current: PromptFilters) => Partial<PromptFilters>)) => {
    setFilters((current) => {
      const next = normalize({ ...current, ...(typeof patch === 'function' ? patch(current) : patch) });
      savePromptFilters(next);
      return next;
    });
  }, []);
  return [filters, update] as const;
}
