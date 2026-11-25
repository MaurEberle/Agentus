import { useEffect, useId, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { MarkdownView } from '@/components/MarkdownView';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import { PASSING_CARD_KEYS, useHubCardQuery } from '@/modules/models/api';
import { ExternalLink } from '@/modules/models/ModelDetailParts';
import type { HubCard } from '@/modules/models/model';

/** How much of a long card shows before "Ganz anzeigen". */
const PREVIEW_PX = 560;
/** Only cards clearly taller than the preview are cut; a little more just shows. */
const CUT_FROM_PX = 900;

/**
 * The description block of a model's detail view, on the hub and the installed tab alike: the
 * repo's own card, the base model's card when the repo names one (GGUF repos often carry a stub),
 * or, for an Ollama library model without a Hugging Face repo, where its description lives.
 */
export function ModelCards({
  repo,
  baseModel,
  libraryUrl,
  open,
  onToggle,
}: {
  repo?: string | null;
  /** Known from the repo's metadata (hub); otherwise read from the card's header. */
  baseModel?: string | null;
  /** The Ollama library page, for models without a card on Hugging Face. */
  libraryUrl?: string | null;
  open: { own: boolean; base: boolean };
  onToggle: (which: 'own' | 'base') => void;
}) {
  const { t } = useTranslation();
  const own = useHubCardQuery(repo, open.own);
  if (!repo) {
    if (!libraryUrl) return null;
    return (
      <section className="min-w-0 space-y-1.5 rounded-md border px-3 py-2 text-sm">
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{t('models.hub.card.title')}</h3>
        <p className="text-muted-foreground">{t('models.hub.card.library')}</p>
        <ExternalLink href={libraryUrl} />
      </section>
    );
  }
  const base = baseModel ?? own.data?.baseModel ?? null;
  return (
    <>
      <HubCardSection repo={repo} title={t('models.hub.card.title')} open={open.own} onToggle={() => onToggle('own')} />
      {base && base.toLowerCase() !== repo.toLowerCase() ? (
        <HubCardSection
          repo={base}
          title={t('models.hub.card.baseTitle')}
          subtitle={base}
          open={open.base}
          onToggle={() => onToggle('base')}
        />
      ) : null}
    </>
  );
}

/**
 * A repo's model card from the Hub, unfolded on demand: fetched only when open, once per hour,
 * shown as Markdown (the backend has turned the card's HTML into Markdown and resolved its links).
 */
export function HubCardSection({
  repo,
  title,
  subtitle,
  open,
  onToggle,
}: {
  repo: string;
  title: string;
  /** Shown next to the title, e.g. which base model the card belongs to. */
  subtitle?: string;
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const panelId = useId();
  const query = useHubCardQuery(repo, open);
  const card: HubCard | undefined = query.data;
  const [expanded, setExpanded] = useState(false);
  const [tall, setTall] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => setExpanded(false), [repo]);

  // Images load after the text and make the card taller; watch the real height.
  useEffect(() => {
    const element = contentRef.current;
    if (!element) {
      setTall(false);
      return undefined;
    }
    const measure = () => setTall(element.scrollHeight > CUT_FROM_PX);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [card?.markdown, open]);

  const passing = Boolean(card?.messageKey && PASSING_CARD_KEYS.has(card.messageKey));
  return (
    // min-w-0: wide code and tables scroll inside the card instead of widening the detail column.
    <section className="min-w-0 rounded-md border">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
          className="flex w-full min-w-0 items-center gap-2 rounded-md px-3 py-2 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          <ChevronRight className={cn('size-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} aria-hidden />
          <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</span>
          {subtitle ? <span className="min-w-0 truncate text-xs text-muted-foreground">{subtitle}</span> : null}
        </button>
      </h3>
      {open ? (
        <div id={panelId} className="min-w-0 border-t px-3 py-3">
          {query.isPending ? (
            <div className="flex justify-center py-4">
              <Spinner label={t('app.loading')} />
            </div>
          ) : query.isError || !card ? (
            <p className="text-sm text-muted-foreground">{t('models.hub.card.failed')}</p>
          ) : card.messageKey ? (
            <div className="grid justify-items-start gap-2 text-sm text-muted-foreground">
              <p>
                {t(card.messageKey, { defaultValue: t('models.hub.card.failed') })}
                {card.retryAfter ? ` ${t('models.hub.retryIn', { seconds: card.retryAfter })}` : ''}
              </p>
              {passing ? (
                <Button type="button" size="sm" variant="outline" loading={query.isFetching} onClick={() => void query.refetch()}>
                  {t('models.hub.retry')}
                </Button>
              ) : null}
              {card.url ? <ExternalLink href={card.url}>{t('models.hub.open')}</ExternalLink> : null}
            </div>
          ) : (
            <div className="grid grid-cols-[minmax(0,1fr)] gap-2">
              <div className={cn('relative', tall && !expanded && 'overflow-hidden')} style={tall && !expanded ? { maxHeight: PREVIEW_PX } : undefined}>
                <div ref={contentRef}>
                  <MarkdownView text={card.markdown} bare small />
                </div>
                {tall && !expanded ? (
                  <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-background to-transparent" aria-hidden />
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {tall ? (
                  <Button type="button" size="sm" variant="outline" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
                    {expanded ? t('models.hub.card.less') : t('models.hub.card.more')}
                  </Button>
                ) : null}
                {card.truncated ? <span className="text-xs text-muted-foreground">{t('models.hub.card.truncated')}</span> : null}
                <span className="text-xs">
                  <ExternalLink href={card.url}>{t('models.hub.open')}</ExternalLink>
                </span>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
