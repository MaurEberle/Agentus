import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { getChromeHost } from '@/lib/chromeHost';
import {
  useEditorCredentialsQuery,
  useEditorModelsQuery,
  useMcpServersQuery,
  reindexNetworkKnowledge,
  testLlmConnection,
} from '@/modules/network/api';
import type { GraphNode, ValidationIssue } from '@/modules/network/model/document';
import { newId } from '@/modules/network/model/document';
import { editorDeleteSelection, editorUpdateNodeData, useNetworkEditor } from '@/modules/network/store';
import { notify } from '@/lib/notifications';
import { isForbiddenDataRoot } from '@/modules/settings/model';

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
  const models = useEditorModelsQuery();
  const [advanced, setAdvanced] = useState(false);
  const [pinging, setPinging] = useState(false);
  const provider = String(node.data.provider ?? 'ollama');
  const model = String(node.data.model ?? '');

  async function ping() {
    setPinging(true);
    try {
      const result = await testLlmConnection({
        provider,
        model,
        baseUrl: String(node.data.baseUrl ?? '') || undefined,
        credentialId: String(node.data.credentialId ?? '') || undefined,
      });
      notify({
        titleKey: result.messageKey ?? (result.ok ? 'network.inspector.llm.pingOk' : 'network.inspector.llm.pingFail'),
        variant: result.ok ? 'success' : 'error',
      });
    } finally {
      setPinging(false);
    }
  }

  return (
    <>
      <Field label={t('network.inspector.llm.provider')}>
        <Select
          value={provider}
          disabled={readOnly}
          onValueChange={(value) => editorUpdateNodeData(node.id, { provider: value })}
        >
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
      <Field label={t('network.inspector.llm.model')}>
        <Input
          value={model}
          disabled={readOnly}
          list="network-llm-models"
          onChange={(event) => editorUpdateNodeData(node.id, { model: event.target.value })}
        />
        <datalist id="network-llm-models">
          {(models.data?.items ?? []).map((item) => (
            <option key={item.name} value={item.name} />
          ))}
        </datalist>
      </Field>
      {provider !== 'ollama' ? (
        <Field label={t('network.inspector.llm.credential')}>
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
              {(credentials.data?.items ?? [])
                .filter((item) => item.kind === provider || item.kind === 'token')
                .map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </Field>
      ) : null}
      {provider === 'openai_compat' ? (
        <Field label={t('network.inspector.llm.baseUrl')}>
          <Input
            value={String(node.data.baseUrl ?? '')}
            disabled={readOnly}
            onChange={(event) => editorUpdateNodeData(node.id, { baseUrl: event.target.value })}
          />
        </Field>
      ) : null}
      <Button type="button" size="sm" variant="outline" disabled={pinging || !model} onClick={() => void ping()}>
        {t('network.inspector.llm.ping')}
      </Button>
      <button type="button" className="text-xs text-muted-foreground underline" onClick={() => setAdvanced((v) => !v)}>
        {t('network.inspector.llm.advanced')}
      </button>
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

  async function pick() {
    const host = getChromeHost();
    const path = host?.pickFolder ? await host.pickFolder() : 'C:\\Users\\Demo\\AppData\\Local\\Agentus-Network\\data\\workspace\\docs';
    if (!path) return;
    if (isForbiddenDataRoot(path)) {
      notify({ titleKey: 'network.validation.knowledgeRoot', variant: 'error' });
      return;
    }
    editorUpdateNodeData(node.id, { sourcePath: path });
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
            onChange={(event) => editorUpdateNodeData(node.id, { sourcePath: event.target.value })}
          />
          <Button type="button" size="sm" variant="outline" disabled={readOnly} onClick={() => void pick()}>
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
