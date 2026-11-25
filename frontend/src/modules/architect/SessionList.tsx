import { Download, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { SessionSummary } from '@/modules/architect/api';

/** Earlier sessions; one is picked, the active one is marked. */
export function SessionList({
  sessions,
  selectedId,
  activeId,
  fresh,
  onSelect,
  onNew,
  onDelete,
  onExport,
}: {
  sessions: SessionSummary[];
  selectedId: string | null;
  activeId: string | null;
  /** An empty chat from "Neu" that has no session yet; it heads the list. */
  fresh: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onExport: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  return (
    <aside className="flex min-h-0 w-60 shrink-0 flex-col border-r">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <h2 className="text-sm font-semibold">{t('architect.sessions.title')}</h2>
        <Button type="button" size="sm" variant="outline" onClick={onNew}>
          <Plus className="size-4" aria-hidden />
          {t('architect.sessions.new')}
        </Button>
      </div>
      <ul className="min-h-0 flex-1 overflow-auto">
        {fresh ? (
          <li className="border-b bg-accent px-3 py-2" aria-current="true">
            <span className="block text-sm font-medium">{t('architect.sessions.untitled')}</span>
            <span className="block text-xs text-muted-foreground">{t('architect.sessions.freshHint')}</span>
          </li>
        ) : null}
        {sessions.length === 0 && !fresh ? <li className="p-3 text-xs text-muted-foreground">{t('architect.sessions.empty')}</li> : null}
        {sessions.map((item) => (
          <li key={item.id} className={cn('group border-b', item.id === selectedId && 'bg-accent')}>
            <button type="button" className="grid w-full gap-0.5 px-3 py-2 text-left" onClick={() => onSelect(item.id)}>
              <span className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
                {item.id === activeId ? <span className="size-2 shrink-0 rounded-full bg-primary" aria-label={t('architect.session.running')} /> : null}
                <span className="truncate">{item.title || t('architect.sessions.untitled')}</span>
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {formatDateTime(item.updatedAt, i18n.language)}
                {item.model ? ` · ${item.model}` : ''}
              </span>
            </button>
            {item.id === selectedId ? (
              <div className="flex gap-1 px-2 pb-2">
                <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => onExport(item.id)}>
                  <Download className="size-3.5" aria-hidden />
                  {t('architect.sessions.export')}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                  onClick={() => onDelete(item.id)}
                >
                  <Trash2 className="size-3.5" aria-hidden />
                  {t('architect.sessions.delete')}
                </Button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </aside>
  );
}
