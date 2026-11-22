/**
 * Whether a model fits the GPU, judged from its weight count at Q4_K_M, the quant the hub
 * pane picks first. llama.cpp's Q4_K_M averages about 4.85 bits per weight.
 */
const Q4_BYTES_PER_WEIGHT = 4.85 / 8;
/** Weights up to this share of VRAM leave room for the KV cache and the runtime. */
const FITS_SHARE = 0.8;
/** Up to this share it still loads, with little room for context. */
const TIGHT_SHARE = 0.95;

export type GpuFit = 'fits' | 'tight' | 'large';

/** Minimum context choices, in tokens. Round thousands, so 131072 and 128000 both count as 128k. */
export const CONTEXT_STEPS = [32_000, 64_000, 128_000, 256_000] as const;

export function q4Bytes(parameterCount: number): number {
  return parameterCount * Q4_BYTES_PER_WEIGHT;
}

export function gpuFit(parameterCount: number | undefined, vramBytes: number): GpuFit | null {
  if (!parameterCount || parameterCount <= 0 || vramBytes <= 0) return null;
  const share = q4Bytes(parameterCount) / vramBytes;
  if (share <= FITS_SHARE) return 'fits';
  return share <= TIGHT_SHARE ? 'tight' : 'large';
}

/** The largest model (billions of weights, one decimal, rounded down) that still loads at Q4_K_M. */
export function maxFitBillions(vramBytes: number): number | null {
  if (vramBytes <= 0) return null;
  return Math.floor((vramBytes * TIGHT_SHARE) / Q4_BYTES_PER_WEIGHT / 1e8) / 10;
}

/** 131072 and 128000 → "128k", 1048576 → "1M". */
export function contextLabel(tokens: number): string {
  if (tokens >= 1_000_000) {
    const millions = tokens % 1_048_576 === 0 ? tokens / 1_048_576 : tokens / 1_000_000;
    return `${Number(millions.toFixed(1))}M`;
  }
  const thousands = tokens % 1024 === 0 ? tokens / 1024 : tokens / 1000;
  return `${Math.round(thousands)}k`;
}
