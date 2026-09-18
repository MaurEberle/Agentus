import type { NetworkListItem } from '@/modules/dashboard/model';
import type { NetworksSortDir, NetworksSortKey } from '@/modules/networks/store';

export function uniqueTags(items: NetworkListItem[]): string[] {
  const tags = new Set<string>();
  for (const item of items) {
    for (const tag of item.tags ?? []) tags.add(tag);
  }
  return [...tags].sort((a, b) => a.localeCompare(b));
}

export function applyNetworkFilters(
  items: NetworkListItem[],
  filters: {
    query: string;
    tagFilter: string[];
    onlyValid: boolean;
    onlyActive: boolean;
    sortKey: NetworksSortKey;
    sortDir: NetworksSortDir;
  },
): NetworkListItem[] {
  const query = filters.query.trim().toLowerCase();
  let list = items.filter((item) => {
    if (filters.onlyValid && item.validationStatus !== 'valid') return false;
    if (filters.onlyActive && !item.isActive) return false;
    if (filters.tagFilter.length > 0) {
      const tags = item.tags ?? [];
      if (!filters.tagFilter.some((tag) => tags.includes(tag))) return false;
    }
    if (!query) return true;
    const haystack = `${item.name} ${item.description ?? ''} ${(item.tags ?? []).join(' ')}`.toLowerCase();
    return haystack.includes(query);
  });
  const dir = filters.sortDir === 'asc' ? 1 : -1;
  list = [...list].sort((a, b) => {
    if (filters.sortKey === 'name') return a.name.localeCompare(b.name) * dir;
    const aMissing = filters.sortKey === 'lastUsedAt' && !a.lastUsedAt;
    const bMissing = filters.sortKey === 'lastUsedAt' && !b.lastUsedAt;
    if (aMissing && !bMissing) return 1;
    if (!aMissing && bMissing) return -1;
    const av = Date.parse(filters.sortKey === 'lastUsedAt' ? (a.lastUsedAt ?? '') : a.updatedAt);
    const bv = Date.parse(filters.sortKey === 'lastUsedAt' ? (b.lastUsedAt ?? '') : b.updatedAt);
    const an = Number.isNaN(av) ? 0 : av;
    const bn = Number.isNaN(bv) ? 0 : bv;
    if (an === bn) return a.name.localeCompare(b.name);
    return (an - bn) * dir;
  });
  return list;
}

export function rangeIds(visibleIds: string[], fromId: string | null, toId: string): string[] {
  if (!fromId) return [toId];
  const from = visibleIds.indexOf(fromId);
  const to = visibleIds.indexOf(toId);
  if (from < 0 || to < 0) return [toId];
  const start = Math.min(from, to);
  const end = Math.max(from, to);
  return visibleIds.slice(start, end + 1);
}
