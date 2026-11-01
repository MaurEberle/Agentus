import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownAZ, ArrowUpAZ, Tags, Trash2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError, apiFetch, queryClient } from '@/api/client';
import { ModuleLoading } from '@/components/layout/ModuleLoading';
import { Spinner } from '@/components/ui/spinner';
import { TagCloud } from '@/components/tags/TagCloud';
import { TagInput, type TagInputHandle } from '@/components/TagInput';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { WidthGrip } from '@/modules/monitoring/PaneGrips';
import { formatBytes, formatDateTime } from '@/lib/format';
import { matchesTags, parseTagTokens, type TagMatch } from '@/lib/tags';
import { cn } from '@/lib/utils';
import { listInstalled, saveModelTags } from '@/modules/models/api';
import { HubPane } from '@/modules/models/HubPane';
import type { InstalledModel, ModelKind } from '@/modules/models/model';
import { useModelStatsQuery } from '@/modules/settings/api';

const KINDS: ModelKind[] = ['embedding', 'image', 'moe', 'normal'];

function usageText(t: (key: string, options?: Record<string, string>) => string, usage: { kind: string; network?: string; node?: string }) {
  if (usage.kind === 'network') return t('models.delete.network', { network: usage.network ?? '', node: usage.node ?? '' });
  if (usage.kind === 'help.llm') return t('models.delete.helpLlm');
  if (usage.kind === 'help.embed') return t('models.delete.helpEmbed');
  if (usage.kind === 'help.fallback') return t('models.delete.helpFallback');
  if (usage.kind === 'run') return t('models.delete.run');
  return usage.kind;
}

function clampShare(value: number): number {
  if (!Number.isFinite(value)) return 0.62;
  return Math.min(0.75, Math.max(0.4, value));
}

export function ModelsModule() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<'installed' | 'hub'>('installed');
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div role="tablist" className="flex gap-1 border-b px-3">
        {(['installed', 'hub'] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm',
              tab === key ? 'border-primary font-semibold' : 'border-transparent font-medium text-muted-foreground',
            )}
            onClick={() => setTab(key)}
          >
            {t(`models.tabs.${key}`)}
          </button>
        ))}
      </div>
      {tab === 'installed' ? <InstalledPane /> : <HubPane />}
    </div>
  );
}

