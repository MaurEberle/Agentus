import { MoreHorizontal } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import type { NetworkListItem } from '@/modules/dashboard/model';

export type LibraryRibbonHandlers = {
  onNew: () => void;
  onOpen: () => void;
  onDuplicate: () => void;
  onRename: () => void;
  onTags: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onImport: () => void;
  onExport: () => void;
  onRefresh: () => void;
};

export function LibraryRibbon({
  selected,
  busy,
  handlers,
}: {
  selected: NetworkListItem[];
  busy: boolean;
  handlers: LibraryRibbonHandlers;
}) {
  const { t } = useTranslation();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const n = selected.length;
  const one = n === 1 ? selected[0] : undefined;
  const canOpen = n === 1;
  const canDuplicate = n === 1;
  const canRename = n === 1;
  const canTags = n >= 1;
  const canActivate = Boolean(one && one.validationStatus === 'valid' && !one.isActive);
  const canDelete = n >= 1 && selected.some((item) => !item.isRunning);
  const canExport = n >= 1;

  const actions = [
    { key: 'new', label: t('networks.ribbon.new'), enabled: true, onClick: handlers.onNew },
    {
      key: 'open',
      label: t('networks.ribbon.open'),
      enabled: canOpen && !busy,
      hint: canOpen ? undefined : t('networks.ribbon.needOne'),
      onClick: handlers.onOpen,
    },
    {
      key: 'duplicate',
      label: t('networks.ribbon.duplicate'),
      enabled: canDuplicate && !busy,
      hint: canDuplicate ? undefined : t('networks.ribbon.needOne'),
      onClick: handlers.onDuplicate,
    },
    {
      key: 'rename',
      label: t('networks.ribbon.rename'),
      enabled: canRename && !busy,
      hint: canRename ? undefined : t('networks.ribbon.needOne'),
      onClick: handlers.onRename,
    },
    {
      key: 'tags',
      label: t('networks.ribbon.tags'),
      enabled: canTags && !busy,
      hint: canTags ? undefined : t('networks.ribbon.needSome'),
      onClick: handlers.onTags,
    },
    {
      key: 'activate',
      label: t('networks.ribbon.activate'),
      enabled: canActivate && !busy,
      hint: !one
        ? t('networks.ribbon.needOne')
        : one.isActive
          ? t('networks.ribbon.alreadyActive')
          : one.validationStatus !== 'valid'
            ? t('networks.ribbon.needValid')
            : undefined,
      onClick: handlers.onActivate,
    },
    {
      key: 'delete',
      label: t('networks.ribbon.delete'),
      enabled: canDelete && !busy,
      hint: n === 0 ? t('networks.ribbon.needSome') : canDelete ? undefined : t('networks.ribbon.runningBlocked'),
      onClick: handlers.onDelete,
    },
    { key: 'import', label: t('networks.ribbon.import'), enabled: !busy, onClick: handlers.onImport },
    {
      key: 'export',
      label: t('networks.ribbon.export'),
      enabled: canExport && !busy,
      hint: canExport ? undefined : t('networks.ribbon.needSome'),
      onClick: handlers.onExport,
    },
    { key: 'refresh', label: t('networks.ribbon.refresh'), enabled: !busy, onClick: handlers.onRefresh },
  ] as const;

  const compactKeys = new Set(['new', 'import', 'refresh']);
  const primary = actions.filter((action) => compactKeys.has(action.key));
  const rest = actions.filter((action) => !compactKeys.has(action.key));

  return (
    <div className="flex flex-wrap items-center gap-1 border-b bg-card px-2 py-1.5">
      <p className="mr-2 text-sm font-medium">{t('networks.title')}</p>
      {(isDesktop ? actions : primary).map(({ key, ...action }) => (
        <RibbonAction key={key} {...action} />
      ))}
      {!isDesktop ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" size="sm" variant="outline" aria-label={t('networks.ribbon.more')}>
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {rest.map((action) => (
              <DropdownMenuItem
                key={action.key}
                disabled={!action.enabled}
                onSelect={() => {
                  if (action.enabled) action.onClick();
                }}
              >
                {action.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </div>
  );
}

function RibbonAction({
  label,
  enabled,
  hint,
  onClick,
}: {
  label: string;
  enabled: boolean;
  hint?: string;
  onClick: () => void;
}) {
  const button = (
    <Button type="button" size="sm" variant="outline" disabled={!enabled} onClick={onClick}>
      {label}
    </Button>
  );
  if (!hint && enabled) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{button}</span>
      </TooltipTrigger>
      <TooltipContent>{hint ?? label}</TooltipContent>
    </Tooltip>
  );
}
