const DISCRETE_BYTES = 512 * 1024 * 1024;

export type VramGpu = {
  name?: string;
  vramTotalBytes: number;
  inference?: boolean;
};

/** GPUs one runtime can fill together. Falls back when the host sent no flag. */
export function inferenceGpus<T extends VramGpu>(gpus: T[]): T[] {
  const flagged = gpus.filter((gpu) => gpu.inference);
  if (flagged.length > 0) return flagged;
  const discrete = gpus.filter((gpu) => gpu.vramTotalBytes >= DISCRETE_BYTES);
  if (discrete.length > 0) return discrete;
  if (gpus.length === 0) return [];
  return [gpus.reduce((best, gpu) => (gpu.vramTotalBytes > best.vramTotalBytes ? gpu : best))];
}

export function inferenceVramBytes(gpus: VramGpu[]): number {
  return inferenceGpus(gpus).reduce((sum, gpu) => sum + Math.max(0, gpu.vramTotalBytes), 0);
}

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

export type MoeFit = {
  gpuBytes: number;
  ramBytes: number;
  expertsOnGpu: number;
  expertLayers: number;
  attentionLayersOnGpu: number;
  nonExpertOnGpu: number;
  expertOnGpuBytes: number;
  kvBytes: number;
  overheadBytes: number;
};

/** MoE with no explicit partial layer choice. The runtime then omits num_gpu. */
export function moeLeavesPlacementToRuntime(opts: {
  expertCount?: number | null;
  gpuLayers?: number | null;
  numGpuLayers?: number | null;
  numGpuPercent?: number | null;
  gpuPlacement?: string | null;
}): boolean {
  if ((opts.expertCount ?? 0) <= 1) return false;
  if (opts.gpuPlacement === 'layers') return false;
  const total = opts.gpuLayers ?? 0;
  const stored = opts.numGpuLayers;
  if (total > 0 && Number.isFinite(stored) && (stored as number) >= 1 && (stored as number) < total) return false;
  const percent = opts.numGpuPercent;
  if (Number.isFinite(percent) && (percent as number) >= 10 && (percent as number) < 100) return false;
  return true;
}

export function hasWindowedKv(opts: {
  kvSwaBytesPerToken?: number | null;
  swaWindow?: number | null;
  kvLayers?: KvLayer[] | null;
}): boolean {
  if ((opts.kvSwaBytesPerToken ?? 0) > 0 || (opts.swaWindow ?? 0) > 0) return true;
  const layers = opts.kvLayers ?? [];
  if (layers.some((layer) => (layer.window ?? 0) > 0)) return true;
  if (layers.length === 0) return false;
  const active = layers.filter((layer) => (layer.bytesPerToken ?? 0) > 0 || (layer.fixedBytes ?? 0) > 0).length;
  return active > 0 && active < layers.length;
}

function kvBytesForOn(
  kvLayers: KvLayer[],
  kvBytesPerToken: number,
  on: number,
  layers: number,
  ctx: number,
): number {
  const hasLayers = kvLayers.some((layer) => (layer.bytesPerToken ?? 0) > 0 || (layer.fixedBytes ?? 0) > 0);
  if (hasLayers) return sumLastN(kvLayers, on, ctx).kv;
  if (layers < 1) return 0;
  return Math.floor((kvBytesPerToken * ctx * on) / layers);
}

/** Same integer fit as backend fit_moe. The byte split arrives already computed. */
export function fitMoe(opts: {
  nonExpertBytes?: number | null;
  routedExpertBytes?: number | null;
  overheadBytes?: number | null;
  gpuLayers?: number | null;
  kvLayers?: KvLayer[] | null;
  kvBytesPerToken?: number | null;
  leadingDenseBlocks?: number | null;
  numCtx: number;
  poolBytes: number;
}): MoeFit | null {
  const kvLayers = opts.kvLayers ?? [];
  const layers = opts.gpuLayers && opts.gpuLayers > 0 ? opts.gpuLayers : kvLayers.length;
  const routed = opts.routedExpertBytes ?? 0;
  const non = opts.nonExpertBytes ?? 0;
  const pool = opts.poolBytes;
  if (layers < 1 || routed <= 0 || non <= 0 || pool <= 0) return null;
  let leading = opts.leadingDenseBlocks ?? 0;
  if (!Number.isFinite(leading) || leading < 0) leading = 0;
  if (leading > layers) leading = layers;
  const expertLayers = layers - leading;
  if (expertLayers < 1) return null;
  const overheadTotal = opts.overheadBytes ?? 0;
  const perToken = opts.kvBytesPerToken ?? 0;
  const ctx = Number.isFinite(opts.numCtx) && opts.numCtx > 0 ? opts.numCtx : 0;
  const fixed = (on: number) => {
    const weights = Math.floor((non * on) / layers);
    const overhead = Math.floor((overheadTotal * on) / layers);
    const kv = kvBytesForOn(kvLayers, perToken, on, layers, ctx);
    return { weights, overhead, kv, total: weights + overhead + kv };
  };
  let on = layers;
  while (on > 0 && fixed(on).total > pool) on -= 1;
  const base = fixed(on);
  const room = Math.max(0, pool - base.total);
  const cap = Math.min(on, expertLayers);
  let expertsOn = cap > 0 ? Math.min(cap, Math.floor((room * expertLayers) / routed)) : 0;
  while (expertsOn > 0 && Math.floor((routed * expertsOn) / expertLayers) > room) expertsOn -= 1;
  const expertOnGpu = Math.floor((routed * expertsOn) / expertLayers);
  return {
    gpuBytes: base.weights + base.kv + base.overhead + expertOnGpu,
    ramBytes: Math.max(0, non - base.weights) + Math.max(0, routed - expertOnGpu),
    expertsOnGpu: expertsOn,
    expertLayers,
    attentionLayersOnGpu: on,
    nonExpertOnGpu: base.weights,
    expertOnGpuBytes: expertOnGpu,
    kvBytes: base.kv,
    overheadBytes: base.overhead,
  };
}
