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
} from '@/modules/network/api';
import { uniqueTags } from '@/modules/networks/model/filter';
import { useHostResourcesQuery, useMcpRecipesQuery, useModelStatsQuery, useRuntimeModelsQuery } from '@/modules/settings/api';
import {
  ROUTER_MATCHES,
  newId,
  routerMatchOf,
  routerPatternOf,
  type GraphNode,
  type RouterMatch,
  type ValidationIssue,
} from '@/modules/network/model/document';
import { PromptPickDialog } from '@/modules/network/inspector/PromptPickDialog';
import { editorDeleteSelection, editorUpdateNodeData, useNetworkEditor } from '@/modules/network/store';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import { formatBytes, formatPercent, meterTone } from '@/modules/monitoring/model/format';
import {
  estimateVramParts,
  fitMoe,
  hasWindowedKv,
  inferenceGpus,
  kvCacheScale,
  moeAutoOffload,
  moeLeavesPlacementToRuntime,
  resolveGpuLayers,
  scaleKvLayers,
} from '@/modules/network/inspector/vram';
import {
  EMBEDDING_PROVIDERS,
  LLM_PROVIDERS,
  credentialMatchesProvider,
  credentialMatchesSearchProvider,
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
  const expertCount = stats.data?.expertCount ?? 0;
  const isMoe = expertCount > 1;
  const placement = typeof node.data.gpuPlacement === 'string' ? node.data.gpuPlacement : null;
  const auto = moeLeavesPlacementToRuntime({
    expertCount,
    gpuLayers: layers,
    numGpuLayers: Number(node.data.numGpuLayers),
    numGpuPercent: Number(node.data.numGpuPercent),
    gpuPlacement: placement,
  });
  const value =
    layers == null
      ? 1
      : resolveGpuLayers(Number(node.data.numGpuLayers), Number(node.data.numGpuPercent), layers);

  useEffect(() => {
    if (readOnly || layers == null) return;
    if (isMoe && auto) {
      if (
        node.data.gpuPlacement === 'auto' &&
        node.data.numGpuPercent === undefined &&
        node.data.numGpu === undefined
      ) {
        return;
      }
      editorUpdateNodeData(node.id, {
        gpuPlacement: 'auto',
        numGpuPercent: undefined,
        numGpu: undefined,
      });
      return;
    }
    if (isMoe) {
      if (
        node.data.gpuPlacement === 'layers' &&
        node.data.numGpuLayers === value &&
        node.data.numGpuPercent === undefined &&
        node.data.numGpu === undefined &&
        node.data.numCpuMoe === undefined
      ) {
        return;
      }
      editorUpdateNodeData(node.id, {
        gpuPlacement: 'layers',
        numGpuLayers: value,
        numGpuPercent: undefined,
        numGpu: undefined,
        numCpuMoe: undefined,
      });
      return;
    }
    if (
      node.data.numGpuLayers === value &&
      node.data.numGpuPercent === undefined &&
      node.data.numGpu === undefined
    ) {
      return;
    }
    editorUpdateNodeData(node.id, { numGpuLayers: value, numGpuPercent: undefined, numGpu: undefined });
  }, [
    auto,
    isMoe,
    layers,
    node.data.gpuPlacement,
    node.data.numGpu,
    node.data.numGpuLayers,
    node.data.numGpuPercent,
    node.id,
    readOnly,
    value,
  ]);

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

  const used = stats.data?.expertUsedCount;
  const knownSplit = (stats.data?.routedExpertBytes ?? 0) > 0;
  return (
    <Field label={t('network.inspector.llm.numGpu')}>
      {isMoe ? (
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={auto}
            disabled={readOnly}
            onCheckedChange={(checked) => {
              if (checked === true) {
                editorUpdateNodeData(node.id, {
                  gpuPlacement: 'auto',
                  numGpuPercent: undefined,
                  numGpu: undefined,
                });
                return;
              }
              editorUpdateNodeData(node.id, {
                gpuPlacement: 'layers',
                numGpuLayers: layers,
                numGpuPercent: undefined,
                numGpu: undefined,
                numCpuMoe: undefined,
              });
            }}
          />
          {t('network.inspector.llm.moeAuto')}
        </label>
      ) : null}
      {isMoe && auto ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={readOnly}
          onClick={() =>
            editorUpdateNodeData(node.id, {
              gpuPlacement: 'layers',
              numGpuLayers: layers,
              numGpuPercent: undefined,
              numGpu: undefined,
              numCpuMoe: undefined,
            })
          }
        >
          {t('network.inspector.llm.moeForce')}
        </Button>
      ) : null}
      {isMoe && auto ? (
        <p className="text-xs text-muted-foreground">
          {used
            ? t('network.inspector.llm.moeAutoHint', { count: expertCount, used })
            : t('network.inspector.llm.moeAutoHintNoUsed', { count: expertCount })}
        </p>
      ) : null}
      {isMoe && auto && !knownSplit ? (
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.moeUnknown')}</p>
      ) : null}
      {auto ? null : (
        <>
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
                gpuPlacement: isMoe ? 'layers' : undefined,
                numGpuLayers: Number(event.target.value),
                numGpuPercent: undefined,
                numGpu: undefined,
                numCpuMoe: undefined,
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
          <p className="text-xs text-muted-foreground">
            {isMoe ? t('network.inspector.llm.moeLayerWarn') : t('network.inspector.llm.numGpuHint')}
          </p>
        </>
      )}
    </Field>
  );
}

