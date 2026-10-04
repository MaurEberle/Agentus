export function snapGpuPercent(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(100, Math.max(10, Math.round(value / 10) * 10));
}

export function offloadLayers(percent: number, total: number): number {
  const pct = snapGpuPercent(percent);
  if (pct >= 100) return total;
  return Math.max(1, Math.min(total, Math.floor((total * pct + 50) / 100)));
}

export type VramParts = {
  total: number;
  weights: number;
  kv: number;
  overhead: number;
};

export function estimateVramParts(opts: {
  weightBytes?: number | null;
  kvBytesPerToken?: number | null;
  overheadBytes?: number | null;
  gpuLayers?: number | null;
  numCtx: number;
  numGpuPercent: number;
}): VramParts | null {
  const weight = opts.weightBytes ?? 0;
  const kvPerToken = opts.kvBytesPerToken ?? 0;
  const overhead = opts.overheadBytes ?? 0;
  if (weight <= 0 && kvPerToken <= 0) return null;
  const layers = opts.gpuLayers ?? null;
  const frac = layers != null && layers > 0 ? offloadLayers(opts.numGpuPercent, layers) / layers : 1;
  const ctx = Number.isFinite(opts.numCtx) && opts.numCtx > 0 ? opts.numCtx : 0;
  const weights = Math.round(weight * frac);
  const kv = Math.round(kvPerToken * ctx * frac);
  const reserve = Math.round(overhead * frac);
  return { total: weights + kv + reserve, weights, kv, overhead: reserve };
}