function InstalledPane() {
  const { t, i18n } = useTranslation();
  const query = useQuery({ queryKey: ['models'], queryFn: listInstalled });
  const items = query.data?.items ?? [];
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<'name' | 'size' | 'modified'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [kind, setKind] = useState<'all' | ModelKind>('all');
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [tagMode, setTagMode] = useState<TagMatch>('or');
  const [selectedNames, setSelectedNames] = useState<string[]>([]);
  const [share, setShare] = useState(0.62);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const suggestions = useMemo(() => parseTagTokens(items.flatMap((item) => item.tags).join(',')), [items]);
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const next = items.filter((item) => {
      if (kind !== 'all' && item.kind !== kind) return false;
      if (!matchesTags(item.tags, tagFilter, tagMode)) return false;
      if (!needle) return true;
      const hay = `${item.name} ${item.family ?? ''} ${item.quantization ?? ''} ${item.architecture ?? ''}`.toLowerCase();
      return hay.includes(needle);
    });
    const dir = sortDir === 'asc' ? 1 : -1;
    next.sort((a, b) => {
      if (sortKey === 'size') return ((a.sizeBytes ?? 0) - (b.sizeBytes ?? 0)) * dir;
      if (sortKey === 'modified') return (a.modifiedAt ?? '').localeCompare(b.modifiedAt ?? '') * dir;
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }) * dir;
    });
    return next;
  }, [items, kind, search, sortDir, sortKey, tagFilter, tagMode]);
  const selectedItems = items.filter((item) => selectedNames.includes(item.name));
  const detailItem = selectedItems.length === 1 ? selectedItems[0] : null;
  const visibleNames = filtered.map((item) => item.name);
  const allVisibleSelected = visibleNames.length > 0 && visibleNames.every((name) => selectedNames.includes(name));

  function toggle(name: string) {
    setSelectedNames((current) => (current.includes(name) ? current.filter((item) => item !== name) : [...current, name]));
  }

  function toggleAll() {
    if (allVisibleSelected) {
      const visible = new Set(visibleNames);
      setSelectedNames((current) => current.filter((name) => !visible.has(name)));
      return;
    }
    setSelectedNames((current) => [...new Set([...current, ...visibleNames])]);
  }

  function chooseSort(key: 'name' | 'size' | 'modified') {
    if (sortKey === key) setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <Button type="button" size="sm" variant="outline" disabled={selectedItems.length !== 1} onClick={() => setTagsOpen(true)}>
          <Tags />
          {t('models.ribbon.tags')}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          disabled={selectedItems.length === 0}
          onClick={() => setDeleteOpen(true)}
        >
          <Trash2 />
          {t('models.ribbon.delete')}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('models.search')}
          aria-label={t('models.search')}
          className="h-8 max-w-xs"
        />
        <div className="flex items-center gap-1">
          {(['name', 'size', 'modified'] as const).map((key) => (
            <Button key={key} type="button" size="sm" variant={sortKey === key ? 'secondary' : 'outline'} onClick={() => chooseSort(key)}>
              {t(`models.sort.${key}`)}
            </Button>
          ))}
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="size-8"
            aria-label={t('networks.filter.direction')}
            onClick={() => setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))}
          >
            {sortDir === 'asc' ? <ArrowUpAZ className="size-4" /> : <ArrowDownAZ className="size-4" />}
          </Button>
        </div>
        <span className="mx-1 h-6 w-px shrink-0 bg-border" aria-hidden />
        <Select value={kind} onValueChange={(value) => setKind(value as typeof kind)}>
          <SelectTrigger className="w-36 shrink-0" aria-label={t('models.kind.label')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('models.kind.all')}</SelectItem>
            {KINDS.map((key) => (
              <SelectItem key={key} value={key}>{t(`models.kind.${key}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="mx-1 h-6 w-px shrink-0 bg-border" aria-hidden />
        <TagCloud
          tags={suggestions}
          tagSets={items.map((item) => item.tags)}
          selected={tagFilter}
          mode={tagMode}
          onToggle={(tag) => setTagFilter((current) => (current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]))}
          onClear={() => setTagFilter([])}
          onModeChange={setTagMode}
          label={t('models.filter.tags')}
        />
      </div>
      <div data-split-row className="flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {!query.isLoading && !query.data?.messageKey && filtered.length > 0 ? (
            <div className="flex items-center border-b py-2">
              <div className="px-3">
                <Checkbox
                  checked={allVisibleSelected ? true : visibleNames.some((name) => selectedNames.includes(name)) ? 'indeterminate' : false}
                  onCheckedChange={toggleAll}
                  aria-label={t('models.list.selectAll')}
                />
              </div>
              <span className="px-3 text-sm text-muted-foreground">{t('models.list.selectAll')}</span>
            </div>
          ) : null}
        <div className="min-h-0 min-w-0 flex-1 overflow-auto">
          {query.isLoading ? (
            <ModuleLoading />
          ) : query.data?.messageKey ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.unreachable')}</p>
          ) : filtered.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.empty')}</p>
          ) : (
            <>
            {query.isFetching ? (
              <div className="flex items-center gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
                <Spinner size="sm" label={t('app.loading')} />
                <span>{t('app.loading')}</span>
              </div>
            ) : null}
            {KINDS.map((group) => {
              const rows = filtered.filter((item) => item.kind === group);
              if (rows.length === 0) return null;
              return (
                <section key={group}>
                  <h2 className="sticky top-0 border-b bg-background px-3 py-2 text-sm font-medium">{t(`models.kind.${group}`)}</h2>
                  <ul>
                    {rows.map((item) => (
                      <li key={item.name} className={cn('flex items-center border-b', selectedNames.includes(item.name) && 'bg-accent/60')}>
                        <div className="px-3" onClick={(event) => event.stopPropagation()}>
                          <Checkbox checked={selectedNames.includes(item.name)} onCheckedChange={() => toggle(item.name)} aria-label={item.name} />
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedNames([item.name])}
                          className="flex min-w-0 flex-1 flex-col gap-0.5 px-3 py-2 text-left"
                        >
                          <span className="truncate font-mono text-xs">{item.name}</span>
                          <span className="truncate text-xs text-muted-foreground">
                            {[
                              item.sizeBytes ? formatBytes(item.sizeBytes, i18n.language) : '',
                              item.parameterSize,
                              item.quantization,
                              item.vision ? t('models.badges.vision') : '',
                              item.tools ? t('models.badges.tools') : '',
                              item.thinking ? t('models.badges.thinking') : '',
                            ].filter(Boolean).join(' · ')}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
            </>
          )}
        </div>
        </div>
        <WidthGrip label={t('models.split')} share={share} onChange={(next) => setShare(clampShare(next))} />
        <div className="min-h-0 min-w-0 overflow-auto border-l" style={{ width: `${(1 - share) * 100}%` }}>
          {selectedItems.length > 1 ? (
            <p className="p-4 text-sm text-muted-foreground">{t('models.detail.many', { count: selectedItems.length })}</p>
          ) : (
            <DetailPane item={detailItem} />
          )}
        </div>
      </div>
      <TagsEditor
        open={tagsOpen}
        item={detailItem}
        suggestions={suggestions}
        onClose={() => setTagsOpen(false)}
      />
      <DeleteModelDialog
        open={deleteOpen}
        items={selectedItems}
        onClose={() => setDeleteOpen(false)}
        onDeleted={(removed) => setSelectedNames((current) => current.filter((name) => !removed.includes(name)))}
      />
    </div>
  );
}

function DetailPane({ item }: { item: InstalledModel | null }) {
  const { t, i18n } = useTranslation();
  const stats = useModelStatsQuery({ provider: 'ollama', model: item?.name ?? '', enabled: Boolean(item) });
  if (!item) return <p className="p-4 text-sm text-muted-foreground">{t('models.detail.empty')}</p>;
  const rows: [string, string][] = [
    [t('models.detail.size'), item.sizeBytes ? formatBytes(item.sizeBytes, i18n.language) : '—'],
    [t('models.detail.modified'), item.modifiedAt ? formatDateTime(item.modifiedAt, i18n.language) : '—'],
    [t('models.detail.loaded'), item.loaded ? t('models.detail.loadedYes') : t('models.detail.loadedNo')],
    [t('models.detail.family'), item.family || '—'],
    [t('models.detail.parameters'), item.parameterSize || '—'],
    [t('models.detail.quant'), item.quantization || '—'],
    [t('models.detail.format'), item.format || '—'],
    [t('models.detail.architecture'), item.architecture || '—'],
    [t('models.detail.context'), item.contextLength ? String(item.contextLength) : '—'],
    [t('models.detail.embedding'), item.embeddingLength ? String(item.embeddingLength) : '—'],
    [t('models.detail.layers'), item.blockCount ? String(item.blockCount) : '—'],
    [t('models.detail.experts'), item.expertCount ? String(item.expertCount) : '—'],
    [t('models.detail.capabilities'), item.capabilities.length ? item.capabilities.join(', ') : '—'],
  ];
  if (item.loaded && item.vramBytes) rows.push([t('models.detail.vramNow'), formatBytes(item.vramBytes, i18n.language)]);
  if (stats.data?.weightBytes) rows.push([t('models.detail.weights'), formatBytes(stats.data.weightBytes, i18n.language)]);
  return (
    <div className="flex min-h-full flex-col">
      <div className="border-b px-3 py-2">
        <h2 className="min-w-0 break-all font-mono text-xs font-medium">{item.name}</h2>
      </div>
      <dl className="grid gap-2 p-3 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="min-w-0 break-words">{value}</dd>
          </div>
        ))}
        {item.hfUrl ? (
          <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-2">
            <dt className="text-muted-foreground">{t('models.detail.hf')}</dt>
            <dd><a className="text-primary underline" href={item.hfUrl} target="_blank" rel="noreferrer">{item.hfUrl.replace('https://', '')}</a></dd>
          </div>
        ) : null}
        {item.hasTemplate ? <p className="text-xs text-muted-foreground">{t('models.detail.template')}</p> : null}
        {item.license ? (
          <details>
            <summary className="cursor-pointer text-muted-foreground">{t('models.detail.license')}</summary>
            <p className="mt-1 whitespace-pre-wrap text-xs">{item.license}{item.licenseClipped ? '…' : ''}</p>
          </details>
        ) : null}
        {item.digest ? <p className="break-all font-mono text-xs text-muted-foreground">{item.digest}</p> : null}
        {stats.isFetching ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Spinner size="sm" label={t('app.loading')} />
            <span>{t('app.loading')}</span>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

function TagsEditor({
  open,
  item,
  suggestions,
  onClose,
}: {
  open: boolean;
  item: InstalledModel | null;
  suggestions: string[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<TagInputHandle>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open && item) setTags([...item.tags]);
  }, [open, item]);

  async function save() {
    if (!item) return;
    setBusy(true);
    try {
      await saveModelTags(item.name, inputRef.current?.commitDraft() ?? tags);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent closeLabel={t('models.dialog.close')}>
        <DialogHeader>
          <DialogTitle>{t('models.ribbon.tags')}</DialogTitle>
          <DialogDescription>{item?.name}</DialogDescription>
        </DialogHeader>
        <TagInput
          ref={inputRef}
          value={tags}
          onChange={setTags}
          suggestions={suggestions}
          placeholder={t('networks.tags.placeholder')}
          addLabel={t('networks.tags.add')}
          removeLabel={(tag) => t('networks.tags.remove', { tag })}
        />
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>{t('models.dialog.cancel')}</Button>
          <Button type="button" disabled={busy} loading={busy} onClick={() => void save()}>{t('models.dialog.save')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteModelDialog({
  open,
  items,
  onClose,
  onDeleted,
}: {
  open: boolean;
  items: InstalledModel[];
  onClose: () => void;
  onDeleted: (removed: string[]) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [blocks, setBlocks] = useState<{ name: string; usages: { kind: string; network?: string; node?: string }[] }[]>([]);
  const anyLoaded = items.some((item) => item.loaded);
  const blocked = blocks.length > 0;

  useEffect(() => {
    if (open) setBlocks([]);
  }, [open]);

  async function confirm() {
    if (items.length === 0) return;
    setBusy(true);
    const removed: string[] = [];
    const failed: { name: string; usages: { kind: string; network?: string; node?: string }[] }[] = [];
    try {
      for (const item of items) {
        try {
          await apiFetch('/models/delete', {
            method: 'POST',
            body: JSON.stringify({ name: item.name, unload: item.loaded }),
          });
          removed.push(item.name);
        } catch (caught) {
          if (caught instanceof ApiError && caught.messageKey === 'models.loaded') {
            try {
              await apiFetch('/models/delete', { method: 'POST', body: JSON.stringify({ name: item.name, unload: true }) });
              removed.push(item.name);
            } catch (again) {
              if (again instanceof ApiError && again.usages?.length) failed.push({ name: item.name, usages: again.usages });
              else throw again;
            }
            continue;
          }
          if (caught instanceof ApiError && caught.usages?.length) {
            failed.push({ name: item.name, usages: caught.usages });
            continue;
          }
          throw caught;
        }
      }
      await queryClient.invalidateQueries({ queryKey: ['models'] });
      onDeleted(removed);
      if (failed.length) setBlocks(failed);
      else onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent closeLabel={t('models.dialog.close')}>
        <DialogHeader>
          <DialogTitle>{blocked ? t('models.delete.inUseTitle') : t('models.delete.title')}</DialogTitle>
          <DialogDescription>
            {blocked
              ? t('models.delete.inUseBodyMany', { count: blocks.length })
              : items.length === 1
                ? t('models.delete.body', { name: items[0]?.name ?? '' })
                : t('models.delete.bodyMany', { count: items.length })}
          </DialogDescription>
        </DialogHeader>
        {blocked ? (
          <ul className="grid max-h-60 gap-3 overflow-auto text-sm">
            {blocks.map((block) => (
              <li key={block.name}>
                <p className="break-all font-mono text-xs">{block.name}</p>
                <ul className="mt-1 grid gap-1">
                  {block.usages.map((usage, index) => (
                    <li key={`${usage.kind}-${index}`}>{usageText(t, usage)}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        ) : null}
        {!blocked && anyLoaded ? <p className="text-sm">{t('models.delete.loaded')}</p> : null}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {blocked ? t('models.dialog.close') : t('models.dialog.cancel')}
          </Button>
          {blocked ? null : (
            <Button type="button" variant="destructive" disabled={busy || items.length === 0} loading={busy} onClick={() => void confirm()}>
              {t('models.ribbon.delete')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
