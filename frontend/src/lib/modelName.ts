const REGISTRY_HOSTS = new Set(['hf.co', 'huggingface.co', 'www.huggingface.co']);

export type ModelLabel = {
  raw: string;
  name: string;
  publisher: string | null;
};

/** Visible model name. The stored id is unchanged. */
export function modelLabel(raw: string): ModelLabel {
  const text = raw.trim();
  if (!text) return { raw: text, name: text, publisher: null };
  const slash = text.lastIndexOf('/');
  const colon = text.lastIndexOf(':');
  let path = text;
  let suffix = '';
  if (colon > slash) {
    path = text.slice(0, colon);
    suffix = text.slice(colon + 1);
  }
  const parts = path.split('/').filter(Boolean);
  while (parts.length > 1 && REGISTRY_HOSTS.has(parts[0].toLowerCase())) parts.shift();
  const repo = parts.pop() ?? path;
  const publisher = parts.length > 0 ? parts.join('/') : null;
  const name = suffix && suffix.toLowerCase() !== 'latest' ? `${repo}:${suffix}` : repo;
  return { raw: text, name, publisher };
}

/** What the runtime list knows about a model, for the hover card in model pickers. */
export type ModelFacts = {
  parameterSize?: string;
  quantization?: string;
  sizeBytes?: number;
};

export function modelFactsMap(
  items: readonly { name: string; parameterSize?: string; quantization?: string; sizeBytes?: number }[],
): Map<string, ModelFacts> {
  return new Map(
    items.map((item) => [item.name, { parameterSize: item.parameterSize, quantization: item.quantization, sizeBytes: item.sizeBytes }]),
  );
}

/** Ollama's "32.0B", "30.5B", "566.70M" → "32B", "30.5B", "566.7M". Unknown shapes stay as they are. */
export function formatParameters(raw: string | undefined): string | null {
  const text = (raw ?? '').trim();
  if (!text) return null;
  const match = /^(\d+(?:\.\d+)?)\s*([KMBT])$/i.exec(text);
  if (!match) return text;
  const value = Number(match[1]);
  const shown = Number.isInteger(value) ? String(value) : String(Number(value.toFixed(1)));
  return `${shown}${match[2].toUpperCase()}`;
}

/** Publisher in dropdowns. The stored id, when the visible name dropped :latest. */
export function modelHover(label: ModelLabel): string | undefined {
  if (label.publisher) return label.publisher;
  if (label.raw !== label.name) return label.raw;
  return undefined;
}
