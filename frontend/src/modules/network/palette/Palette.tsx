import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { createNode } from '@/modules/network/schema/defaults';
import { PALETTE_TYPES } from '@/modules/network/schema/ports';
import type { NodeType } from '@/modules/network/model/document';
import { editorAddNode } from '@/modules/network/store';

const ICONS = {
  chat_input: MessageSquare,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
  knowledge: Database,
  router: GitFork,
  end: CircleStop,
};

export function Palette({
  disabled,
  insertAt,
  compact,
}: {
  disabled?: boolean;
  insertAt: () => { x: number; y: number };
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const types = useMemo(
    () =>
      PALETTE_TYPES.filter((type) => {
        const hay = `${t(`network.palette.${type}`)} ${t(`network.palette.${type}Hint`)} ${type}`.toLowerCase();
        return hay.includes(query.trim().toLowerCase());
      }),
    [query, t],
  );

  function insert(type: NodeType) {
    if (disabled) return;
    editorAddNode(createNode(type, insertAt(), true));
  }

  const items = compact ? PALETTE_TYPES : types;

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      {compact ? null : (
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('network.palette.search')}
          aria-label={t('network.palette.search')}
        />
      )}
      <ul className={compact ? 'flex min-h-0 flex-1 flex-col items-center gap-1 overflow-auto' : 'min-h-0 flex-1 space-y-1 overflow-auto'}>
        {items.map((type) => {
          const Icon = ICONS[type];
          return (
            <li key={type}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    disabled={disabled}
                    draggable={!disabled}
                    aria-label={t(`network.palette.${type}`)}
                    onDragStart={(event) => {
                      event.dataTransfer.setData('application/agentus-node', type);
                      event.dataTransfer.effectAllowed = 'move';
                    }}
                    onClick={() => insert(type)}
                    className={
                      compact
                        ? 'flex size-8 items-center justify-center rounded-md hover:bg-accent disabled:opacity-50'
                        : 'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent disabled:opacity-50'
                    }
                  >
                    <Icon className="size-4 text-primary" />
                    {compact ? null : t(`network.palette.${type}`)}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {compact ? t(`network.palette.${type}`) : t(`network.palette.${type}Hint`)}
                </TooltipContent>
              </Tooltip>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
