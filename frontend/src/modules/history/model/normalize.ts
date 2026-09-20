import type { LlmProvider, RunDetail, RunSummary } from '@/modules/history/model/types';

type RawModel = string | { provider?: string; model?: string; name?: string };

type RawRun = {
  id?: string;
  runId?: string;
  networkId: string;
  networkName: string;
  startedAt: string;
  endedAt?: string | null;
  outcome: RunSummary['outcome'];
  errorMessage?: string | null;
  errorClass?: RunSummary['errorClass'];
  errorNodeId?: string | null;
  errorNodeName?: string | null;
  models?: RawModel[];
  graphSnapshot?: RunDetail['graphSnapshot'];
  chat?: RunDetail['chat'];
  calls?: RunDetail['calls'];
  steps?: RunDetail['steps'];
};

function asProvider(value: string | undefined): LlmProvider {
  if (
    value === 'xai' ||
    value === 'openai' ||
    value === 'anthropic' ||
    value === 'gemini' ||
    value === 'openai_compat'
  ) {
    return value;
  }
  return 'ollama';
}

export function normalizeModels(models: RawModel[] | undefined): RunSummary['models'] {
  const items: RunSummary['models'] = [];
  for (const item of models ?? []) {
    if (typeof item === 'string') {
      if (item.trim()) items.push({ provider: 'ollama', model: item });
      continue;
    }
    const name = (item.model || item.name || '').trim();
    if (!name) continue;
    items.push({ provider: asProvider(item.provider), model: name });
  }
  return items;
}

export function normalizeRun(raw: RawRun): RunSummary {
  return {
    runId: raw.runId || raw.id || '',
    networkId: raw.networkId,
    networkName: raw.networkName,
    startedAt: raw.startedAt,
    endedAt: raw.endedAt ?? undefined,
    outcome: raw.outcome,
    errorMessage: raw.errorMessage ?? undefined,
    errorClass: raw.errorClass,
    errorNodeId: raw.errorNodeId ?? undefined,
    errorNodeName: raw.errorNodeName ?? undefined,
    models: normalizeModels(raw.models),
  };
}

export function normalizeRunDetail(raw: RawRun): RunDetail {
  return {
    ...normalizeRun(raw),
    graphSnapshot: raw.graphSnapshot,
    chat: raw.chat,
    calls: raw.calls ?? [],
    steps: raw.steps ?? [],
  };
}
