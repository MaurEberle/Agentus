const MAX_TAG_LENGTH = 48;

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
export function applyTagEdit(current: string[] | undefined, seed: string[], next: string[]): string[] {
  const removed = new Set(seed.filter((tag) => !next.includes(tag)));
  const kept = (current ?? []).filter((tag) => !removed.has(tag));
  return mergeTags(kept, next);
}
