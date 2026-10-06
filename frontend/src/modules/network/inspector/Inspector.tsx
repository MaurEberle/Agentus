import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ModelCombobox } from '@/components/ModelCombobox';
import { TagInput } from '@/components/TagInput';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { pickFolderPath } from '@/lib/pickFolder';
import {
  useEditorCredentialsQuery,
  useEditorNetworksQuery,
  useMcpServersQuery,
  reindexNetworkKnowledge,
  testLlmConnection,
} from '@/modules/network/api';
import { uniqueTags } from '@/modules/networks/model/filter';
import { useHostResourcesQuery, useMcpRecipesQuery, useModelStatsQuery, useRuntimeModelsQuery } from '@/modules/settings/api';
import type { GraphNode, ValidationIssue } from '@/modules/network/model/document';
import { newId } from '@/modules/network/model/document';
import { editorDeleteSelection, editorUpdateNodeData, useNetworkEditor } from '@/modules/network/store';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import { formatBytes, formatPercent, meterTone } from '@/modules/monitoring/model/format';
import { estimateVramParts, resolveGpuLayers } from '@/modules/network/inspector/vram';
import {
  EMBEDDING_PROVIDERS,
  LLM_PROVIDERS,
  credentialMatchesProvider,
  credentialMatchesToolKind,
  embeddingNeedsCredential,
  isCloudCatalogProvider,
  isEmbeddingModelName,
  isForbiddenDataRoot,
  providerNeedsCredential,
  type EmbeddingProvider,
  type LlmProvider,
} from '@/modules/settings/model';