function VramNeedField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
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
  const placement = typeof node.data.gpuPlacement === 'string' ? node.data.gpuPlacement : null;
  const auto = moeLeavesPlacementToRuntime({
    expertCount: stats.data?.expertCount,
    gpuLayers: stats.data?.gpuLayers,
    numGpuLayers: Number(node.data.numGpuLayers),
    numGpuPercent: Number(node.data.numGpuPercent),
    gpuPlacement: placement,
  });
  const kvScale = kvCacheScale(node.data.kvCacheType);
  const kvLayers = scaleKvLayers(stats.data?.kvLayers, kvScale);
  const kvPerToken =
    stats.data?.kvBytesPerToken && kvScale !== 1
      ? Math.round(stats.data.kvBytesPerToken * kvScale)
      : stats.data?.kvBytesPerToken;
  const kvSwaPerToken =
    stats.data?.kvSwaBytesPerToken && kvScale !== 1
      ? Math.round(stats.data.kvSwaBytesPerToken * kvScale)
      : stats.data?.kvSwaBytesPerToken;
  const parts = estimateVramParts({
    weightBytes: stats.data?.weightBytes,
    kvBytesPerToken: kvPerToken,
    kvSwaBytesPerToken: kvSwaPerToken,
    swaWindow: stats.data?.swaWindow,
    overheadBytes: stats.data?.overheadBytes,
    gpuLayers: stats.data?.gpuLayers,
    kvLayers,
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
  const pool = inferenceGpus(resources.data?.gpus ?? []);
  const gpuTotal = pool.reduce((sum, gpu) => sum + Math.max(0, gpu.vramTotalBytes), 0);
  const gpuNames = pool
    .map((gpu) => gpu.name?.trim())
    .filter((name): name is string => Boolean(name))
    .join(' · ');
  const fit =
    (stats.data?.routedExpertBytes ?? 0) > 0
      ? fitMoe({
          nonExpertBytes: stats.data?.nonExpertBytes,
          routedExpertBytes: stats.data?.routedExpertBytes,
          overheadBytes: stats.data?.overheadBytes,
          gpuLayers: stats.data?.gpuLayers,
          kvLayers,
          kvBytesPerToken: kvPerToken,
          leadingDenseBlocks: stats.data?.leadingDenseBlocks,
          projectorBytes: stats.data?.projectorBytes,
          numCtx: ctx,
          poolBytes: gpuTotal,
        })
      : null;
  useEffect(() => {
    if (readOnly || !auto || !fit) return;
    const next = moeAutoOffload(fit, stats.data?.leadingDenseBlocks);
    if (
      node.data.gpuPlacement === 'auto' &&
      node.data.numGpuLayers === next.numGpuLayers &&
      node.data.numCpuMoe === next.numCpuMoe &&
      node.data.numGpuPercent === undefined &&
      node.data.numGpu === undefined
    ) {
      return;
    }
    editorUpdateNodeData(node.id, {
      gpuPlacement: 'auto',
      numGpuLayers: next.numGpuLayers,
      numCpuMoe: next.numCpuMoe,
      numGpuPercent: undefined,
      numGpu: undefined,
    });
  }, [
    auto,
    fit,
    node.data.gpuPlacement,
    node.data.numCpuMoe,
    node.data.numGpu,
    node.data.numGpuLayers,
    node.data.numGpuPercent,
    node.id,
    readOnly,
    stats.data?.leadingDenseBlocks,
  ]);
  const placed = auto ? fit : null;
  const need = placed ? placed.gpuBytes : (parts?.total ?? 0);
  const weightBytes = placed ? placed.nonExpertOnGpu : (parts?.weights ?? 0);
  const kvBytes = placed ? placed.kvBytes : (parts?.kv ?? 0);
  const overheadBytes = placed ? placed.overheadBytes : (parts?.overhead ?? 0);
  const percent = (placed || parts) && gpuTotal > 0 ? (need / gpuTotal) * 100 : 0;
  const over = Boolean(!placed && parts && gpuTotal > 0 && parts.total > gpuTotal);
  const tight = Boolean((placed || parts) && gpuTotal > 0 && !over && percent >= 85);
  const tone = meterTone(Math.min(100, percent), Boolean((placed || parts) && gpuTotal > 0));
  const ramTotal = resources.data?.ramTotalBytes ?? 0;
  const ramFree = Math.max(0, ramTotal - (resources.data?.ramUsedBytes ?? 0));
  const ramTight = Boolean(placed && placed.ramBytes > 0 && ramTotal > 0 && placed.ramBytes > ramFree);
  const windowed = hasWindowedKv({
    kvSwaBytesPerToken: stats.data?.kvSwaBytesPerToken,
    swaWindow: stats.data?.swaWindow,
    kvLayers: stats.data?.kvLayers,
  });
  const layerCount = stats.data?.gpuLayers ?? 0;

  if (stats.isPending && !stats.data) {
    return (
      <Field label={t('network.inspector.llm.vram')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.vramLoading')}</p>
      </Field>
    );
  }
  if (!parts && !placed) return null;

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
                need: formatBytes(need, locale),
                total: formatBytes(gpuTotal, locale),
              })
            : t('network.inspector.llm.vramNeedOnly', { need: formatBytes(need, locale) })}
        </span>
        {gpuTotal > 0 ? (
          <span className="tabular-nums text-muted-foreground">{formatPercent(percent, locale)}</span>
        ) : null}
      </div>
      {gpuNames ? <p className="text-xs text-muted-foreground">{t('network.inspector.llm.vramPool', { names: gpuNames })}</p> : null}
      <p className="text-xs text-muted-foreground">
        {t('network.inspector.llm.vramParts', {
          weights: formatBytes(weightBytes, locale),
          kv: formatBytes(kvBytes, locale),
          overhead: formatBytes(overheadBytes, locale),
        })}
      </p>
      {placed ? (
        <p className="text-xs text-muted-foreground">
          {t('network.inspector.llm.moeExpertsGpu', { experts: formatBytes(placed.expertOnGpuBytes, locale) })}
        </p>
      ) : null}
      {!auto && fit ? (
        <p className="text-xs text-muted-foreground">
          {t('network.inspector.llm.moeAutoFit', {
            gpu: formatBytes(fit.gpuBytes, locale),
            ram: formatBytes(fit.ramBytes, locale),
          })}
        </p>
      ) : null}
      {placed && placed.ramBytes > 0 ? (
        <p className={cn('text-xs', ramTight ? 'text-warning' : 'text-muted-foreground')}>
          {t('network.inspector.llm.moeRam', { ram: formatBytes(placed.ramBytes, locale) })}
        </p>
      ) : null}
      {ramTight ? <p className="text-xs text-warning">{t('network.inspector.llm.moeRamTight')}</p> : null}
      {placed && layerCount > 0 && placed.attentionLayersOnGpu < layerCount ? (
        <p className="text-xs text-muted-foreground">
          {t('network.inspector.llm.moeAttention', { on: placed.attentionLayersOnGpu, total: layerCount })}
        </p>
      ) : null}
      {placed && windowed ? <p className="text-xs text-muted-foreground">{t('network.inspector.llm.moeSwa')}</p> : null}
      {placed && placed.fullLayers > 0 && placed.bytesPerToken > 0 ? (
        <p className="text-xs text-muted-foreground">
          {t('network.inspector.llm.moeKvFormula', {
            full: placed.fullLayers,
            perToken: count(placed.bytesPerToken),
            ctx: count(ctx),
          })}
        </p>
      ) : null}
      {!placed && formula ? <p className="text-xs text-muted-foreground">{formula}</p> : null}
      {over ? <p className="text-xs text-destructive">{t('network.inspector.llm.vramOver')}</p> : null}
      {tight ? <p className="text-xs text-warning">{t('network.inspector.llm.vramTight')}</p> : null}
      <p className="text-xs text-muted-foreground">
        {placed ? t('network.inspector.llm.moeEstimate') : t('network.inspector.llm.vramHint')}
      </p>
    </Field>
  );
}

