import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Folder, FolderUp, HardDrive, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  fetchFolderList,
  fetchFolderRoots,
  fsPluginReady,
  registerFolderPicker,
  type FsEntry,
  type FsRoot,
} from '@/lib/pickFolder';
import { cn } from '@/lib/utils';

type Pending = { resolve: (path: string | null) => void };

export function FolderPickerHost() {
  const [open, setOpen] = useState(false);
  const pendingRef = useRef<Pending | null>(null);

  useEffect(() => {
    return registerFolderPicker(
      () =>
        new Promise((resolve) => {
          pendingRef.current?.resolve(null);
          pendingRef.current = { resolve };
          setOpen(true);
        }),
    );
  }, []);

  function finish(path: string | null) {
    pendingRef.current?.resolve(path);
    pendingRef.current = null;
    setOpen(false);
  }

  return (
    <FolderPickerDialog
      open={open}
      onCancel={() => finish(null)}
      onSelect={(path) => finish(path)}
    />
  );
}

function FolderPickerDialog({
  open,
  onCancel,
  onSelect,
}: {
  open: boolean;
  onCancel: () => void;
  onSelect: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [roots, setRoots] = useState<FsRoot[]>([]);
  const [current, setCurrent] = useState('');
  const [parent, setParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<FsEntry[]>([]);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [pathDraft, setPathDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorKey, setErrorKey] = useState<'error' | 'unavailable' | null>(null);
  const loadGen = useRef(0);

  const chosen = pathDraft.trim() || highlighted || current;

  const loadDir = useCallback(async (path: string, isCancelled?: () => boolean) => {
    const gen = loadGen.current + 1;
    loadGen.current = gen;
    const stale = () => isCancelled?.() || loadGen.current !== gen;
    setLoading(true);
    setErrorKey(null);
    setHighlighted(null);
    try {
      const list = await fetchFolderList(path);
      if (stale()) return;
      setCurrent(list.path);
      setPathDraft(list.path);
      setParent(list.parent);
      setEntries(list.entries);
      if (list.error) setErrorKey('error');
    } catch {
      if (!stale()) setErrorKey('error');
    } finally {
      if (!stale()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setHighlighted(null);
    setEntries([]);
    setErrorKey(null);
    setLoading(true);
    void (async () => {
      const ready = await fsPluginReady();
      if (!ready) {
        if (!cancelled) {
          setLoading(false);
          setErrorKey('unavailable');
        }
        return;
      }
      try {
        const nextRoots = await fetchFolderRoots();
        if (cancelled) return;
        setRoots(nextRoots);
        const home = nextRoots.find((root) => root.id === 'home')?.path ?? nextRoots[0]?.path ?? '';
        if (home) await loadDir(home, () => cancelled);
        else {
          setCurrent('');
          setPathDraft('');
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setLoading(false);
          setErrorKey('unavailable');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadDir, open]);

  function confirm() {
    const path = chosen.trim();
    if (!path) return;
    onSelect(path);
  }

  function onPathKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    const next = pathDraft.trim();
    if (next) void loadDir(next);
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent closeLabel={t('folderPicker.close')} className="max-w-2xl gap-3">
        <DialogHeader>
          <DialogTitle>{t('folderPicker.title')}</DialogTitle>
          <DialogDescription>{t('folderPicker.description')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-1">
          {roots.map((root) => (
            <Button
              key={`${root.id}:${root.path}`}
              type="button"
              size="sm"
              variant={current.toLowerCase() === root.path.toLowerCase() ? 'secondary' : 'outline'}
              onClick={() => void loadDir(root.path)}
            >
              {root.id === 'drive' ? (
                <HardDrive className="size-3.5" />
              ) : root.id === 'home' ? (
                <Home className="size-3.5" />
              ) : (
                <Folder className="size-3.5" />
              )}
              {root.id === 'drive'
                ? `${root.letter}:`
                : t(`folderPicker.places.${root.id}`)}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            size="icon"
            variant="outline"
            disabled={!parent}
            aria-label={t('folderPicker.up')}
            onClick={() => parent && void loadDir(parent)}
          >
            <FolderUp className="size-4" />
          </Button>
          <Input
            value={pathDraft}
            aria-label={t('folderPicker.path')}
            spellCheck={false}
            autoComplete="off"
            className="font-mono text-xs"
            onChange={(event) => {
              setHighlighted(null);
              setPathDraft(event.target.value);
            }}
            onKeyDown={onPathKey}
            onBlur={() => {
              const next = pathDraft.trim();
              if (next && next !== current) void loadDir(next);
            }}
          />
        </div>
        <ScrollArea className="h-64 rounded-md border">
          {loading ? (
            <p className="p-3 text-sm text-muted-foreground">{t('folderPicker.loading')}</p>
          ) : errorKey && entries.length === 0 ? (
            <p className="p-3 text-sm text-destructive">{t(`folderPicker.${errorKey}`)}</p>
          ) : entries.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">{t('folderPicker.empty')}</p>
          ) : (
            <ul>
              {entries.map((entry) => (
                <li key={entry.path}>
                  <button
                    type="button"
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-accent',
                      highlighted === entry.path && 'bg-accent',
                    )}
                    onClick={() => {
                      setHighlighted(entry.path);
                      setPathDraft(entry.path);
                    }}
                    onDoubleClick={() => void loadDir(entry.path)}
                  >
                    <Folder className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate">{entry.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
        {errorKey && entries.length > 0 ? (
          <p className="text-sm text-destructive">{t(`folderPicker.${errorKey}`)}</p>
        ) : null}
        <p className="truncate font-mono text-xs text-muted-foreground" title={chosen}>
          {chosen || '—'}
        </p>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            {t('folderPicker.cancel')}
          </Button>
          <Button type="button" disabled={!chosen.trim()} onClick={confirm}>
            {t('folderPicker.select')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
