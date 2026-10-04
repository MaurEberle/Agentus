export function snapGpuPercent(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(100, Math.max(10, Math.round(value / 10) * 10));
}

export function offloadLayers(percent: number, total: number): number {
  const pct = snapGpuPercent(percent);
  if (pct >= 100) return total;
  return Math.max(1, Math.min(total, Math.floor((total * pct + 50) / 100)));
}

export function clampGpuLayers(value: number, total: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(total) || total < 1) return 1;
  return Math.min(total, Math.max(1, Math.round(value)));
}

export function resolveGpuLayers(
  storedLayers: number,
  storedPercent: number,
  total: number,
): number {
  if (Number.isFinite(storedLayers) && storedLayers >= 1) {
    return clampGpuLayers(storedLayers, total);
  }
  if (Number.isFinite(storedPercent) && storedPercent >= 10) {
    return offloadLayers(storedPercent, total);
  }
  return total;
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
  numGpuLayers?: number;
  numGpuPercent?: number;
}): VramParts | null {
  const weight = opts.weightBytes ?? 0;
  const kvPerToken = opts.kvBytesPerToken ?? 0;
  const overhead = opts.overheadBytes ?? 0;
  if (weight <= 0 && kvPerToken <= 0) return null;
  const layers = opts.gpuLayers ?? null;
  const frac =
    layers != null && layers > 0
      ? resolveGpuLayers(Number(opts.numGpuLayers), Number(opts.numGpuPercent), layers) / layers
      : 1;
  const ctx = Number.isFinite(opts.numCtx) && opts.numCtx > 0 ? opts.numCtx : 0;
  const weights = Math.round(weight * frac);
  const kv = Math.round(kvPerToken * ctx * frac);
  const reserve = Math.round(overhead * frac);
  return { total: weights + kv + reserve, weights, kv, overhead: reserve };
}
