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

export type KvLayer = {
  bytesPerToken?: number;
  window?: number | null;
  fixedBytes?: number;
};

export type VramParts = {
  total: number;
  weights: number;
  kv: number;
  overhead: number;
  gpuOn: number;
  gpuTotal: number;
  fullLayers: number;
  swaLayers: number;
  swaWindow: number;
  fullBytesPerToken: number;
};

function sumLastN(layers: KvLayer[], on: number, ctx: number): { kv: number; full: number; swa: number; window: number; bpt: number } {
  const start = Math.max(0, layers.length - Math.min(on, layers.length));
  let kv = 0;
  let full = 0;
  let swa = 0;
  let window = 0;
  const fullBpt: number[] = [];
  for (let i = start; i < layers.length; i += 1) {
    const layer = layers[i];
    kv += layer.fixedBytes ?? 0;
    const bpt = layer.bytesPerToken ?? 0;
    if (bpt <= 0) continue;
    const win = layer.window ?? 0;
    if (win > 0) {
      swa += 1;
      window = Math.max(window, win);
      kv += bpt * Math.min(ctx, win);
    } else {
      full += 1;
      fullBpt.push(bpt);
      kv += bpt * ctx;
    }
  }
  const uniform = fullBpt.length > 0 && fullBpt.every((value) => value === fullBpt[0]) ? fullBpt[0] : 0;
  return { kv, full, swa, window, bpt: uniform };
}

export function estimateVramParts(opts: {
  weightBytes?: number | null;
  kvBytesPerToken?: number | null;
  kvSwaBytesPerToken?: number | null;
  swaWindow?: number | null;
  overheadBytes?: number | null;
  gpuLayers?: number | null;
  kvLayers?: KvLayer[] | null;
  numCtx: number;
  numGpuLayers?: number;
  numGpuPercent?: number;
}): VramParts | null {
  const weight = opts.weightBytes ?? 0;
  const kvPerToken = opts.kvBytesPerToken ?? 0;
  const kvSwaPerToken = opts.kvSwaBytesPerToken ?? 0;
  const swaWindow = opts.swaWindow ?? 0;
  const overhead = opts.overheadBytes ?? 0;
  const kvLayers = opts.kvLayers ?? [];
  const hasLayers = kvLayers.some((layer) => (layer.bytesPerToken ?? 0) > 0 || (layer.fixedBytes ?? 0) > 0);
  if (weight <= 0 && kvPerToken <= 0 && kvSwaPerToken <= 0 && !hasLayers) return null;
  const total = kvLayers.length > 0 ? kvLayers.length : (opts.gpuLayers ?? 0);
  const on =
    total > 0
      ? resolveGpuLayers(Number(opts.numGpuLayers), Number(opts.numGpuPercent), total)
      : 0;
  const frac = total > 0 ? on / total : 1;
  const ctx = Number.isFinite(opts.numCtx) && opts.numCtx > 0 ? opts.numCtx : 0;
  const weights = Math.round(weight * frac);
  const reserve = Math.round(overhead * frac);
  if (hasLayers) {
    const sliced = sumLastN(kvLayers, on, ctx);
    return {
      total: weights + sliced.kv + reserve,
      weights,
      kv: Math.round(sliced.kv),
      overhead: reserve,
      gpuOn: on,
      gpuTotal: total,
      fullLayers: sliced.full,
      swaLayers: sliced.swa,
      swaWindow: sliced.window,
      fullBytesPerToken: sliced.bpt,
    };
  }
  const swaTokens = swaWindow > 0 ? Math.min(ctx, swaWindow) : ctx;
  const kv = Math.round((kvPerToken * ctx + kvSwaPerToken * swaTokens) * frac);
  return {
    total: weights + kv + reserve,
    weights,
    kv,
    overhead: reserve,
    gpuOn: on,
    gpuTotal: total,
    fullLayers: 0,
    swaLayers: 0,
    swaWindow: swaWindow > 0 ? swaWindow : 0,
    fullBytesPerToken: 0,
  };
}