function standardThreads(threads: number): number {
  return Math.max(1, Math.round(threads / 2));
}

function KvCacheField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const value = node.data.kvCacheType === 'q8_0' ? 'q8_0' : 'f16';
  return (
    <Field label={t('network.inspector.llm.kvCache')}>
      <Select
        value={value}
        disabled={readOnly}
        onValueChange={(next) =>
          editorUpdateNodeData(node.id, { kvCacheType: next === 'q8_0' ? 'q8_0' : 'f16' })
        }
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="f16">{t('network.inspector.llm.kvCacheF16')}</SelectItem>
          <SelectItem value="q8_0">{t('network.inspector.llm.kvCacheQ8')}</SelectItem>
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">{t('network.inspector.llm.kvCacheHint')}</p>
    </Field>
  );
}

function CpuThreadField({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const resources = useHostResourcesQuery({ live: false });
  const threads = resources.data?.cpuThreads ?? resources.data?.cpuCores ?? null;
  const current = Number(node.data.numThread);
  const touched = node.data.numThreadTouched === true;
  const standard = threads == null ? 1 : standardThreads(threads);

  useEffect(() => {
    if (readOnly || threads == null) return;
    const missing = !Number.isFinite(current) || current < 1 || current > threads;
    // Full load was the old automatic default. A value the user picked stays.
    const oldFullDefault = !touched && current === threads;
    if (missing || oldFullDefault) {
      editorUpdateNodeData(node.id, { numThread: standard, numThreadTouched: true });
    }
  }, [current, node.id, readOnly, standard, threads, touched]);

  if (resources.isPending && !resources.data) {
    return (
      <Field label={t('network.inspector.llm.numThread')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numThreadLoading')}</p>
      </Field>
    );
  }
  if (threads == null) {
    return (
      <Field label={t('network.inspector.llm.numThread')}>
        <p className="text-xs text-muted-foreground">{t('network.inspector.llm.numThreadUnavailable')}</p>
      </Field>
    );
  }

  const value = Number.isFinite(current) ? Math.min(threads, Math.max(1, current)) : standard;

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
        onChange={(event) =>
          editorUpdateNodeData(node.id, { numThread: Number(event.target.value), numThreadTouched: true })
        }
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

  const ollamaChat = useMemo(
    () => (ollamaModels.data?.items ?? []).filter((item) => !isEmbeddingModelName(item.name)),
    [ollamaModels.data?.items],
  );
  const denseNames = useMemo(() => ollamaChat.filter((item) => !item.moe).map((item) => item.name), [ollamaChat]);
  const moeNames = useMemo(() => ollamaChat.filter((item) => item.moe).map((item) => item.name), [ollamaChat]);
  const ollamaListReady = provider === 'ollama' && ollamaModels.isSuccess && !ollamaModels.isFetching;
  const onlyMoe = ollamaListReady && moeNames.length > 0 && denseNames.length === 0;
  const onlyDense = ollamaListReady && denseNames.length > 0 && moeNames.length === 0;
  const storedKind = node.data.modelKind === 'moe' ? 'moe' : node.data.modelKind === 'dense' ? 'dense' : null;
  const modelKind: 'dense' | 'moe' = onlyMoe
    ? 'moe'
    : onlyDense
      ? 'dense'
      : (storedKind ?? (moeNames.includes(model) ? 'moe' : 'dense'));
  const modelOptions = useMemo(() => {
    if (provider === 'ollama') return modelKind === 'moe' ? moeNames : denseNames;
    if (!catalogProvider) return [];
    return (catalogModels.data?.items ?? []).map((item) => item.name).filter((name) => !isEmbeddingModelName(name));
  }, [catalogModels.data?.items, catalogProvider, denseNames, moeNames, modelKind, provider]);
  const modelsLoading =
    provider === 'ollama'
      ? ollamaModels.isPending || ollamaModels.isFetching
      : catalogProvider
        ? catalogModels.isPending || catalogModels.isFetching
        : false;
  const modelLocked = catalogProvider && !credentialId;

  useEffect(() => {
    if (readOnly || modelLocked || modelsLoading) return;
    const patch: Record<string, unknown> = {};
    if (provider === 'ollama' && node.data.modelKind !== modelKind) patch.modelKind = modelKind;
    if (modelOptions.length === 0) {
      if (model) patch.model = '';
    } else if (!modelOptions.includes(model)) {
      patch.model = modelOptions[0];
      patch.numCtx = undefined;
      patch.numGpu = undefined;
      patch.numGpuPercent = undefined;
      patch.numGpuLayers = undefined;
      patch.numCpuMoe = undefined;
      patch.gpuPlacement = undefined;
    }
    if (Object.keys(patch).length > 0) editorUpdateNodeData(node.id, patch);
  }, [model, modelKind, modelLocked, modelOptions, modelsLoading, node.data.modelKind, node.id, provider, readOnly]);
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
      patch.numCpuMoe = undefined;
      patch.gpuPlacement = undefined;
      patch.kvCacheType = undefined;
      patch.modelKind = undefined;
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
      {provider === 'ollama' ? (
        <Field label={t('network.inspector.llm.modelKind')}>
          <Select
            value={modelKind}
            disabled={readOnly || modelsLoading}
            onValueChange={(value) => {
              const next = value === 'moe' ? 'moe' : 'dense';
              const options = next === 'moe' ? moeNames : denseNames;
              editorUpdateNodeData(node.id, {
                modelKind: next,
                model: options.includes(model) ? model : (options[0] ?? ''),
                numCtx: undefined,
                numGpu: undefined,
                numGpuPercent: undefined,
                numGpuLayers: undefined,
                numCpuMoe: undefined,
                gpuPlacement: undefined,
              });
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dense" disabled={ollamaListReady && denseNames.length === 0 && moeNames.length > 0}>
                {t('network.inspector.llm.kindDense')}
              </SelectItem>
              <SelectItem value="moe" disabled={ollamaListReady && moeNames.length === 0 && denseNames.length > 0}>
                {t('network.inspector.llm.kindMoe')}
              </SelectItem>
            </SelectContent>
          </Select>
        </Field>
      ) : null}
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
              numCpuMoe: undefined,
              gpuPlacement: undefined,
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
          <KvCacheField node={node} readOnly={readOnly} />
          <CpuThreadField node={node} readOnly={readOnly} />
          <GpuOffloadField node={node} readOnly={readOnly} />
          <VramNeedField node={node} readOnly={readOnly} />
        </>
      ) : null}
      <div className="pt-1">
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
      <SystemPromptField key={node.id} node={node} readOnly={readOnly} label={t('network.inspector.orchestrator.systemPrompt')} />
      <Field label={t('network.inspector.orchestrator.agentMissLimit')}>
        <Input
          type="number"
          min={1}
          max={8}
          value={node.data.agentMissLimit == null ? 3 : String(node.data.agentMissLimit)}
          disabled={readOnly}
          onChange={(event) => {
            const raw = event.target.value;
            if (raw === '') {
              editorUpdateNodeData(node.id, { agentMissLimit: undefined });
              return;
            }
            const next = Math.round(Number(raw));
            if (!Number.isFinite(next)) return;
            editorUpdateNodeData(node.id, { agentMissLimit: Math.max(1, Math.min(8, next)) });
          }}
        />
      </Field>
      <p className="text-xs text-muted-foreground">{t('network.inspector.orchestrator.agentMissLimitHint')}</p>
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
      <SystemPromptField key={node.id} node={node} readOnly={readOnly} label={t('network.inspector.agent.systemPrompt')} />
    </>
  );
}

function SystemPromptField({ node, readOnly, label }: { node: GraphNode; readOnly: boolean; label: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="grid min-w-0 gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label>{label}</Label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          disabled={readOnly}
          onClick={() => setOpen(true)}
        >
          {t('network.inspector.prompt.pick')}
        </Button>
      </div>
      <Textarea
        rows={6}
        value={String(node.data.systemPrompt ?? '')}
        disabled={readOnly}
        onChange={(event) => editorUpdateNodeData(node.id, { systemPrompt: event.target.value })}
      />
      <PromptPickDialog
        open={open}
        onOpenChange={setOpen}
        onPick={(prompt) => {
          const patch: Record<string, string> = { systemPrompt: prompt.body };
          const currentName = String(node.data.displayName ?? '').trim();
          const promptName = prompt.name.trim();
          if (!currentName && promptName) patch.displayName = promptName;
          editorUpdateNodeData(node.id, patch);
        }}
      />
    </div>
  );
}

function ToolFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const credentials = useEditorCredentialsQuery();
  const kind = String(node.data.kind ?? 'datetime');
  const kinds = ['http', 'web_search', 'datetime', 'calculator', 'file_access', 'terminal', 'zip'] as const;
  const searchProvider = String(node.data.searchProvider ?? 'brave');
  const items = credentials.data?.items ?? [];
  const matching = items.filter((item) =>
    kind === 'web_search' ? credentialMatchesSearchProvider(item.kind, searchProvider) : true,
  );
  const credentialId = String(node.data.credentialId ?? '');
  const listedId = matching.some((item) => item.id === credentialId) ? credentialId : 'none';

  useEffect(() => {
    if (readOnly || kind !== 'web_search' || !credentials.data) return;
    if (!credentialId) return;
    const ok = (credentials.data.items ?? []).some(
      (item) => item.id === credentialId && credentialMatchesSearchProvider(item.kind, searchProvider),
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
              const provider = String(node.data.searchProvider ?? 'brave');
              if (!current || !credentialMatchesSearchProvider(current.kind, provider)) {
                patch.credentialId = undefined;
              }
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
      {kind === 'web_search' ? <WebSearchFields node={node} readOnly={readOnly} items={items} /> : null}
      {kind === 'http' ? (
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
      {kind === 'terminal' ? <TerminalFields node={node} readOnly={readOnly} /> : null}
      {kind === 'zip' ? <ZipFields node={node} readOnly={readOnly} /> : null}
      {kind === 'datetime' ? (
        <p className="text-xs text-muted-foreground">{t('network.inspector.tool.dateHint')}</p>
      ) : null}
      {kind === 'calculator' ? (
        <p className="text-xs text-muted-foreground">{t('network.inspector.tool.calculatorHint')}</p>
      ) : null}
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

const FILE_ACTIONS = [
  'list',
  'stat',
  'read',
  'read_many',
  'write',
  'mkdir',
  'delete',
  'edit',
  'move',
  'search',
  'tree',
] as const;
const FILE_WRITE_ACTIONS = new Set(['write', 'mkdir', 'edit', 'move']);
const SEARCH_PROVIDERS = ['brave', 'tavily', 'exa', 'searxng'] as const;

function WebSearchFields({
  node,
  readOnly,
  items,
}: {
  node: GraphNode;
  readOnly: boolean;
  items: { id: string; name: string; kind: string }[];
}) {
  const { t } = useTranslation();
  const provider = String(node.data.searchProvider ?? 'brave');
  const matching = items.filter((item) => item.kind === provider);
  const credentialId = String(node.data.credentialId ?? '');
  const listedId = matching.some((item) => item.id === credentialId) ? credentialId : 'none';
  const maxResults = Number(node.data.maxResults ?? 5);

  return (
    <>
      <Field label={t('network.inspector.tool.searchProvider')}>
        <Select
          value={provider}
          disabled={readOnly}
          onValueChange={(value) => {
            const current = items.find((item) => item.id === node.data.credentialId);
            editorUpdateNodeData(node.id, {
              searchProvider: value,
              credentialId: current && current.kind === value ? current.id : undefined,
              searchBaseUrl: value === 'searxng' ? node.data.searchBaseUrl : undefined,
            });
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SEARCH_PROVIDERS.map((item) => (
              <SelectItem key={item} value={item}>
                {t(`network.inspector.tool.searchProviderName.${item}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {provider === 'searxng' ? (
        <Field label={t('network.inspector.tool.searchBaseUrl')}>
          <Input
            value={String(node.data.searchBaseUrl ?? '')}
            disabled={readOnly}
            spellCheck={false}
            autoComplete="off"
            placeholder="https://"
            onChange={(event) => editorUpdateNodeData(node.id, { searchBaseUrl: event.target.value })}
          />
        </Field>
      ) : null}
      <Field label={t('network.inspector.tool.maxResults')}>
        <Input
          type="number"
          min={1}
          max={10}
          value={Number.isFinite(maxResults) ? maxResults : 5}
          disabled={readOnly}
          onChange={(event) => {
            const next = Number(event.target.value);
            editorUpdateNodeData(node.id, {
              maxResults: Number.isFinite(next) ? Math.max(1, Math.min(10, next)) : 5,
            });
          }}
        />
      </Field>
      <p className="text-xs text-muted-foreground">{t(`network.inspector.tool.searchHint.${provider}`)}</p>
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
    </>
  );
}

function FileAccessFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);
  const stored = Array.isArray(node.data.fileActions) ? node.data.fileActions.map(String) : null;
  const selected = new Set(stored ?? FILE_ACTIONS);

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
      <div className="space-y-2">
        <p className="text-sm font-medium">{t('network.inspector.tool.fileActions')}</p>
        {FILE_ACTIONS.map((action) => (
          <label key={action} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={selected.has(action)}
              disabled={readOnly}
              onCheckedChange={(value) => {
                const next = new Set(selected);
                if (value === true) next.add(action);
                else next.delete(action);
                const ordered = FILE_ACTIONS.filter((item) => next.has(item));
                editorUpdateNodeData(node.id, {
                  fileActions: ordered.length === FILE_ACTIONS.length ? undefined : [...ordered],
                  allowWrite: ordered.some((item) => FILE_WRITE_ACTIONS.has(item)),
                  allowDelete: ordered.includes('delete'),
                });
              }}
            />
            {t(`network.inspector.tool.fileAction.${action}`)}
          </label>
        ))}
      </div>
    </>
  );
}

function ZipFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);

  function applyPath(path: string) {
    const trimmed = path.trim();
    if (!trimmed) return;
    editorUpdateNodeData(node.id, { rootPath: trimmed });
    if (isForbiddenDataRoot(trimmed)) {
      notify({ titleKey: 'network.validation.zipRoot', variant: 'error' });
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
      <p className="text-xs text-muted-foreground">{t('network.inspector.tool.zipHint')}</p>
    </>
  );
}

const TERMINAL_CHOICES = ['git', 'python', 'py', 'dotnet', 'node', 'npm', 'pnpm', 'cargo', 'go'] as const;
const TERMINAL_DEFAULT = ['git', 'python', 'py', 'dotnet'];

function TerminalFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);
  const [extra, setExtra] = useState('');
  const unrestricted = String(node.data.terminalMode ?? 'restricted') === 'unrestricted';
  const stored = Array.isArray(node.data.terminalPrograms) ? node.data.terminalPrograms.map(String) : null;
  const selected = stored ?? TERMINAL_DEFAULT;

  function applyPath(path: string) {
    const trimmed = path.trim();
    if (!trimmed) return;
    editorUpdateNodeData(node.id, { rootPath: trimmed });
    if (isForbiddenDataRoot(trimmed)) {
      notify({ titleKey: 'network.validation.terminalRoot', variant: 'error' });
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

  function setPrograms(next: string[]) {
    editorUpdateNodeData(node.id, { terminalPrograms: next });
  }

  function addExtra() {
    const name = extra.trim().replace(/\.exe$/i, '').toLowerCase();
    if (!/^[a-z0-9._+-]{1,40}$/.test(name)) return;
    setPrograms([...new Set([...selected, name])]);
    setExtra('');
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
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={unrestricted}
          disabled={readOnly}
          onCheckedChange={(value) =>
            editorUpdateNodeData(node.id, { terminalMode: value === true ? 'unrestricted' : 'restricted' })
          }
        />
        {t('network.inspector.tool.terminalUnrestricted')}
      </label>
      <p className="text-xs text-muted-foreground">
        {t(unrestricted ? 'network.inspector.tool.terminalUnrestrictedHint' : 'network.inspector.tool.terminalHint')}
      </p>
      {unrestricted ? null : (
        <div className="space-y-2">
          <p className="text-sm font-medium">{t('network.inspector.tool.terminalPrograms')}</p>
          {TERMINAL_CHOICES.map((program) => (
            <label key={program} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={selected.includes(program)}
                disabled={readOnly}
                onCheckedChange={(value) => {
                  const next = new Set(selected);
                  if (value === true) next.add(program);
                  else next.delete(program);
                  setPrograms([...next]);
                }}
              />
              {program}
            </label>
          ))}
          {selected
            .filter((program) => !TERMINAL_CHOICES.includes(program as (typeof TERMINAL_CHOICES)[number]))
            .map((program) => (
              <label key={program} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked
                  disabled={readOnly}
                  onCheckedChange={() => setPrograms(selected.filter((item) => item !== program))}
                />
                {program}
              </label>
            ))}
          <div className="flex gap-2">
            <Input
              value={extra}
              disabled={readOnly}
              spellCheck={false}
              autoComplete="off"
              placeholder={t('network.inspector.tool.terminalProgramPlaceholder')}
              className="min-w-0 font-mono text-xs"
              onChange={(event) => setExtra(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  addExtra();
                }
              }}
            />
            <Button type="button" size="sm" variant="outline" disabled={readOnly || !extra.trim()} onClick={addExtra}>
              {t('network.inspector.tool.terminalProgramAdd')}
            </Button>
          </div>
        </div>
      )}
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
  const branches = Array.isArray(node.data.branches)
    ? (node.data.branches as Array<{ id: string; name?: string; match?: string; pattern?: string; condition?: string }>)
    : [];

  function stored(next: typeof branches) {
    editorUpdateNodeData(node.id, {
      branches: next.map((branch) => ({
        id: branch.id,
        name: branch.name ?? '',
        match: routerMatchOf(branch.match),
        pattern: routerPatternOf(branch),
      })),
    });
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">{t('network.inspector.router.hint')}</p>
      <p className="text-sm font-medium">{t('network.inspector.router.branches')}</p>
      {branches.map((branch, index) => {
        const match = routerMatchOf(branch.match);
        return (
          <div key={branch.id} className="grid gap-1.5 rounded-md border p-2">
            <Input
              value={branch.name ?? ''}
              disabled={readOnly}
              placeholder={t('network.inspector.router.branchName')}
              onChange={(event) =>
                stored(branches.map((item, i) => (i === index ? { ...item, name: event.target.value } : item)))
              }
            />
            <Select
              value={match}
              disabled={readOnly}
              onValueChange={(next) =>
                stored(
                  branches.map((item, i) =>
                    i === index ? { ...item, match: next as RouterMatch } : item,
                  ),
                )
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROUTER_MATCHES.map((item) => (
                  <SelectItem key={item} value={item}>
                    {t(`network.inspector.router.match.${item}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={routerPatternOf(branch)}
              disabled={readOnly}
              placeholder={t('network.inspector.router.pattern')}
              onChange={(event) =>
                stored(branches.map((item, i) => (i === index ? { ...item, pattern: event.target.value } : item)))
              }
            />
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={readOnly}
              onClick={() => stored(branches.filter((item) => item.id !== branch.id))}
            >
              {t('network.context.delete')}
            </Button>
          </div>
        );
      })}
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={readOnly}
        onClick={() => stored([...branches, { id: newId('br'), name: '', match: 'contains', pattern: '' }])}
      >
        {t('network.inspector.router.add')}
      </Button>
      <div className="rounded-md border border-dashed p-2">
        <p className="text-sm font-medium">{t('network.ports.default')}</p>
        <p className="text-xs text-muted-foreground">{t('network.inspector.router.defaultHint')}</p>
      </div>
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
