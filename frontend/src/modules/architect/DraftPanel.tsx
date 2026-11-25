import { useMemo } from 'react';
import { ChevronDown, CircleAlert, EyeOff, FileInput, Info, PackageCheck, Undo2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { undoable, type ArchitectCheck, type ArchitectState } from '@/modules/architect/api';
import { DiffList } from '@/modules/network/versions/DiffList';
import type { ValidationIssue } from '@/modules/network/model/document';
import { DocumentGraph, type NodeMark } from '@/modules/networks/detail/ReadonlyGraph';

/** The check as a badge; errors and hints open from it instead of taking room below the graph. */
function CheckBadge({ check }: { check: ArchitectCheck }) {
  const { t, i18n } = useTranslation();
  // The check speaks to the model in English; a validation key reads in the UI language.
  const text = (item: ArchitectCheck['errors'][number]) => (item.key && i18n.exists(item.key) ? t(item.key) : item.text);
  const label = check.ok ? t('architect.draft.valid') : t('architect.draft.errors', { count: check.errors.length });
  const problems = check.errors.length + check.hints.length;
  if (problems === 0) return <Badge variant="default">{label}</Badge>;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={t('architect.draft.details', { label })}
        >
          <Badge variant={check.ok ? 'default' : 'destructive'} className="cursor-pointer gap-1">
            {label}
            {check.hints.length > 0 ? <span className="opacity-80">· {t('architect.draft.hints', { count: check.hints.length })}</span> : null}
            <ChevronDown className="size-3" aria-hidden />
          </Badge>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 max-w-[90vw] p-3">
        <ul className="grid max-h-72 gap-1.5 overflow-y-auto text-sm">
          {check.errors.map((item, index) => (
            <li key={`e${index}`} className="flex gap-1.5 text-destructive">
              <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>{text(item)}</span>
            </li>
          ))}
          {check.hints.map((item, index) => (
            <li key={`h${index}`} className="flex gap-1.5 text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>{text(item)}</span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
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
  const diff = state.diff && !state.diff.empty ? state.diff : null;
  const changes = diff ? diff.added.length + diff.changed.length + diff.removed.length + (diff.head.length ? 1 : 0) : 0;
  return (
    <div className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
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
      {diff ? (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                'ms-1 inline-flex shrink-0 items-center gap-0.5 rounded-sm px-1 font-medium text-foreground underline-offset-2 hover:underline',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              )}
            >
              {t('architect.diff.count', { count: changes })}
              <ChevronDown className="size-3" aria-hidden />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-80 max-w-[90vw] p-3">
            <p className="mb-2 text-xs font-medium">{t('architect.diff.title', { version: source.version ?? '' })}</p>
            <div className="max-h-72 overflow-y-auto">
              <DiffList diff={diff} />
            </div>
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
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
          {check ? <CheckBadge check={check} /> : null}
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
    </section>
  );
}
