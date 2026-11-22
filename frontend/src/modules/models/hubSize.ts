/** "8", "0.6" or "0,6" as billions; null for anything else. */
export function billions(raw: string): string | null {
  const text = raw.trim().replace(',', '.');
  if (!text || !/^\d+(\.\d+)?$/.test(text)) return null;
  return text;
}

/**
 * The backend's size filter: "min:3B,max:8B", one side only, or "any". Swapped bounds are put
 * right; `capB` (what fits the GPU) lowers the maximum.
 */
export function sizeQuery(minRaw: string, maxRaw: string, capB: number | null = null): string {
  let minimum = billions(minRaw);
  let maximum = billions(maxRaw);
  if (minimum && maximum && Number(minimum) > Number(maximum)) {
    [minimum, maximum] = [maximum, minimum];
  }
  if (capB != null && capB > 0 && (maximum == null || Number(maximum) > capB)) maximum = String(capB);
  const parts = [minimum ? `min:${minimum}B` : '', maximum ? `max:${maximum}B` : ''].filter(Boolean);
  return parts.join(',') || 'any';
}
