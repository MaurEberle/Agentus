import { useEffect, useRef } from 'react';
import { Download } from 'lucide-react';
import { Link, useMatch } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { queryClient } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { listDownloads } from '@/modules/models/api';

export function DownloadsHeader() {
  const { t } = useTranslation();
  const active = useMatch('/downloads');
  const seenDone = useRef(new Set<string>());
  const downloads = useQuery({
    queryKey: ['models', 'downloads'],
    queryFn: listDownloads,
    refetchInterval: 1500,
  });
  const items = downloads.data?.items ?? [];
  const count = items.filter((item) => item.status === 'queued' || item.status === 'running' || item.status === 'paused').length;

  useEffect(() => {
    const done = items.filter((item) => item.status === 'done').map((item) => item.id);
    const fresh = done.filter((id) => !seenDone.current.has(id));
    if (fresh.length > 0 && seenDone.current.size > 0) {
      void queryClient.invalidateQueries({ queryKey: ['models'], exact: true });
      void queryClient.invalidateQueries({ queryKey: ['models', 'hub', 'files'] });
    }
    for (const id of done) seenDone.current.add(id);
  }, [items]);

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="sm" asChild className={cn('relative', active && 'bg-accent text-accent-foreground')}>
            <Link to="/downloads" aria-label={t('models.downloads.title')} aria-current={active ? 'page' : undefined}>
              <Download className="size-4" />
              {count > 0 ? (
                <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
                  {count}
                </span>
              ) : null}
            </Link>
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t('models.downloads.title')}</TooltipContent>
      </Tooltip>
    </>
  );
}