export function Inspector({
  issues,
  readOnly,
  isActive,
  isRunning,
}: {
  issues: ValidationIssue[];
  readOnly: boolean;
  isActive: boolean;
  isRunning: boolean;
}) {
  const { t } = useTranslation();
  const document = useNetworkEditor((state) => state.document);
  const selectedNodeIds = useNetworkEditor((state) => state.selectedNodeIds);
  const setMeta = useNetworkEditor((state) => state.setMeta);
  const select = useNetworkEditor((state) => state.select);
  const networks = useEditorNetworksQuery();
  const tagSuggestions = useMemo(() => uniqueTags(networks.data?.items ?? []), [networks.data?.items]);

  if (selectedNodeIds.length > 1) {
    return (
      <div className="space-y-3 p-3">
        <p className="text-sm text-muted-foreground">
          {t('network.inspector.multi', { count: selectedNodeIds.length })}
        </p>
        <Button type="button" variant="destructive" size="sm" disabled={readOnly} onClick={() => editorDeleteSelection()}>
          {t('network.context.delete')}
        </Button>
      </div>
    );
  }

  const node = selectedNodeIds[0]
    ? document.nodes.find((item) => item.id === selectedNodeIds[0])
    : undefined;

  if (!node) {
    return (
      <div className="space-y-4 p-3">
        <header>
          <h2 className="text-sm font-semibold">{t('network.inspector.graph.title')}</h2>
          <div className="mt-2 flex flex-wrap gap-1">
            <Badge variant={issues.length ? 'destructive' : 'default'}>
              {issues.length ? t('network.badge.invalid') : t('network.badge.valid')}
            </Badge>
            {isActive ? <Badge>{t('network.badge.active')}</Badge> : null}
            {isRunning ? <Badge variant="warning">{t('network.badge.running')}</Badge> : null}
          </div>
        </header>
        <Field label={t('network.inspector.graph.name')}>
          <Input
            value={document.name}
            disabled={readOnly}
            onChange={(event) => setMeta({ name: event.target.value })}
          />
        </Field>
        <Field label={t('network.inspector.graph.description')}>
          <Textarea
            value={document.description ?? ''}
            disabled={readOnly}
            onChange={(event) => setMeta({ description: event.target.value })}
          />
        </Field>
        <Field label={t('network.inspector.graph.tags')} htmlFor="network-graph-tags">
          <TagInput
            id="network-graph-tags"
            value={document.tags ?? []}
            disabled={readOnly}
            placeholder={t('network.inspector.graph.tagsPlaceholder')}
            addLabel={t('network.inspector.graph.addTag')}
            removeLabel={(tag) => t('network.inspector.graph.removeTag', { tag })}
            suggestions={tagSuggestions}
            describedBy="network-graph-tags-hint"
            onChange={(tags) => setMeta({ tags })}
          />
          <p id="network-graph-tags-hint" className="text-xs text-muted-foreground">
            {t('network.inspector.graph.tagsHint')}
          </p>
        </Field>
        <p className="text-xs text-muted-foreground">
          {t('network.inspector.graph.stats', {
            nodes: document.nodes.length,
            edges: document.edges.length,
          })}
        </p>
        {issues.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {issues.map((issue, index) => (
              <li key={`${issue.messageKey}-${issue.nodeId ?? index}`}>
                <button
                  type="button"
                  className="text-left text-destructive hover:underline"
                  onClick={() => issue.nodeId && select([issue.nodeId])}
                >
                  {t(issue.messageKey, issue.values)}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t('network.inspector.graph.noIssues')}</p>
        )}
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4 overflow-x-hidden p-3">
      <h2 className="text-sm font-semibold">{t(`network.palette.${node.type}`)}</h2>
      <DisplayNameField node={node} readOnly={readOnly} />
      {node.type === 'llm' ? <LlmFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'agent' ? <AgentFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'orchestrator' ? <OrchestratorFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'tool' ? <ToolFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'mcp' ? <McpFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'knowledge' ? <KnowledgeFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'router' ? <RouterFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'chat_input' ? <ChatInputFields node={node} readOnly={readOnly} /> : null}
      {issues.filter((issue) => issue.nodeId === node.id).map((issue) => (
        <p key={issue.messageKey} className="text-sm text-destructive">
          {t(issue.messageKey, issue.values)}
        </p>
      ))}
    </div>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

function formatTokenCount(value: number): string {
  if (value >= 1_000_000) {
    const millions = value / 1_000_000;
    return `${Number.isInteger(millions) ? millions : millions.toFixed(1)}M`;
  }
  if (value >= 10_000) return `${Math.round(value / 1000)}k`;
  return value.toLocaleString();
}

function sliderStep(min: number, max: number): number {
  const span = max - min;
  if (span <= 4096) return 256;
  if (span <= 16384) return 512;
  if (span <= 65536) return 1024;
  return 2048;
}

function ContextWindowField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const provider = String(node.data.provider ?? 'ollama');
  const model = String(node.data.model ?? '');
  const credentialId = String(node.data.credentialId ?? '') || undefined;
  const local = provider === 'ollama';
  const stats = useModelStatsQuery({
    provider: provider as LlmProvider,
    model,
    credentialId,
    baseUrl: String(node.data.baseUrl ?? '') || undefined,
    enabled: Boolean(model),
  });
  const min = stats.data?.contextMin;
  const max = stats.data?.contextMax;
  const steps = stats.data?.steps ?? [];
  const current = Number(node.data.numCtx);

  useEffect(() => {
    if (readOnly || max == null || min == null) return;
    if (!Number.isFinite(current) || current < min || current > max) {
      editorUpdateNodeData(node.id, { numCtx: max });
    }
  }, [current, max, min, node.id, readOnly]);

  if (stats.isPending && !stats.data) {
    return (
      <Field label={t('network.inspector.llm.numCtx')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numCtxLoading')}</p>
      </Field>
    );
  }
  if (max == null || min == null) {
    return (
      <Field label={t('network.inspector.llm.numCtx')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numCtxUnavailable')}</p>
      </Field>
    );
  }

  const value = Number.isFinite(current) ? Math.min(max, Math.max(min, current)) : max;

  return (
    <Field label={t('network.inspector.llm.numCtx')}>
      {local ? (
        <>
          <input
            type="range"
            min={min}
            max={max}
            step={sliderStep(min, max)}
            value={value}
            disabled={readOnly}
            className="w-full accent-primary"
            onChange={(event) => editorUpdateNodeData(node.id, { numCtx: Number(event.target.value) })}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{formatTokenCount(min)}</span>
            <span className="font-medium text-foreground">{formatTokenCount(value)}</span>
            <span>{formatTokenCount(max)}</span>
          </div>
        </>
      ) : (
        <Select
          value={String(value)}
          disabled={readOnly}
          onValueChange={(next) => editorUpdateNodeData(node.id, { numCtx: Number(next) })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(steps.length > 0 ? steps : [max]).map((step) => (
              <SelectItem key={step} value={String(step)}>
                {formatTokenCount(step)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numCtxHint')}</p>
    </Field>
  );
}

function GpuOffloadField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const provider = String(node.data.provider ?? 'ollama');
  const model = String(node.data.model ?? '');
  const stats = useModelStatsQuery({
    provider: provider as LlmProvider,
    model,
    credentialId: String(node.data.credentialId ?? '') || undefined,
    baseUrl: String(node.data.baseUrl ?? '') || undefined,
    enabled: Boolean(model),
  });
  const layers = stats.data?.gpuLayers && stats.data.gpuLayers > 0 ? stats.data.gpuLayers : null;
  const value =
    layers == null
      ? 1
      : resolveGpuLayers(Number(node.data.numGpuLayers), Number(node.data.numGpuPercent), layers);

  useEffect(() => {
    if (readOnly || layers == null) return;
    if (
      node.data.numGpuLayers === value &&
      node.data.numGpuPercent === undefined &&
      node.data.numGpu === undefined
    ) {
      return;
    }
    editorUpdateNodeData(node.id, { numGpuLayers: value, numGpuPercent: undefined, numGpu: undefined });
  }, [layers, node.data.numGpu, node.data.numGpuLayers, node.data.numGpuPercent, node.id, readOnly, value]);

  if (stats.isPending && !stats.data) {
    return (
      <Field label={t('network.inspector.llm.numGpu')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numGpuLoading')}</p>
      </Field>
    );
  }
  if (layers == null) {
    return (
      <Field label={t('network.inspector.llm.numGpu')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numGpuUnavailable')}</p>
      </Field>
    );
  }

  return (
    <Field label={t('network.inspector.llm.numGpu')}>
      <input
        type="range"
        min={1}
        max={layers}
        step={1}
        value={value}
        disabled={readOnly}
        className="w-full accent-primary"
        onChange={(event) =>
          editorUpdateNodeData(node.id, {
            numGpuLayers: Number(event.target.value),
            numGpuPercent: undefined,
            numGpu: undefined,
          })
        }
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>1</span>
        <span className="font-medium text-foreground">
          {t('network.inspector.llm.numGpuLayers', { offload: value, total: layers })}
        </span>
        <span>{layers}</span>
      </div>
      <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numGpuHint')}</p>
    </Field>
  );
}

function VramNeedField({ node }: { node: GraphNode }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const provider = String(node.data.provider ?? 'ollama');
  const model = String(node.data.model ?? '');
  const stats = useModelStatsQuery({
    provider: provider as LlmProvider,
    model,
    credentialId: String(node.data.credentialId ?? '') || undefined,
    baseUrl: String(node.data.baseUrl ?? '') || undefined,
    enabled: Boolean(model),
  });
  const resources = useHostResourcesQuery({ live: false });
  const ctxRaw = Number(node.data.numCtx);
  const ctx = Number.isFinite(ctxRaw) && ctxRaw > 0 ? ctxRaw : (stats.data?.contextMax ?? 0);
  const parts = estimateVramParts({
    weightBytes: stats.data?.weightBytes,
    kvBytesPerToken: stats.data?.kvBytesPerToken,
    kvSwaBytesPerToken: stats.data?.kvSwaBytesPerToken,
    swaWindow: stats.data?.swaWindow,
    overheadBytes: stats.data?.overheadBytes,
    gpuLayers: stats.data?.gpuLayers,
    kvLayers: stats.data?.kvLayers,
    numCtx: ctx,
    numGpuLayers: Number(node.data.numGpuLayers),
    numGpuPercent: Number(node.data.numGpuPercent),
  });
  const count = (value: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
  const formula =
    parts && (parts.fullLayers > 0 || parts.swaLayers > 0)
      ? parts.swaLayers > 0
        ? t('network.inspector.llm.vramFormulaSwa', {
            on: parts.gpuOn,
            total: parts.gpuTotal,
            full: parts.fullLayers,
            swa: parts.swaLayers,
            ctx: count(ctx),
            window: count(parts.swaWindow),
          })
        : parts.fullBytesPerToken > 0
          ? t('network.inspector.llm.vramFormula', {
              on: parts.gpuOn,
              total: parts.gpuTotal,
              full: parts.fullLayers,
              perToken: count(parts.fullBytesPerToken),
              ctx: count(ctx),
            })
          : t('network.inspector.llm.vramFormulaMixed', {
              on: parts.gpuOn,
              total: parts.gpuTotal,
              full: parts.fullLayers,
              ctx: count(ctx),
            })
      : null;
  const gpuTotal = resources.data?.gpus?.[0]?.vramTotalBytes ?? 0;
  const percent = parts && gpuTotal > 0 ? (parts.total / gpuTotal) * 100 : 0;
  const over = Boolean(parts && gpuTotal > 0 && parts.total > gpuTotal);
  const tight = Boolean(parts && gpuTotal > 0 && !over && percent >= 85);
  const tone = meterTone(Math.min(100, percent), Boolean(parts && gpuTotal > 0));

  if (stats.isPending && !stats.data) {
    return (
      <Field label={t('network.inspector.llm.vram')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.vramLoading')}</p>
      </Field>
    );
  }
  if (!parts) return null;

  return (
    <Field label={t('network.inspector.llm.vram')}>
      {gpuTotal > 0 ? (
        <div
          className="h-2 overflow-hidden rounded-full bg-muted"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(Math.min(100, percent))}
          aria-label={t('network.inspector.llm.vram')}
        >
          <div
            className={cn(
              'h-full rounded-full',
              tone === 'off' && 'bg-muted-foreground/30',
              tone === 'normal' && 'bg-primary',
              tone === 'warn' && 'bg-warning',
              tone === 'hot' && 'bg-destructive',
            )}
            style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
          />
        </div>
      ) : null}
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className={cn('tabular-nums', over && 'font-medium text-destructive', tight && 'font-medium text-warning')}>
          {gpuTotal > 0
            ? t('network.inspector.llm.vramNeed', {
                need: formatBytes(parts.total, locale),
                total: formatBytes(gpuTotal, locale),
              })
            : t('network.inspector.llm.vramNeedOnly', { need: formatBytes(parts.total, locale) })}
        </span>
        {gpuTotal > 0 ? (
          <span className="tabular-nums text-muted-foreground">{formatPercent(percent, locale)}</span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('network.inspector.llm.vramParts', {
          weights: formatBytes(parts.weights, locale),
          kv: formatBytes(parts.kv, locale),
          overhead: formatBytes(parts.overhead, locale),
        })}
      </p>
      {formula ? <p className="text-xs text-muted-foreground">{formula}</p> : null}
      {over ? <p className="text-xs text-destructive">{t('network.inspector.llm.vramOver')}</p> : null}
      {tight ? <p className="text-xs text-warning">{t('network.inspector.llm.vramTight')}</p> : null}
      <p className="text-xs text-muted-foreground">{t('network.inspector.llm.vramHint')}</p>
    </Field>
  );
}

function CpuThreadField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const resources = useHostResourcesQuery({ live: false });
  const threads = resources.data?.cpuThreads ?? resources.data?.cpuCores ?? null;
  const cores = resources.data?.cpuCores ?? threads;
  const current = Number(node.data.numThread);

  useEffect(() => {
    if (readOnly || threads == null || cores == null) return;
    if (!Number.isFinite(current) || current < 1 || current > threads) {
      editorUpdateNodeData(node.id, { numThread: cores });
    }
  }, [cores, current, node.id, readOnly, threads]);

  if (resources.isPending && !resources.data) {
    return (
      <Field label={t('network.inspector.llm.numThread')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numThreadLoading')}</p>
      </Field>
    );
  }
  if (threads == null || cores == null) {
    return (
      <Field label={t('network.inspector.llm.numThread')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numThreadUnavailable')}</p>
      </Field>
    );
  }

  const value = Number.isFinite(current) ? Math.min(threads, Math.max(1, current)) : cores;

  return (
    <Field label={t('network.inspector.llm.numThread')}>
      <input
        type="range"
        min={1}
        max={threads}
        step={1}
        value={value}
        disabled={readOnly}
        className="w-full accent-primary"
        onChange={(event) => editorUpdateNodeData(node.id, { numThread: Number(event.target.value) })}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>1</span>
        <span className="font-medium text-foreground">{value}</span>
        <span>{threads}</span>
      </div>
      <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numThreadHint')}</p>
    </Field>
  );
}

function DisplayNameField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  return (
    <Field label={t('network.inspector.displayName')}>
      <Input
        value={String(node.data.displayName ?? '')}
        disabled={readOnly}
        onChange={(event) => editorUpdateNodeData(node.id, { displayName: event.target.value })}
      />
    </Field>
  );
}

function LlmFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const credentials = useEditorCredentialsQuery();
  const [advanced, setAdvanced] = useState(false);
  const [pinging, setPinging] = useState(false);
  const provider = String(node.data.provider ?? 'ollama');
  const model = String(node.data.model ?? '');
  const credentialId = String(node.data.credentialId ?? '') || undefined;
  const catalogProvider = isCloudCatalogProvider(provider);
  const matchingCredentials = (credentials.data?.items ?? []).filter((item) =>
    credentialMatchesProvider(item.kind, provider),
  );
  const kindCredentials = (credentials.data?.items ?? []).filter((item) => item.kind === provider);
  const ollamaModels = useRuntimeModelsQuery({ enabled: provider === 'ollama' });
  const catalogModels = useRuntimeModelsQuery({
    provider: provider as LlmProvider,
    credentialId,
    enabled: catalogProvider && Boolean(credentialId),
  });

  const modelOptions = useMemo(() => {
    const items =
      provider === 'ollama'
        ? (ollamaModels.data?.items ?? [])
        : catalogProvider
          ? (catalogModels.data?.items ?? [])
          : [];
    return items.map((item) => item.name).filter((name) => !isEmbeddingModelName(name));
  }, [catalogModels.data?.items, catalogProvider, ollamaModels.data?.items, provider]);
  const modelsLoading =
    provider === 'ollama'
      ? ollamaModels.isPending || ollamaModels.isFetching
      : catalogProvider
        ? catalogModels.isPending || catalogModels.isFetching
        : false;
  const modelLocked = catalogProvider && !credentialId;

  useEffect(() => {
    if (readOnly || modelLocked || modelsLoading) return;
    if (modelOptions.length === 0) {
      if (model) editorUpdateNodeData(node.id, { model: '' });
      return;
    }
    if (!modelOptions.includes(model)) {
      editorUpdateNodeData(node.id, { model: modelOptions[0] });
    }
  }, [model, modelLocked, modelOptions, modelsLoading, node.id, readOnly]);
  const catalogFailed =
    catalogProvider &&
    Boolean(credentialId) &&
    !catalogModels.isFetching &&
    !catalogModels.isPending &&
    (catalogModels.data?.items.length ?? 0) === 0;

  function setProvider(next: string) {
    const patch: Record<string, unknown> = { provider: next };
    if (next !== provider) {
      patch.model = '';
      patch.numCtx = undefined;
    }
    if (next !== 'ollama') {
      patch.numThread = undefined;
      patch.numGpu = undefined;
      patch.numGpuPercent = undefined;
      patch.numGpuLayers = undefined;
    }
    if (next === 'ollama') {
      patch.credentialId = undefined;
    } else if (isCloudCatalogProvider(next)) {
      const current = matchingCredentials.find((item) => item.id === credentialId);
      const nextKind = (credentials.data?.items ?? []).filter((item) => item.kind === next);
      if (!current || !credentialMatchesProvider(current.kind, next)) {
        patch.credentialId = nextKind.length === 1 ? nextKind[0].id : undefined;
      }
    }
    editorUpdateNodeData(node.id, patch);
  }

  async function ping() {
    setPinging(true);
    try {
      const result = await testLlmConnection({
        provider,
        model,
        baseUrl: String(node.data.baseUrl ?? '') || undefined,
        credentialId,
      });
      notify({
        titleKey: result.messageKey ?? (result.ok ? 'network.inspector.llm.pingOk' : 'network.inspector.llm.pingFail'),
        variant: result.ok ? 'success' : 'error',
      });
    } finally {
      setPinging(false);
    }
  }

  const credentialField =
    providerNeedsCredential(provider) ? (
      <Field label={t('network.inspector.llm.credential')}>
        <Select
          value={credentialId ?? 'none'}
          disabled={readOnly}
          onValueChange={(value) =>
            editorUpdateNodeData(node.id, {
              credentialId: value === 'none' ? undefined : value,
              ...(catalogProvider ? { model: '', numCtx: undefined } : {}),
            })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">{t('network.inspector.llm.credentialEmpty')}</SelectItem>
            {matchingCredentials.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {catalogProvider && kindCredentials.length === 0 ? (
          <p className="text-xs text-destructive">
            {t('network.inspector.llm.noCredentials')}{' '}
            <Link to="/settings#credentials" className="underline">
              {t('nav.settings')}
            </Link>
          </p>
        ) : catalogProvider ? (
          <p className="text-xs text-muted-foreground">{t('network.inspector.llm.credentialHint')}</p>
        ) : null}
      </Field>
    ) : null;

  return (
    <>
      <Field label={t('network.inspector.llm.provider')}>
        <Select value={provider} disabled={readOnly} onValueChange={setProvider}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LLM_PROVIDERS.map((id) => (
              <SelectItem key={id} value={id}>
                {t(`providers.${id}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {catalogProvider ? credentialField : null}
      <Field label={t('network.inspector.llm.model')}>
        <ModelCombobox
          value={modelLocked ? '' : model}
          options={modelOptions}
          disabled={readOnly || modelLocked}
          restrictToOptions
          placeholder={
            modelLocked ? t('network.inspector.llm.pickCredentialFirst') : t('network.inspector.llm.model')
          }
          noModelsLabel={t('network.inspector.llm.noModels')}
          onChange={(value) =>
            editorUpdateNodeData(node.id, {
              model: value,
              numCtx: undefined,
              numGpu: undefined,
              numGpuPercent: undefined,
              numGpuLayers: undefined,
            })
          }
        />
        {catalogFailed ? (
          <p className="text-xs text-destructive">{t('network.inspector.llm.modelsLoadError')}</p>
        ) : null}
      </Field>
      {model && !modelLocked ? <ContextWindowField node={node} readOnly={readOnly} /> : null}
      {provider === 'ollama' && model && !modelLocked ? (
        <>
          <CpuThreadField node={node} readOnly={readOnly} />
          <GpuOffloadField node={node} readOnly={readOnly} />
          <VramNeedField node={node} />
        </>
      ) : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={pinging || !model || modelLocked}
          loading={pinging}
          onClick={() => void ping()}
        >
          {t('network.inspector.llm.ping')}
        </Button>
        <button type="button" className="text-xs text-muted-foreground underline" onClick={() => setAdvanced((v) => !v)}>
          {t('network.inspector.llm.advanced')}
        </button>
      </div>
      {advanced ? (
        <>
          <Field label={t('network.inspector.llm.temperature')}>
            <Input
              type="number"
              step="0.1"
              value={node.data.temperature == null ? '' : String(node.data.temperature)}
              disabled={readOnly}
              onChange={(event) =>
                editorUpdateNodeData(node.id, {
                  temperature: event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
            />
          </Field>
          <Field label={t('network.inspector.llm.maxTokens')}>
            <Input
              type="number"
              value={node.data.maxTokens == null ? '' : String(node.data.maxTokens)}
              disabled={readOnly}
              onChange={(event) =>
                editorUpdateNodeData(node.id, {
                  maxTokens: event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
            />
          </Field>
        </>
      ) : null}
    </>
  );
}

function OrchestratorFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <p className="text-xs text-muted-foreground">{t('network.inspector.orchestrator.hint')}</p>
      <Field label={t('network.inspector.orchestrator.systemPrompt')}>
        <Textarea
          rows={6}
          value={String(node.data.systemPrompt ?? '')}
          disabled={readOnly}
          onChange={(event) => editorUpdateNodeData(node.id, { systemPrompt: event.target.value })}
        />
      </Field>
    </>
  );
}

function AgentFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const onChannel = useNetworkEditor((state) =>
    state.document.edges.some((edge) => edge.target === node.id && edge.targetHandle === 'channel'),
  );
  return (
    <>
      <p className="text-xs text-muted-foreground">
        {t(onChannel ? 'network.inspector.agent.channelHint' : 'network.inspector.agent.hint')}
      </p>
      <Field label={t('network.inspector.agent.systemPrompt')}>
        <Textarea
          rows={6}
          value={String(node.data.systemPrompt ?? '')}
          disabled={readOnly}
          onChange={(event) => editorUpdateNodeData(node.id, { systemPrompt: event.target.value })}
        />
      </Field>
    </>
  );
}

function ToolFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const credentials = useEditorCredentialsQuery();
  const kind = String(node.data.kind ?? 'datetime');
  const kinds = ['http', 'web_search', 'datetime', 'calculator', 'file_access'] as const;
  const items = credentials.data?.items ?? [];
  const matching = items.filter((item) => credentialMatchesToolKind(item.kind, kind));
  const credentialId = String(node.data.credentialId ?? '');
  const listedId = matching.some((item) => item.id === credentialId) ? credentialId : 'none';

  useEffect(() => {
    if (readOnly || kind !== 'web_search' || !credentials.data) return;
    if (!credentialId) return;
    const ok = (credentials.data.items ?? []).some(
      (item) => item.id === credentialId && item.kind === 'web_search',
    );
    if (!ok) editorUpdateNodeData(node.id, { credentialId: undefined });
  }, [kind, credentialId, credentials.data, readOnly, node.id]);

  return (
    <>
      <Field label={t('network.inspector.tool.kind')}>
        <Select
          value={kind}
          disabled={readOnly}
          onValueChange={(value) => {
            const patch: Record<string, unknown> = { kind: value };
            if (value === 'web_search') {
              const current = items.find((item) => item.id === node.data.credentialId);
              if (!current || current.kind !== 'web_search') patch.credentialId = undefined;
            }
            editorUpdateNodeData(node.id, patch);
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {kinds.map((item) => (
              <SelectItem key={item} value={item}>
                {t(`network.inspector.tool.kindName.${item}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {kind === 'http' ? (
        <>
          <Field label={t('network.inspector.tool.method')}>
            <Input
              value={String(node.data.method ?? 'GET')}
              disabled={readOnly}
              onChange={(event) => editorUpdateNodeData(node.id, { method: event.target.value })}
            />
          </Field>
          <Field label={t('network.inspector.tool.url')}>
            <Input
              value={String(node.data.url ?? '')}
              disabled={readOnly}
              onChange={(event) => editorUpdateNodeData(node.id, { url: event.target.value })}
            />
          </Field>
        </>
      ) : null}
      {kind === 'http' || kind === 'web_search' ? (
        <Field label={t('network.inspector.tool.credential')}>
          <Select
            value={listedId}
            disabled={readOnly}
            onValueChange={(value) =>
              editorUpdateNodeData(node.id, { credentialId: value === 'none' ? undefined : value })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t('network.inspector.llm.credentialEmpty')}</SelectItem>
              {matching.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      ) : null}
      {kind === 'file_access' ? <FileAccessFields node={node} readOnly={readOnly} /> : null}
    </>
  );
}

function McpFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const mcp = useMcpServersQuery();
  const recipes = useMcpRecipesQuery();
  const credentials = useEditorCredentialsQuery();
  const enabledServers = (mcp.data?.items ?? []).filter((item) => item.enabled);
  const serverId = String(node.data.mcpServerId ?? '');
  const selected = enabledServers.find((item) => item.id === serverId);
  const recipe = recipes.data?.items.find((item) => item.id === selected?.recipeId);
  const [pickingRoot, setPickingRoot] = useState(false);
  const selectedNames = Array.isArray(node.data.mcpToolNames)
    ? (node.data.mcpToolNames as string[])
    : undefined;
  const toolNames = selected?.toolNames ?? [];

  function selectServer(value: string) {
    const nextId = value === 'none' ? undefined : value;
    const next = enabledServers.find((item) => item.id === nextId);
    const nextRecipe = recipes.data?.items.find((item) => item.id === next?.recipeId);
    const patch: Record<string, unknown> = {
      mcpServerId: nextId,
      mcpToolNames: undefined,
      credentialId: undefined,
    };
    if (!nextRecipe?.rootOnNode) {
      patch.rootPath = undefined;
    }
    const currentName = String(node.data.displayName ?? '').trim();
    if (!currentName && next) {
      patch.displayName = next.recipeId
        ? t(`mcp.recipe.${next.recipeId}`, { defaultValue: next.name })
        : next.name;
    }
    editorUpdateNodeData(node.id, patch);
  }

  function toggleTool(name: string, on: boolean) {
    const current = selectedNames ?? toolNames;
    const next = on ? [...new Set([...current, name])] : current.filter((item) => item !== name);
    editorUpdateNodeData(node.id, {
      mcpToolNames: next.length === 0 || next.length === toolNames.length ? undefined : next,
    });
  }

  function applyMcpRoot(path: string) {
    const trimmed = path.trim();
    if (!trimmed) return;
    editorUpdateNodeData(node.id, { rootPath: trimmed });
    if (isForbiddenDataRoot(trimmed)) {
      notify({ titleKey: 'network.validation.mcpRoot', variant: 'error' });
    }
  }

  async function pickMcpRoot() {
    setPickingRoot(true);
    try {
      const path = await pickFolderPath();
      if (path) applyMcpRoot(path);
    } finally {
      setPickingRoot(false);
    }
  }

  return (
    <>
      <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.hint')}</p>
      <Field label={t('network.inspector.mcp.server')}>
        <Select value={serverId || 'none'} disabled={readOnly} onValueChange={selectServer}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">{t('network.inspector.mcp.empty')}</SelectItem>
            {enabledServers.map((server) => (
              <SelectItem key={server.id} value={server.id}>
                {server.recipeId
                  ? t(`mcp.recipe.${server.recipeId}`, { defaultValue: server.name })
                  : server.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {recipe ? (
        <p className="text-xs text-muted-foreground">
          {t(`settings.mcp.hint.${recipe.id}`, { defaultValue: t('network.inspector.mcp.hint') })}
        </p>
      ) : null}
      {recipe?.rootOnNode ? (
        <Field label={t('network.inspector.tool.rootPath')}>
          <div className="flex gap-2">
            <Input
              value={String(node.data.rootPath ?? '')}
              disabled={readOnly}
              spellCheck={false}
              autoComplete="off"
              title={String(node.data.rootPath ?? '')}
              className="min-w-0 font-mono text-xs"
              onChange={(event) => editorUpdateNodeData(node.id, { rootPath: event.target.value })}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={readOnly || pickingRoot}
              loading={pickingRoot}
              onClick={() => void pickMcpRoot()}
            >
              {t('network.inspector.tool.pickRoot')}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.rootHint')}</p>
        </Field>
      ) : null}
      {selected && (recipe?.credentialKinds?.length ?? 0) > 0
        ? (() => {
            const kinds = new Set(recipe?.credentialKinds ?? []);
            const matching = (credentials.data?.items ?? []).filter((item) => kinds.has(item.kind));
            const defaultId = selected.credentialIds?.[0];
            const defaultName = matching.find((item) => item.id === defaultId)?.name;
            if (matching.length === 0) return null;
            return (
              <Field label={t('network.inspector.mcp.credential')}>
                <Select
                  value={String(node.data.credentialId ?? 'default')}
                  disabled={readOnly}
                  onValueChange={(value) =>
                    editorUpdateNodeData(node.id, { credentialId: value === 'default' ? undefined : value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">
                      {t('network.inspector.mcp.credentialDefault', { name: defaultName || '—' })}
                    </SelectItem>
                    {matching.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.credentialHint')}</p>
              </Field>
            );
          })()
        : null}
      {enabledServers.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.noneEnabled')}</p>
      ) : null}
      {toolNames.length > 0 ? (
        <div className="space-y-2">
          <p className="text-sm font-medium">{t('network.inspector.mcp.tools')}</p>
          <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.toolsHint')}</p>
          {toolNames.map((name) => (
            <label key={name} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={selectedNames ? selectedNames.includes(name) : true}
                disabled={readOnly}
                onCheckedChange={(value) => toggleTool(name, value === true)}
              />
              <span className="font-mono text-xs">{name}</span>
            </label>
          ))}
        </div>
      ) : selected ? (
        <p className="text-xs text-muted-foreground">{t('network.inspector.mcp.probeHint')}</p>
      ) : null}
      <Button asChild size="sm" variant="link" className="h-auto px-0">
        <Link to="/settings#mcp">{t('network.inspector.mcp.settings')}</Link>
      </Button>
    </>
  );
}

function FileAccessFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);
  const allowWrite = node.data.allowWrite !== false;
  const allowDelete = node.data.allowDelete !== false;

  function applyPath(path: string) {
    const trimmed = path.trim();
    if (!trimmed) return;
    editorUpdateNodeData(node.id, { rootPath: trimmed });
    if (isForbiddenDataRoot(trimmed)) {
      notify({ titleKey: 'network.validation.fileAccessRoot', variant: 'error' });
    }
  }

  async function pick() {
    setPicking(true);
    try {
      const path = await pickFolderPath();
      if (path) applyPath(path);
    } finally {
      setPicking(false);
    }
  }

  return (
    <>
      <Field label={t('network.inspector.tool.rootPath')}>
        <div className="flex gap-2">
          <Input
            value={String(node.data.rootPath ?? '')}
            disabled={readOnly}
            spellCheck={false}
            autoComplete="off"
            title={String(node.data.rootPath ?? '')}
            className="min-w-0 font-mono text-xs"
            onChange={(event) => editorUpdateNodeData(node.id, { rootPath: event.target.value })}
          />
          <Button type="button" size="sm" variant="outline" disabled={readOnly || picking} loading={picking} onClick={() => void pick()}>
            {t('network.inspector.tool.pickRoot')}
          </Button>
        </div>
      </Field>
      <p className="text-xs text-muted-foreground">{t('network.inspector.tool.fileAccessHint')}</p>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={allowWrite}
          disabled={readOnly}
          onCheckedChange={(value) => editorUpdateNodeData(node.id, { allowWrite: value === true })}
        />
        {t('network.inspector.tool.allowWrite')}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={allowDelete}
          disabled={readOnly}
          onCheckedChange={(value) => editorUpdateNodeData(node.id, { allowDelete: value === true })}
        />
        {t('network.inspector.tool.allowDelete')}
      </label>
    </>
  );
}

function KnowledgeFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const document = useNetworkEditor((state) => state.document);
  const credentials = useEditorCredentialsQuery();
  const [reindexing, setReindexing] = useState(false);
  const [picking, setPicking] = useState(false);
  const embedProvider = (String(node.data.embeddingProvider ?? 'ollama') || 'ollama') as EmbeddingProvider;
  const embedModel = String(node.data.embeddingModel ?? '');
  const embedCredentialId = String(node.data.embeddingCredentialId ?? '') || undefined;
  const embedNeedsCred = embeddingNeedsCredential(embedProvider);
  const ollamaModels = useRuntimeModelsQuery({ enabled: embedProvider === 'ollama' });
  const embedCatalog = useRuntimeModelsQuery({
    provider: embedProvider as LlmProvider,
    credentialId: embedCredentialId,
    enabled: embedNeedsCred && Boolean(embedCredentialId),
  });
  const embedOptions = useMemo(() => {
    const items = embedProvider === 'ollama' ? (ollamaModels.data?.items ?? []) : (embedCatalog.data?.items ?? []);
    return items.map((item) => item.name).filter((name) => isEmbeddingModelName(name));
  }, [embedCatalog.data?.items, embedProvider, ollamaModels.data?.items]);
  const embedLoading =
    embedProvider === 'ollama'
      ? ollamaModels.isPending || ollamaModels.isFetching
      : embedCatalog.isPending || embedCatalog.isFetching;
  const embedLocked = embedNeedsCred && !embedCredentialId;
  const embedFailed =
    embedNeedsCred &&
    Boolean(embedCredentialId) &&
    !embedCatalog.isFetching &&
    !embedCatalog.isPending &&
    embedOptions.length === 0;
  const embedKindCredentials = (credentials.data?.items ?? []).filter((item) => item.kind === embedProvider);
  const embedCredentials = (credentials.data?.items ?? []).filter((item) =>
    credentialMatchesProvider(item.kind, embedProvider),
  );

  useEffect(() => {
    if (readOnly || embedLocked || embedLoading) return;
    if (embedOptions.length === 0) {
      if (embedModel) editorUpdateNodeData(node.id, { embeddingModel: '' });
      return;
    }
    if (!embedOptions.includes(embedModel)) {
      editorUpdateNodeData(node.id, { embeddingModel: embedOptions[0] });
    }
  }, [embedLoading, embedLocked, embedModel, embedOptions, node.id, readOnly]);

  function applyPath(path: string) {
    const trimmed = path.trim();
    if (!trimmed) return;
    editorUpdateNodeData(node.id, { sourcePath: trimmed });
    if (isForbiddenDataRoot(trimmed)) {
      notify({ titleKey: 'network.validation.knowledgeRoot', variant: 'error' });
    }
  }

  async function pick() {
    setPicking(true);
    try {
      const path = await pickFolderPath();
      if (path) applyPath(path);
    } finally {
      setPicking(false);
    }
  }

  async function reindex() {
    if (!document.id) return;
    setReindexing(true);
    try {
      const result = await reindexNetworkKnowledge(document.id, node.id);
      notify({
        titleKey: result.state === 'ready' ? 'network.inspector.knowledge.reindexOk' : 'network.inspector.knowledge.reindexFail',
        variant: result.state === 'ready' ? 'success' : 'error',
      });
    } finally {
      setReindexing(false);
    }
  }

  return (
    <>
      <Field label={t('network.inspector.knowledge.embedProvider')}>
        <Select
          value={embedProvider || 'ollama'}
          disabled={readOnly}
          onValueChange={(value) => {
            const next = value as EmbeddingProvider;
            const patch: Record<string, unknown> = {
              embeddingProvider: next,
              embeddingModel: '',
            };
            if (!embeddingNeedsCredential(next)) {
              patch.embeddingCredentialId = undefined;
            } else {
              const nextKind = (credentials.data?.items ?? []).filter((item) => item.kind === next);
              const current = (credentials.data?.items ?? []).find((item) => item.id === embedCredentialId);
              if (!current || !credentialMatchesProvider(current.kind, next)) {
                patch.embeddingCredentialId = nextKind.length === 1 ? nextKind[0].id : undefined;
              }
            }
            editorUpdateNodeData(node.id, patch);
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {EMBEDDING_PROVIDERS.map((id) => (
              <SelectItem key={id} value={id}>
                {t(`providers.${id}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {embedNeedsCred ? (
        <Field label={t('network.inspector.llm.credential')}>
          <Select
            value={embedCredentialId ?? 'none'}
            disabled={readOnly}
            onValueChange={(value) =>
              editorUpdateNodeData(node.id, {
                embeddingCredentialId: value === 'none' ? undefined : value,
                embeddingModel: '',
              })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t('network.inspector.llm.credentialEmpty')}</SelectItem>
              {embedCredentials.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {embedKindCredentials.length === 0 ? (
            <p className="text-xs text-destructive">
              {t('network.inspector.llm.noCredentials')}{' '}
              <Link to="/settings#credentials" className="underline">
                {t('nav.settings')}
              </Link>
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">{t('network.inspector.llm.credentialHint')}</p>
          )}
        </Field>
      ) : null}
      <Field label={t('network.inspector.knowledge.embedModel')}>
        <ModelCombobox
          value={embedLocked ? '' : embedModel}
          options={embedOptions}
          disabled={readOnly || embedLocked}
          restrictToOptions
          placeholder={
            embedLocked ? t('network.inspector.llm.pickCredentialFirst') : t('network.inspector.knowledge.embedModel')
          }
          noModelsLabel={t('network.inspector.llm.noModels')}
          onChange={(value) => editorUpdateNodeData(node.id, { embeddingModel: value })}
        />
        {embedFailed ? (
          <p className="text-xs text-destructive">{t('network.inspector.llm.modelsLoadError')}</p>
        ) : null}
      </Field>
      <Field label={t('network.inspector.knowledge.path')}>
        <div className="flex gap-2">
          <Input
            value={String(node.data.sourcePath ?? '')}
            disabled={readOnly}
            spellCheck={false}
            autoComplete="off"
            title={String(node.data.sourcePath ?? '')}
            className="min-w-0 font-mono text-xs"
            onChange={(event) => editorUpdateNodeData(node.id, { sourcePath: event.target.value })}
          />
          <Button type="button" size="sm" variant="outline" disabled={readOnly || picking} loading={picking} onClick={() => void pick()}>
            {t('network.inspector.knowledge.pick')}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">{t('network.inspector.knowledge.filesHint')}</p>
      </Field>
      <Field label={t('network.inspector.knowledge.topK')}>
        <Input
          type="number"
          value={node.data.topK == null ? 5 : Number(node.data.topK)}
          disabled={readOnly}
          onChange={(event) => editorUpdateNodeData(node.id, { topK: Number(event.target.value) })}
        />
      </Field>
      <Field label={t('network.inspector.knowledge.score')}>
        <Input
          type="number"
          step="0.05"
          value={node.data.scoreThreshold == null ? '' : String(node.data.scoreThreshold)}
          disabled={readOnly}
          onChange={(event) =>
            editorUpdateNodeData(node.id, {
              scoreThreshold: event.target.value === '' ? undefined : Number(event.target.value),
            })
          }
        />
      </Field>
      <p className="text-xs text-muted-foreground">{t('network.inspector.knowledge.reindexHint')}</p>
      <Button type="button" size="sm" variant="outline" disabled={!document.id || reindexing} loading={reindexing} onClick={() => void reindex()}>
        {t('network.inspector.knowledge.reindex')}
      </Button>
    </>
  );
}

function RouterFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const branches = Array.isArray(node.data.branches) ? (node.data.branches as Array<{ id: string; name: string; condition: string }>) : [];

  function update(next: typeof branches) {
    editorUpdateNodeData(node.id, { branches: next });
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{t('network.inspector.router.branches')}</p>
      {branches.map((branch, index) => (
        <div key={branch.id} className="grid gap-1 rounded-md border p-2">
          <Input
            value={branch.name}
            disabled={readOnly}
            placeholder={t('network.inspector.router.branchName')}
            onChange={(event) =>
              update(branches.map((item, i) => (i === index ? { ...item, name: event.target.value } : item)))
            }
          />
          <Input
            value={branch.condition}
            disabled={readOnly}
            placeholder={t('network.inspector.router.condition')}
            onChange={(event) =>
              update(branches.map((item, i) => (i === index ? { ...item, condition: event.target.value } : item)))
            }
          />
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={readOnly || branches.length < 1}
            onClick={() => update(branches.filter((item) => item.id !== branch.id))}
          >
            {t('network.context.delete')}
          </Button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={readOnly}
        onClick={() => update([...branches, { id: newId('br'), name: '', condition: '' }])}
      >
        {t('network.inspector.router.add')}
      </Button>
    </div>
  );
}

function ChatInputFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <p className="text-xs text-muted-foreground">{t('network.inspector.chat.hint')}</p>
      <Field label={t('network.inspector.chat.placeholder')}>
        <Input
          value={String(node.data.placeholder ?? '')}
          disabled={readOnly}
          onChange={(event) => editorUpdateNodeData(node.id, { placeholder: event.target.value })}
        />
      </Field>
      <Field label={t('network.inspector.chat.startMessage')}>
        <Textarea
          value={String(node.data.startMessage ?? '')}
          disabled={readOnly}
          onChange={(event) => editorUpdateNodeData(node.id, { startMessage: event.target.value })}
        />
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={Boolean(node.data.requireInput)}
          disabled={readOnly}
          onCheckedChange={(value) => editorUpdateNodeData(node.id, { requireInput: value === true })}
        />
        {t('network.inspector.chat.requireInput')}
      </label>
    </>
  );
}
