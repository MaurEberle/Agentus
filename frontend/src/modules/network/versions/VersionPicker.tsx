import { useRef, useState, type KeyboardEvent } from 'react';
import { ChevronsUpDown, History, Pin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { VersionSource } from '@/modules/network/versions/VersionParts';
import { versionStamp } from '@/modules/network/versions/versionActions';
import { useNetworkVersionsQuery } from '@/modules/network/versions/api';
import { useVersionPreview } from '@/modules/network/versions/previewStore';

/**
 * The inspector's version field: shows which version the editor shows and switches between them.
 * Picking an older version opens a read-only preview; the working document stays as it is.
 */
export function VersionPicker({ networkId }: { networkId: string }) {
  const { t, i18n } = useTranslation();
  const list = useNetworkVersionsQuery(networkId, true);
  const preview = useVersionPreview((state) => state.preview);
  const setPreview = useVersionPreview((state) => state.setPreview);
  const setDialogOpen = useVersionPreview((state) => state.setDialogOpen);
  const [open, setOpen] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const current = list.data?.version ?? null;
  const previewing = preview?.networkId === networkId ? preview.version : null;
  const shown = previewing ?? current;
  const items = list.data?.items ?? [];

  function pick(version: number) {
    setOpen(false);
    setPreview(networkId, version === current ? null : version);
  }

  function onListKey(event: KeyboardEvent<HTMLUListElement>) {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return;
    const options = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
    if (options.length === 0) return;
    event.preventDefault();
    const index = options.indexOf(document.activeElement as HTMLButtonElement);
    const next =
      event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : event.key === 'ArrowDown' ? Math.min(options.length - 1, index + 1) : Math.max(0, index - 1);
    options[next]?.focus();
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className="w-full justify-between gap-2 font-normal"
          aria-label={t('network.versions.picker')}
          disabled={!list.data}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate">{shown ? t('network.versions.version', { version: shown }) : t('network.versions.loading')}</span>
            {previewing ? (
              <Badge variant="warning" className="px-1.5 py-0 text-[10px]">{t('network.versions.previewBadge')}</Badge>
            ) : shown ? (
              <Badge className="px-1.5 py-0 text-[10px]">{t('network.versions.current')}</Badge>
            ) : null}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-60" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] min-w-72 p-1"
        onOpenAutoFocus={(event) => {
          // Focus the shown version, not the first row.
          event.preventDefault();
          listRef.current?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus();
        }}
      >
        <ul ref={listRef} role="listbox" aria-label={t('network.versions.list')} className="max-h-72 overflow-y-auto" onKeyDown={onListKey}>
          {items.map((item) => (
            <li key={item.version}>
              <button
                type="button"
                role="option"
                aria-selected={item.version === shown}
                className={cn(
                  'w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none',
                  item.version === shown && 'bg-primary/10',
                )}
                onClick={() => pick(item.version)}
              >
                <span className="flex items-center gap-1.5">
                  <span className="font-medium">{t('network.versions.version', { version: item.version })}</span>
                  {item.version === current ? (
                    <Badge className="px-1.5 py-0 text-[10px]">{t('network.versions.current')}</Badge>
                  ) : null}
                  {item.pinned ? (
                    <Pin className="ms-auto size-3.5 fill-current text-primary" aria-label={t('network.versions.pinned')} />
                  ) : null}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {versionStamp(item.updatedAt, i18n.language)} · <VersionSource item={item} />
                </span>
                {item.note ? <span className="block truncate text-xs">{item.note}</span> : null}
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-1 border-t pt-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full justify-start"
            onClick={() => {
              setOpen(false);
              setDialogOpen(true);
            }}
          >
            <History className="size-3.5" aria-hidden />
            {t('network.versions.manage')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
