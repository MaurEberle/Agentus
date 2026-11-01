const MAX_TAG_LENGTH = 48;

export type TagMatch = 'and' | 'or';

/** Empty selection matches everything. AND needs every tag, OR any one of them. */
export function matchesTags(
  itemTags: readonly string[] | undefined,
  selected: readonly string[],
  mode: TagMatch,
): boolean {
  if (selected.length === 0) return true;
  const tags = itemTags ?? [];
  if (mode === 'and') return selected.every((tag) => tags.includes(tag));
  return selected.some((tag) => tags.includes(tag));
}

/**
 * Tags that can still be combined with the current AND selection.
 * `null` means every tag stays available (OR, or nothing selected yet).
 * Already selected tags stay available so they can be turned off.
 */
export function compatibleTags(
  tagSets: readonly (readonly string[])[],
  selected: readonly string[],
  mode: TagMatch,
): ReadonlySet<string> | null {
  if (mode !== 'and' || selected.length === 0) return null;
  const allowed = new Set<string>(selected);
  for (const tags of tagSets) {
    if (!selected.every((tag) => tags.includes(tag))) continue;
    for (const tag of tags) allowed.add(tag);
  }
  return allowed;
}

export function normalizeTag(raw: string): string {
  return raw.trim().replace(/\s+/g, ' ').slice(0, MAX_TAG_LENGTH);
}

export function parseTagTokens(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(/[,;\n]+/)) {
    const tag = normalizeTag(part);
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
  }
  return out;
}

export function mergeTags(existing: string[], incoming: string[]): string[] {
  const seen = new Set(existing);
  const out = [...existing];
  for (const item of incoming) {
    const tag = normalizeTag(item);
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
  }
  return out;
}

/** Drop seed tags that left `next`, keep other current tags, then add `next`. */
/** Tags present on every item. Empty selection yields none. Order follows the first item. */
export function sharedTagList(items: readonly { tags?: readonly string[] | null }[]): string[] {
  if (items.length === 0) return [];
  const [first, ...rest] = items;
  const firstTags = first.tags ?? [];
  return firstTags.filter((tag) => rest.every((item) => (item.tags ?? []).includes(tag)));
}

export function applyTagEdit(current: string[] | undefined, seed: string[], next: string[]): string[] {
  const removed = new Set(seed.filter((tag) => !next.includes(tag)));
  const kept = (current ?? []).filter((tag) => !removed.has(tag));
  return mergeTags(kept, next);
}
