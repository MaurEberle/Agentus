import { useMemo } from 'react';
import { CircleAlert, EyeOff, FileInput, Info, PackageCheck, Undo2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { undoable, type ArchitectState } from '@/modules/architect/api';
import { DiffList } from '@/modules/network/versions/DiffList';
import type { ValidationIssue } from '@/modules/network/model/document';
import { DocumentGraph, type NodeMark } from '@/modules/networks/detail/ReadonlyGraph';

function nodeLine(node: { type: string; data: Record<string, unknown> }): string {
  const data = node.data ?? {};
  if (node.type === 'llm') return [data.provider, data.model].filter(Boolean).join(' · ');
  if (node.type === 'tool') return String(data.kind ?? '');
  if (node.type === 'mcp') return String(data.mcpServer ?? data.mcpServerId ?? '');
  return String(data.displayName ?? '');
}

type Actions = {
  /** No session picked: nothing to read in or close. */
  disabled: boolean;
  undoBusy: boolean;
  onLoad: () => void;
  onClose: () => void;
  onUndo: () => void;
};

function SourceLine({ state }: { state: ArchitectState }) {
  const { t } = useTranslation();
  const source = state.source;
  if (!source) return null;
  const hidden = Object.keys(source.hidden ?? {}).length > 0;
  return (
    <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
      <span className="truncate">
        {source.purpose === 'change'
          ? t('architect.source.change', { name: source.name, version: source.version ?? '' })
          : t('architect.source.template', { name: source.name })}
      </span>
      {hidden ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex shrink-0" tabIndex={0} aria-label={t('architect.source.hidden')}>
              <EyeOff className="size-3.5" aria-hidden />
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">{t('architect.source.hidden')}</TooltipContent>
        </Tooltip>
      ) : null}
    </p>
  );
}

/** The draft as a graph with what it changes, its check, its nodes and the closing actions. */
export function DraftPanel({
  state,
  layoutWidth,
  actions,
}: {
  state: ArchitectState | null;
  layoutWidth: number;
  actions: Actions;
}) {
  const { t } = useTranslation();
  const document = state?.document ?? null;
  const check = state?.check ?? null;
  const issues = useMemo<ValidationIssue[]>(() => {
    if (!check || !state) return [];
    return check.errors
      .filter((item) => item.ref && state.ids[item.ref])
      .map((item) => ({ nodeId: state.ids[item.ref as string], messageKey: item.key ?? 'architect.draft.error' }));
  }, [check, state]);
  const marks = useMemo<Record<string, NodeMark>>(() => {
    const out: Record<string, NodeMark> = {};
    for (const id of state?.diff?.added ?? []) out[id] = 'added';
    for (const item of state?.diff?.changed ?? []) out[item.id] = 'changed';
    return out;
  }, [state?.diff]);
  const lastUndoable = undoable(state?.applied);

  const loadButton = (
    <Button type="button" size="sm" variant="outline" disabled={actions.disabled} onClick={actions.onLoad}>
      <FileInput className="size-3.5" aria-hidden />
      {t('architect.load.button')}
    </Button>
  );

  if (!document || !state?.draft) {
    return (
      <section className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-4 text-center text-sm text-muted-foreground">
        <p>{t('architect.draft.empty')}</p>
        {loadButton}
      </section>
    );
  }
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <header className="grid gap-1 border-y px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{state.draft.name || t('architect.draft.unnamed')}</h2>
          {check ? (
            <Badge variant={check.ok ? 'default' : 'destructive'}>
              {check.ok ? t('architect.draft.valid') : t('architect.draft.errors', { count: check.errors.length })}
            </Badge>
          ) : null}
        </div>
        <SourceLine state={state} />
        <div className="flex flex-wrap gap-2">
          {loadButton}
          {lastUndoable ? (
            <Button type="button" size="sm" variant="outline" loading={actions.undoBusy} disabled={actions.disabled} onClick={actions.onUndo}>
              <Undo2 className="size-3.5" aria-hidden />
              {t('architect.undo.button')}
            </Button>
          ) : null}
          <Button type="button" size="sm" className="ms-auto" disabled={actions.disabled || !check?.ok} onClick={actions.onClose}>
            <PackageCheck className="size-3.5" aria-hidden />
            {t('architect.closing.button')}
          </Button>
        </div>
      </header>
      <div className="min-h-56 flex-1 overflow-hidden">
        <DocumentGraph document={document} layoutWidth={layoutWidth} issues={issues} marks={marks} />
      </div>
      <div className="max-h-[40%] min-h-0 overflow-auto border-t p-3 text-sm">
        {check && (check.errors.length > 0 || check.hints.length > 0) ? (
          <ul className="mb-3 grid gap-1">
            {check.errors.map((item, index) => (
              <li key={`e${index}`} className="flex gap-1.5 text-destructive">
                <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                <span>{item.text}</span>
              </li>
            ))}
            {check.hints.map((item, index) => (
              <li key={`h${index}`} className="flex gap-1.5 text-muted-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {state.diff && !state.diff.empty ? (
          <div className="mb-3 grid gap-1">
            <h3 className="text-xs font-medium">{t('architect.diff.title', { version: state.source?.version ?? '' })}</h3>
            <DiffList diff={state.diff} />
          </div>
        ) : null}
        <dl className="grid grid-cols-[max-content_max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
          {state.draft.nodes.map((node) => (
            <div key={node.ref} className="contents">
              <dt className="font-medium">{node.ref}</dt>
              <dd className="text-muted-foreground">{t(`network.palette.${node.type}`, { defaultValue: node.type })}</dd>
              <dd className="truncate text-muted-foreground">{nodeLine(node)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
