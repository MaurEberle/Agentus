import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownAZ, ArrowUpAZ } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ModuleLoading } from '@/components/layout/ModuleLoading';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { notify } from '@/lib/notifications';
import { ExportCancelled, saveExportFile } from '@/lib/saveFile';
import { parseTagTokens } from '@/lib/tags';
import { WidthGrip } from '@/modules/monitoring/PaneGrips';
import { formatDateTime } from '@/modules/history/model/format';
import {
  createPrompt,
  deletePrompts,
  duplicatePrompt,
  exportPrompt,
  getPrompt,
  importPrompts,
  listPrompts,
  savePromptTags,
  updatePrompt,
} from '@/modules/prompts/api';
import type { PromptDetail, PromptDraft, PromptFile, PromptListItem } from '@/modules/prompts/model';
import { parsePromptFile } from '@/modules/prompts/model';
import { unzipTextFiles } from '@/modules/prompts/unzip';
import { TagsDialog } from '@/modules/networks/dialogs/TagsDialog';
import { zipStore } from '@/modules/networks/model/zip';
import { cn } from '@/lib/utils';

const PANE_KEY = 'agentus.prompts.panes';
const DETAIL_SHARE = 0.2;
const DEFAULT_LIST_SHARE = 1 - DETAIL_SHARE;

type Panes = { listShare: number; v: number };

function clampListShare(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_LIST_SHARE;
  return Math.min(0.85, Math.max(0.3, value));
}

function loadPanes(): Panes {
  const fallback: Panes = { listShare: DEFAULT_LIST_SHARE, v: 3 };
  try {
    const raw = JSON.parse(window.localStorage.getItem(PANE_KEY) || '') as Partial<Panes>;
    const storedVersion = Number(raw.v) || 1;
    return {
      listShare: storedVersion < 3 ? DEFAULT_LIST_SHARE : clampListShare(Number(raw.listShare)),
      v: 3,
    };
  } catch {
    return fallback;
  }
}

function safeName(name: string): string {
  const cleaned = name.trim().replace(/[^\w.-]+/g, '-').replace(/-+/g, '-');
  return cleaned || 'prompt';
}

