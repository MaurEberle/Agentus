import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { pickFolderPath } from '@/lib/pickFolder';
import {
  useEditorCredentialsQuery,
  useMcpServersQuery,
  reindexNetworkKnowledge,
  testLlmConnection,
} from '@/modules/network/api';
import { useRuntimeModelsQuery } from '@/modules/settings/api';
import type { GraphNode, ValidationIssue } from '@/modules/network/model/document';
import { newId } from '@/modules/network/model/document';
import { editorDeleteSelection, editorUpdateNodeData, useNetworkEditor } from '@/modules/network/store';
import { notify } from '@/lib/notifications';
import { isEmbeddingModelName, isForbiddenDataRoot } from '@/modules/settings/model';

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
        <Field label={t('network.inspector.graph.tags')}>
          <Input
            value={(document.tags ?? []).join(', ')}
            disabled={readOnly}
            onChange={(event) =>
              setMeta({
                tags: event.target.value
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
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
    <div className="space-y-4 p-3">
      <h2 className="text-sm font-semibold">{t(`network.palette.${node.type}`)}</h2>
      <DisplayNameField node={node} readOnly={readOnly} />
      {node.type === 'llm' ? <LlmFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'agent' ? <AgentFields node={node} readOnly={readOnly} /> : null}
      {node.type === 'tool' ? <ToolFields node={node} readOnly={readOnly} /> : null}
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

function ModelCombobox({
  value,
  options,
  disabled,
  onChange,
  placeholder,
}: {
  value: string;
  options: string[];
  disabled?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const names = value && !options.includes(value) ? [value, ...options] : options;
  const query = search.trim().toLowerCase();
  const filtered = query ? names.filter((item) => item.toLowerCase().includes(query)) : names;
  const exact = names.some((item) => item.toLowerCase() === query);

  function commit(next: string) {
    onChange(next);
    setOpen(false);
    setSearch('');
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setSearch('');
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="h-8 w-full justify-between px-2.5 font-normal"
        >
          <span className={cn('truncate', !value && 'text-muted-foreground')}>
            {value || placeholder || t('network.inspector.llm.model')}
          </span>
          <ChevronDown className="size-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={4} className="z-[80] w-[var(--radix-popover-trigger-width)] p-1">
        <Input
          value={search}
          autoFocus
          disabled={disabled}
          placeholder={t('network.inspector.llm.model')}
          className="mb-1 h-8"
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              const next = search.trim();
              if (next) commit(next);
            }
          }}
        />
        <ul className="max-h-48 overflow-auto">
          {filtered.map((item) => (
            <li key={item}>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
                onClick={() => commit(item)}
              >
                <Check className={cn('size-3.5 shrink-0', item === value ? 'opacity-100' : 'opacity-0')} />
                <span className="truncate">{item}</span>
              </button>
            </li>
          ))}
          {query && !exact ? (
            <li>
              <button
                type="button"
                className="flex w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
                onClick={() => commit(search.trim())}
              >
                {t('network.inspector.llm.useModel', { name: search.trim() })}
              </button>
            </li>
          ) : null}
          {filtered.length === 0 && !query ? (
            <li className="px-2 py-1.5 text-sm text-muted-foreground">{t('network.inspector.llm.noModels')}</li>
          ) : null}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
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
  const matchingCredentials = (credentials.data?.items ?? []).filter(
    (item) => item.kind === provider || item.kind === 'token',
  );
  const xaiCredentials = (credentials.data?.items ?? []).filter((item) => item.kind === 'xai');
  const ollamaModels = useRuntimeModelsQuery({ enabled: provider === 'ollama' });
  const xaiModels = useRuntimeModelsQuery({
    provider: 'xai',
    credentialId,
    enabled: provider === 'xai' && Boolean(credentialId),
  });

  const modelOptions =
    provider === 'ollama'
      ? (ollamaModels.data?.items ?? []).map((item) => item.name).filter((name) => !isEmbeddingModelName(name))
      : provider === 'xai'
        ? (xaiModels.data?.items ?? []).map((item) => item.name)
        : [];
  const modelLocked = provider === 'xai' && !credentialId;
  const xaiModelsFailed =
    provider === 'xai' &&
    Boolean(credentialId) &&
    !xaiModels.isFetching &&
    !xaiModels.isPending &&
    (xaiModels.data?.items.length ?? 0) === 0;

  function setProvider(next: string) {
    const patch: Record<string, unknown> = { provider: next };
    if (next !== provider) {
      patch.model = '';
    }
    if (next === 'ollama') {
      patch.credentialId = undefined;
    } else if (next === 'xai') {
      const current = matchingCredentials.find((item) => item.id === credentialId);
      if (!current || (current.kind !== 'xai' && current.kind !== 'token')) {
        patch.credentialId = xaiCredentials.length === 1 ? xaiCredentials[0].id : undefined;
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
    provider !== 'ollama' ? (
      <Field label={t('network.inspector.llm.credential')}>
        <Select
          value={credentialId ?? 'none'}
          disabled={readOnly}
          onValueChange={(value) =>
            editorUpdateNodeData(node.id, {
              credentialId: value === 'none' ? undefined : value,
              ...(provider === 'xai' ? { model: '' } : {}),
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
        {provider === 'xai' && matchingCredentials.length === 0 ? (
          <p className="text-xs text-destructive">
            {t('network.inspector.llm.noCredentials')}{' '}
            <Link to="/settings#credentials" className="underline">
              {t('nav.settings')}
            </Link>
          </p>
        ) : provider === 'xai' ? (
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
            <SelectItem value="ollama">Ollama</SelectItem>
            <SelectItem value="xai">xAI</SelectItem>
            <SelectItem value="openai_compat">{t('network.inspector.llm.openaiCompat')}</SelectItem>
          </SelectContent>
        </Select>
      </Field>
      {provider === 'xai' ? credentialField : null}
      <Field label={t('network.inspector.llm.model')}>
        <ModelCombobox
          value={modelLocked ? '' : model}
          options={modelOptions}
          disabled={readOnly || modelLocked}
          placeholder={
            modelLocked ? t('network.inspector.llm.pickCredentialFirst') : t('network.inspector.llm.model')
          }
          onChange={(value) => editorUpdateNodeData(node.id, { model: value })}
        />
        {xaiModelsFailed ? (
          <p className="text-xs text-destructive">{t('network.inspector.llm.modelsLoadError')}</p>
        ) : null}
      </Field>
      {provider !== 'ollama' && provider !== 'xai' ? credentialField : null}
      {provider === 'openai_compat' ? (
        <Field label={t('network.inspector.llm.baseUrl')}>
          <Input
            value={String(node.data.baseUrl ?? '')}
            disabled={readOnly}
            onChange={(event) => editorUpdateNodeData(node.id, { baseUrl: event.target.value })}
          />
        </Field>
      ) : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={pinging || !model || modelLocked}
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

function AgentFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <p className="text-xs text-muted-foreground">{t('network.inspector.agent.hint')}</p>
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
  const mcp = useMcpServersQuery();
  const kind = String(node.data.kind ?? 'datetime');
  const kinds = ['http', 'web_search', 'datetime', 'calculator', 'mcp'] as const;
  const enabledServers = (mcp.data?.items ?? []).filter((item) => item.enabled);

  return (
    <>
      <Field label={t('network.inspector.tool.kind')}>
        <Select
          value={kind}
          disabled={readOnly}
          onValueChange={(value) => editorUpdateNodeData(node.id, { kind: value })}
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
            value={String(node.data.credentialId ?? 'none')}
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
              {(credentials.data?.items ?? []).map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      ) : null}
      {kind === 'mcp' ? (
        <>
          <Field label={t('network.inspector.tool.mcpServer')}>
            <Select
              value={String(node.data.mcpServerId ?? 'none')}
              disabled={readOnly}
              onValueChange={(value) =>
                editorUpdateNodeData(node.id, { mcpServerId: value === 'none' ? undefined : value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('network.inspector.tool.mcpEmpty')}</SelectItem>
                {enabledServers.map((server) => (
                  <SelectItem key={server.id} value={server.id}>
                    {server.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <p className="text-xs text-muted-foreground">{t('network.inspector.tool.mcpHint')}</p>
          <Button asChild size="sm" variant="link">
            <Link to="/settings#mcp">{t('network.inspector.tool.mcpSettings')}</Link>
          </Button>
        </>
      ) : null}
    </>
  );
}

function KnowledgeFields({ node, readOnly }: { node: GraphNode; readOnly: boolean }) {
  const { t } = useTranslation();
  const document = useNetworkEditor((state) => state.document);
  const [reindexing, setReindexing] = useState(false);
  const [picking, setPicking] = useState(false);

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
          <Button type="button" size="sm" variant="outline" disabled={readOnly || picking} onClick={() => void pick()}>
            {t('network.inspector.knowledge.pick')}
          </Button>
        </div>
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
      <Button type="button" size="sm" variant="outline" disabled={!document.id || reindexing} onClick={() => void reindex()}>
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
