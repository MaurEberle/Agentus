import type { NetworkListItem } from '@/modules/dashboard/model';
import { matchesTags, sharedTagList, type TagMatch } from '@/lib/tags';
import type { NetworksKindFilter, NetworksSortDir, NetworksSortKey } from '@/modules/networks/store';

export function uniqueTags(items: NetworkListItem[]): string[] {
  const tags = new Set<string>();
  for (const item of items) {
    for (const tag of item.tags ?? []) tags.add(tag);
  }
  return [...tags].sort((a, b) => a.localeCompare(b));
}

export function sharedTags(items: NetworkListItem[]): string[] {
  return sharedTagList(items);
}

type NetworkScope = { onlyValid: boolean; kind: NetworksKindFilter };

/** The kind switch and "only valid": the networks every other filter, the tag cloud included, works on. */
function inScope(item: NetworkListItem, scope: NetworkScope): boolean {
  if (scope.onlyValid && item.validationStatus !== 'valid') return false;
  // Without a kind (older backend) a network counts as linear, as it has no orchestrator known.
  return scope.kind === 'all' || (item.kind ?? 'linear') === scope.kind;
}

export function scopeNetworks(items: NetworkListItem[], scope: NetworkScope): NetworkListItem[] {
  return items.filter((item) => inScope(item, scope));
}

/**
 * Tags for the tag cloud: those of the networks in scope, plus any still selected, so a
 * tag chosen before the kind switch moved can still be cleared.
 */
export function cloudTags(scoped: NetworkListItem[], selected: string[]): string[] {
  return [...new Set([...uniqueTags(scoped), ...selected])].sort((a, b) => a.localeCompare(b));
}

export function applyNetworkFilters(
  items: NetworkListItem[],
  filters: {
    query: string;
    tagFilter: string[];
    tagMode: TagMatch;
    onlyValid: boolean;
    kind: NetworksKindFilter;
    sortKey: NetworksSortKey;
    sortDir: NetworksSortDir;
  },
): NetworkListItem[] {
  const query = filters.query.trim().toLowerCase();
  let list = items.filter((item) => {
    if (!inScope(item, filters)) return false;
    if (!matchesTags(item.tags, filters.tagFilter, filters.tagMode)) return false;
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
