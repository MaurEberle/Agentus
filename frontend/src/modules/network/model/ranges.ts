/**
 * Ranges of number settings on nodes. Same values as backend/app/run/node_values.py;
 * the backend validates them again before a run and clamps them when it compiles.
 */

export type NumberRange = { min: number; max: number; integer?: boolean };

export const TEMPERATURE_MIN = 0;
export const TEMPERATURE_MAX = 2;
const TEMPERATURE_MAX_BY_PROVIDER: Record<string, number> = { anthropic: 1 };
export const MAX_TOKENS_MIN = 64;
export const MAX_TOKENS_MAX = 262_144;
export const TOP_K_RANGE: NumberRange = { min: 1, max: 20, integer: true };
export const SCORE_RANGE: NumberRange = { min: 0, max: 1 };
export const TERMINAL_TIMEOUT_RANGE: NumberRange = { min: 5, max: 600, integer: true };
export const SEARCH_RESULTS_RANGE: NumberRange = { min: 1, max: 10, integer: true };
export const AGENT_MISS_RANGE: NumberRange = { min: 1, max: 8, integer: true };
/** Defaults the backend uses when a field is empty (shown as placeholder). */
export const DEFAULT_TOP_K = 4;
export const DEFAULT_SCORE = 0;
export const DEFAULT_TERMINAL_TIMEOUT = 30;
export const DEFAULT_SEARCH_RESULTS = 5;
export const DEFAULT_AGENT_MISS = 2;

export function temperatureRange(provider: string): NumberRange {
  return { min: TEMPERATURE_MIN, max: TEMPERATURE_MAX_BY_PROVIDER[provider] ?? TEMPERATURE_MAX };
}

/** Max tokens: whole number, and below the node context when one is set. */
export function maxTokensRange(numCtx: unknown): NumberRange {
  const context = typeof numCtx === 'number' && Number.isFinite(numCtx) && numCtx > 0 ? numCtx : null;
  const max = context === null ? MAX_TOKENS_MAX : Math.max(MAX_TOKENS_MIN, Math.min(MAX_TOKENS_MAX, context - 1));
  return { min: MAX_TOKENS_MIN, max, integer: true };
}

function isUnset(value: unknown): boolean {
  return value === undefined || value === null || value === '';
}

export function inRange(value: unknown, range: NumberRange): boolean {
  if (typeof value !== 'number' || !Number.isFinite(value)) return false;
  if (range.integer && !Number.isInteger(value)) return false;
  return value >= range.min && value <= range.max;
}

/** Validation message keys for temperature and max tokens (graph.llm.temperature, …). */
export function llmRangeIssues(data: Record<string, unknown>): string[] {
  const issues: string[] = [];
  const provider = typeof data.provider === 'string' && data.provider ? data.provider : 'ollama';
  if (!isUnset(data.temperature) && !inRange(data.temperature, temperatureRange(provider))) {
    issues.push('network.validation.llmTemperature');
  }
  if (!isUnset(data.maxTokens)) {
    if (!inRange(data.maxTokens, { min: MAX_TOKENS_MIN, max: MAX_TOKENS_MAX, integer: true })) {
      issues.push('network.validation.llmMaxTokens');
    } else if (typeof data.numCtx === 'number' && data.numCtx > 0 && (data.maxTokens as number) >= data.numCtx) {
      issues.push('network.validation.llmMaxTokensContext');
    }
  }
  return issues;
}

/** Validation message keys for topK and score threshold (graph.knowledge.topK, …). */
export function knowledgeRangeIssues(data: Record<string, unknown>): string[] {
  const issues: string[] = [];
  if (!isUnset(data.topK) && !inRange(data.topK, TOP_K_RANGE)) issues.push('network.validation.knowledgeTopK');
  if (!isUnset(data.scoreThreshold) && !inRange(data.scoreThreshold, SCORE_RANGE)) {
    issues.push('network.validation.knowledgeScore');
  }
  return issues;
}