export function PromptsModule() {
  const { t, i18n } = useTranslation();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const query = useQuery({ queryKey: ['prompts'], queryFn: listPrompts });
  const items = useMemo(() => query.data?.items ?? [], [query.data]);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<'name' | 'updated'>('updated');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState<PromptDetail | 'new' | null>(null);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [panes, setPanes] = useState<Panes>(loadPanes);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const next = items.filter((item) => {
      if (!needle) return true;
      return `${item.name} ${item.description} ${item.tags.join(' ')}`.toLowerCase().includes(needle);
    });
    const dir = sortDir === 'asc' ? 1 : -1;
    next.sort((a, b) => {
      if (sortKey === 'name') {
        const byName = a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
        return byName === 0 ? 0 : byName * dir;
      }
      const av = Date.parse(a.updatedAt);
      const bv = Date.parse(b.updatedAt);
      if (av === bv) return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
      return (av - bv) * dir;
    });
    return next;
  }, [items, search, sortDir, sortKey]);

  const selected = useMemo(
    () => selectedIds.map((id) => items.find((item) => item.id === id)).filter((item): item is PromptListItem => Boolean(item)),
    [items, selectedIds],
  );
  const activeId = selected.length === 1 ? selected[0].id : undefined;
  const detailQuery = useQuery({
    queryKey: ['prompts', activeId],
    queryFn: () => getPrompt(activeId as string),
    enabled: Boolean(activeId),
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(PANE_KEY, JSON.stringify(panes));
    } catch {
      /* ignore quota */
    }
  }, [panes]);

  const run = useCallback(async (work: () => Promise<void>, key: string) => {
    setBusy(true);
    try {
      await work();
      notify({ titleKey: key, variant: 'success' });
    } catch (error) {
      if (error instanceof ExportCancelled) return;
      notify({ titleKey: 'prompts.notify.failed', variant: 'error' });
    } finally {
      setBusy(false);
    }
  }, []);

  function chooseSort(key: 'name' | 'updated') {
    setSortDir((dir) => (sortKey === key ? (dir === 'asc' ? 'desc' : 'asc') : 'desc'));
    setSortKey(key);
  }

  function toggle(id: string) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function onExport() {
    await run(async () => {
      if (selected.length === 1) {
        const file = await exportPrompt(selected[0].id);
        const blob = new Blob([JSON.stringify(file, null, 2)], { type: 'application/json' });
        await saveExportFile(`${safeName(selected[0].name)}.json`, blob);
        return;
      }
      const files = [];
      for (const item of selected) {
        const file = await exportPrompt(item.id);
        files.push({
          name: `${safeName(item.name)}.json`,
          data: new TextEncoder().encode(JSON.stringify(file, null, 2)),
        });
      }
      await saveExportFile('prompts.zip', zipStore(files));
    }, 'prompts.notify.exported');
  }

  const listPane = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap gap-2 border-b p-3">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('prompts.search')} className="max-w-xs" />
        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="sm"
            variant={sortKey === 'name' ? 'secondary' : 'outline'}
            onClick={() => chooseSort('name')}
          >
            {t('prompts.sort.name')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={sortKey === 'updated' ? 'secondary' : 'outline'}
            onClick={() => chooseSort('updated')}
          >
            {t('prompts.sort.updated')}
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            onClick={() => setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))}
            aria-label={t('networks.filter.direction')}
          >
            {sortDir === 'asc' ? <ArrowUpAZ className="size-4" /> : <ArrowDownAZ className="size-4" />}
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {filtered.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">{t(items.length ? 'prompts.empty.filter' : 'prompts.empty.library')}</p>
        ) : (
          <ul>
            {filtered.map((item) => (
              <li key={item.id} className={cn('flex items-center gap-2 border-b px-3 py-2', activeId === item.id && 'bg-accent/60')}>
                <Checkbox checked={selectedIds.includes(item.id)} onCheckedChange={() => toggle(item.id)} aria-label={item.name} className="p-0" />
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSelectedIds([item.id])}>
                  <span className="block truncate font-medium">{item.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">{item.description || item.tags.join(', ') || '—'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );

  const detail = (
    <div className="flex h-full min-h-0 flex-col">
      {selected.length === 0 ? (
        <p className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground">{t('prompts.detail.none')}</p>
      ) : selected.length > 1 ? (
        <p className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground">
          {t('prompts.detail.many', { count: selected.length })}
        </p>
      ) : detailQuery.isLoading || !detailQuery.data ? (
        <ModuleLoading />
      ) : (
        <div className="min-h-0 flex-1 space-y-3 overflow-auto p-4">
          <div>
            <h2 className="text-lg font-semibold">{detailQuery.data.name}</h2>
            <p className="text-xs text-muted-foreground">
              {t('prompts.detail.created', { date: formatDateTime(detailQuery.data.createdAt, i18n.language) })}
              {' · '}
              {t('prompts.detail.updated', { date: formatDateTime(detailQuery.data.updatedAt, i18n.language) })}
            </p>
            {detailQuery.data.description ? <p className="mt-1 text-sm text-muted-foreground">{detailQuery.data.description}</p> : null}
          </div>
          <div className="flex flex-wrap gap-1">
            {detailQuery.data.tags.map((tag) => (
              <Badge key={tag} variant="outline">{tag}</Badge>
            ))}
          </div>
          <pre className="w-full min-w-0 whitespace-pre-wrap break-words rounded-md border bg-muted/30 p-3 text-sm">{detailQuery.data.body}</pre>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex flex-wrap gap-2 border-b px-3 py-2">
        <Button type="button" size="sm" onClick={() => setEditor('new')} disabled={busy}>{t('prompts.ribbon.new')}</Button>
        <Button type="button" size="sm" variant="outline" disabled={busy || selected.length !== 1} onClick={() => detailQuery.data && setEditor(detailQuery.data)}>
          {t('prompts.ribbon.edit')}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy || selected.length !== 1} onClick={() => void run(async () => { await duplicatePrompt(selected[0].id); }, 'prompts.notify.duplicated')}>
          {t('prompts.ribbon.duplicate')}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy || selected.length === 0} onClick={() => setTagsOpen(true)}>
          {t('prompts.ribbon.tags')}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy || selected.length === 0} onClick={() => setDeleteOpen(true)}>
          {t('prompts.ribbon.delete')}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => setImportOpen(true)}>{t('prompts.ribbon.import')}</Button>
        <Button type="button" size="sm" variant="outline" disabled={busy || selected.length === 0} onClick={() => void onExport()}>
          {t('prompts.ribbon.export')}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}>
          {t('prompts.ribbon.refresh')}
        </Button>
      </div>
      {query.isError ? (
        <Alert variant="destructive" className="m-3">
          <AlertTitle>{t('prompts.error.title')}</AlertTitle>
          <AlertDescription>{t('prompts.error.body')}</AlertDescription>
        </Alert>
      ) : null}
      {query.isLoading ? <ModuleLoading /> : (
        <div data-split-row className="flex min-h-0 w-full flex-1">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="min-h-0 w-full flex-1 overflow-hidden">{listPane}</div>
          </div>
          {isDesktop ? (
            <WidthGrip
              label={t('prompts.resize.width')}
              share={panes.listShare}
              onChange={(listShare) => setPanes((current) => ({ ...current, listShare: clampListShare(listShare) }))}
            />
          ) : null}
          {isDesktop ? (
            <div
              className="flex h-full min-h-0 min-w-0 shrink-0 flex-col"
              style={{ width: `${(1 - panes.listShare) * 100}%` }}
            >
              <div className="min-h-0 w-full min-w-0 flex-1 overflow-hidden">{detail}</div>
            </div>
          ) : null}
        </div>
      )}
      <PromptEditor
        open={editor !== null}
        initial={editor && editor !== 'new' ? editor : null}
        busy={busy}
        onClose={() => setEditor(null)}
        onSave={(draft) => void run(async () => {
          if (editor && editor !== 'new') await updatePrompt(editor.id, draft);
          else await createPrompt(draft);
          setEditor(null);
        }, editor && editor !== 'new' ? 'prompts.notify.saved' : 'prompts.notify.created')}
      />
      <TagsDialog
        open={tagsOpen}
        count={selected.length}
        busy={busy}
        initialTags={parseTagTokens(selected.flatMap((item) => item.tags).join(','))}
        suggestions={parseTagTokens(items.flatMap((item) => item.tags).join(','))}
        onClose={() => setTagsOpen(false)}
        onSave={(next) => void run(async () => {
          const seed = selected[0]?.tags ?? [];
          await savePromptTags(selected, seed, next);
          setTagsOpen(false);
        }, 'prompts.notify.tagged')}
      />
      <Dialog open={deleteOpen} onOpenChange={(open) => !open && setDeleteOpen(false)}>
        <DialogContent closeLabel={t('prompts.dialog.close')}>
          <DialogHeader>
            <DialogTitle>{t('prompts.delete.title', { count: selected.length })}</DialogTitle>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteOpen(false)}>{t('prompts.dialog.cancel')}</Button>
            <Button type="button" variant="destructive" disabled={busy} onClick={() => void run(async () => {
              await deletePrompts(selected.map((item) => item.id));
              setSelectedIds([]);
              setDeleteOpen(false);
            }, 'prompts.notify.deleted')}>
              {t('prompts.ribbon.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ImportPromptsDialog
        open={importOpen}
        busy={busy}
        onClose={() => setImportOpen(false)}
        onImport={(drafts) => void run(async () => {
          await importPrompts(drafts);
          setImportOpen(false);
        }, 'prompts.notify.imported')}
      />
    </div>
  );
}

function PromptEditor({
  open,
  initial,
  busy,
  onClose,
  onSave,
}: {
  open: boolean;
  initial: PromptDetail | null;
  busy: boolean;
  onClose: () => void;
  onSave: (draft: PromptDraft) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [body, setBody] = useState('');

  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? '');
    setDescription(initial?.description ?? '');
    setTags(initial?.tags.join(', ') ?? '');
    setBody(initial?.body ?? '');
  }, [initial, open]);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent closeLabel={t('prompts.dialog.close')} className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{initial ? t('prompts.editor.edit') : t('prompts.editor.create')}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="prompt-name">{t('prompts.editor.name')}</Label>
            <Input id="prompt-name" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="prompt-description">{t('prompts.editor.description')}</Label>
            <Input id="prompt-description" value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="prompt-tags">{t('prompts.editor.tags')}</Label>
            <Input id="prompt-tags" value={tags} onChange={(event) => setTags(event.target.value)} placeholder={t('prompts.editor.tagsHint')} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="prompt-body">{t('prompts.editor.body')}</Label>
            <Textarea id="prompt-body" value={body} onChange={(event) => setBody(event.target.value)} className="min-h-48 font-mono text-sm" />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>{t('prompts.dialog.cancel')}</Button>
          <Button type="button" disabled={busy || !name.trim()} onClick={() => onSave({ name: name.trim(), description: description.trim(), tags: parseTagTokens(tags), body })}>
            {t('prompts.editor.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportPromptsDialog({
  open,
  busy,
  onClose,
  onImport,
}: {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onImport: (drafts: PromptDraft[]) => void;
}) {
  const { t } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<PromptFile[]>([]);

  useEffect(() => {
    if (!open) setFiles([]);
  }, [open]);

  async function onFiles(list: FileList | null) {
    if (!list?.length) return;
    const next: PromptFile[] = [];
    for (const file of Array.from(list)) {
      const lower = file.name.toLowerCase();
      if (lower.endsWith('.zip')) {
        const packed = await unzipTextFiles(await file.arrayBuffer());
        if (!packed.length) {
          next.push({ fileName: file.name, ok: false });
          continue;
        }
        for (const entry of packed) next.push(...parsePromptFile(entry.name, entry.text));
        continue;
      }
      next.push(...parsePromptFile(file.name, await file.text()));
    }
    setFiles(next);
  }

  const ready = files.flatMap((file) => (file.ok && file.draft ? [file.draft] : []));

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent closeLabel={t('prompts.dialog.close')} className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('prompts.import.title')}</DialogTitle>
        </DialogHeader>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".json,.prompty,.md,.zip,application/json,application/zip"
          className="hidden"
          onChange={(event) => {
            void onFiles(event.target.files);
            event.target.value = '';
          }}
        />
        <Button type="button" variant="outline" className="w-fit" onClick={() => fileRef.current?.click()} disabled={busy}>
          {t('prompts.import.pick')}
        </Button>
        {files.length === 0 ? <p className="text-sm text-muted-foreground">{t('prompts.import.empty')}</p> : null}
        <ul className="max-h-64 space-y-1 overflow-auto text-sm">
          {files.map((file, index) => (
            <li key={`${file.fileName}-${index}`} className={file.ok ? '' : 'text-destructive'}>
              {file.ok ? file.draft?.name : t('prompts.import.unreadable', { name: file.fileName })}
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>{t('prompts.dialog.cancel')}</Button>
          <Button type="button" disabled={busy || ready.length === 0} onClick={() => onImport(ready)}>
            {t('prompts.import.save', { count: ready.length })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
