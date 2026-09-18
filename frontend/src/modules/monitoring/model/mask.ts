const SECRET_KEY = /^(api[_-]?key|token|password|authorization|secret|bearer)$/i;

export function maskText(input: string): string {
  return input
    .replace(/(Bearer\s+)([A-Za-z0-9._\-+=/]+)/gi, '$1***')
    .replace(/\bsk-[A-Za-z0-9\-_]{8,}\b/g, 'sk-***')
    .replace(
      /\b(api[_-]?key|token|password|authorization|secret)\b(\s*[:=]\s*)(["']?)([^,\s"']+)\3/gi,
      '$1$2$3***',
    );
}

export function maskSecrets(value: unknown): unknown {
  if (typeof value === 'string') return maskText(value);
  if (Array.isArray(value)) return value.map((item) => maskSecrets(item));
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      result[key] = SECRET_KEY.test(key) ? '***' : maskSecrets(nested);
    }
    return result;
  }
  return value;
}

export function maskLog(event: {
  message: string;
  payload?: unknown;
  stack?: string;
}): { message: string; payload?: unknown; stack?: string } {
  return {
    message: maskText(event.message),
    payload: event.payload === undefined ? undefined : maskSecrets(event.payload),
    stack: event.stack ? maskText(event.stack) : undefined,
  };
}
