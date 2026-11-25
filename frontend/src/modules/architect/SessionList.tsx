import { Download, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { HOVER_CARD } from '@/components/hoverCard';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { SessionSummary } from '@/modules/architect/api';

/** What a session is about, on hover: like the model pickers' card, with what the row cuts off. */
function SessionHoverCard({ item, running }: { item: SessionSummary; running: boolean }) {
  const { t, i18n } = useTranslation();
  const readIn = item.readIn?.name
    ? item.readIn.purpose === 'change'
      ? t('architect.source.change', { name: item.readIn.name, version: item.readIn.version ?? '' })
      : t('architect.source.template', { name: item.readIn.name })
    : '';
  const applied = item.lastApplied?.name
    ? [
        t(item.lastApplied.mode === 'update' ? 'architect.sessions.card.updated' : 'architect.sessions.card.created', {
          name: item.lastApplied.name,
          version: item.lastApplied.version ?? '',
        }),
        item.lastApplied.undone ? t('architect.sessions.card.undone') : '',
      ]
        .filter(Boolean)
        .join(' · ')
    : '';
  const rows: [string, string][] = [
    [t('architect.sessions.card.state'), running ? t('architect.session.running') : t('architect.sessions.card.ended')],
    [
      t('architect.sessions.card.model'),
      [t(`providers.${item.provider}`, { defaultValue: item.provider }), item.model || t('architect.sessions.card.noModel')].join(' · '),
    ],
    [t('architect.sessions.card.started'), formatDateTime(item.createdAt, i18n.language)],
    [t('architect.sessions.card.active'), formatDateTime(item.updatedAt, i18n.language)],
    [t('architect.sessions.card.messages'), item.messageCount ? String(item.messageCount) : ''],
    [t('architect.sessions.card.goal'), item.goal ?? ''],
    [
      t('architect.sessions.card.draft'),
      item.draftName ? `${item.draftName} · ${t('architect.sessions.card.nodes', { count: item.draftNodes ?? 0 })}` : '',
    ],
    [t('architect.sessions.card.readIn'), readIn],
    [t('architect.sessions.card.applied'), applied],
  ];
  const shown = rows.filter(([, value]) => value);
  return (
    <div className="grid gap-1.5">
      <p className="break-words font-medium">{item.title || t('architect.sessions.untitled')}</p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5">
        {shown.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="text-muted-foreground">{key}</dt>
            <dd className="line-clamp-3 min-w-0 break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Earlier sessions; one is picked, the active one is marked. */
export function SessionList({
  sessions,
  selectedId,
  activeId,
  fresh,
  width,
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
  /** In px; the grip next to the list changes it. */
  width: number;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onExport: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  return (
    <aside className="flex min-h-0 shrink-0 flex-col border-r" style={{ width }}>
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <h2 className="truncate text-sm font-semibold">{t('architect.sessions.title')}</h2>
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
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="grid w-full gap-0.5 px-3 py-2 text-left"
                  aria-current={item.id === selectedId ? 'true' : undefined}
                  onClick={() => onSelect(item.id)}
                >
                  <span className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
                    {item.id === activeId ? <span className="size-2 shrink-0 rounded-full bg-primary" aria-label={t('architect.session.running')} /> : null}
                    <span className="truncate">{item.title || t('architect.sessions.untitled')}</span>
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {formatDateTime(item.updatedAt, i18n.language)}
                    {item.model ? ` · ${item.model}` : ''}
                  </span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" align="start" sideOffset={8} className={HOVER_CARD}>
                <SessionHoverCard item={item} running={item.id === activeId} />
              </TooltipContent>
            </Tooltip>
            {item.id === selectedId ? (
              <div className="flex flex-wrap gap-1 px-2 pb-2">
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
