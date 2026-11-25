import { useEffect, useState, type ReactNode } from 'react';
import { ChevronRight, ChevronsDownUp, ChevronsUpDown, Pencil } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { MarkdownView } from '@/components/MarkdownView';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/api/client';
import { notify } from '@/lib/notifications';
import { cn } from '@/lib/utils';
import { BRIEF_FIELDS, type Brief, type BriefField, type Draft } from '@/modules/architect/api';
import { useArchitectUi } from '@/modules/architect/store';

/** How a field shows when open: prose as Markdown, short values as plain text. */
type FieldView = 'markdown' | 'text';
const VIEW: Record<BriefField, FieldView> = {
  goal: 'markdown',
  input: 'markdown',
  output: 'markdown',
  sources: 'markdown',
  deployment: 'text',
  tools: 'markdown',
  constraints: 'markdown',
};

/** The backend keeps 1000 characters per field. */
const MAX_FIELD = 1000;

/** One line for the closed entry: the text without Markdown marks. */
function previewOf(value: string): string {
  return value
    .replace(/\*\*|`/g, '')
    .replace(/^\s*(#{1,6}|>|[-*+]|\d+[.)])\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function Entry({
  id,
  label,
  labelClassName,
  preview,
  meta,
  open,
  onToggle,
  children,
}: {
  id: string;
  label: ReactNode;
  labelClassName?: string;
  preview: ReactNode;
  meta?: ReactNode;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const headerId = `brief-${id}-header`;
  const panelId = `brief-${id}-panel`;
  return (
    <li className="border-b last:border-b-0">
      <h3>
        <button
          id={headerId}
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
          className="flex w-full min-w-0 items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          <ChevronRight className={cn('size-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')} aria-hidden />
          <span className={cn('shrink-0 truncate text-muted-foreground', labelClassName ?? 'w-24')}>{label}</span>
          <span className={cn('min-w-0 flex-1 truncate', open && 'invisible')}>{preview}</span>
          {meta ? <span className="shrink-0 text-xs text-muted-foreground">{meta}</span> : null}
        </button>
      </h3>
      {open ? (
        <div id={panelId} role="region" aria-labelledby={headerId} className="pb-3 pe-3 ps-[2.125rem]">
          {children}
        </div>
      ) : null}
    </li>
  );
}

function FieldBody({
  field,
  value,
  editable,
  onSave,
}: {
  field: BriefField;
  value: string;
  editable: boolean;
  onSave: (field: BriefField, value: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const label = t(`architect.brief.${field}`);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!editing) setText(value);
  }, [value, editing]);

  async function save() {
    const next = text.trim();
    if (next === value.trim()) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(field, next);
      setEditing(false);
    } catch (caught) {
      const key = caught instanceof ApiError ? caught.messageKey : undefined;
      notify({ titleKey: key === 'architect.busy' ? 'architect.busy' : 'architect.brief.saveFailed', variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="grid gap-2">
        <Textarea
          autoFocus
          value={text}
          maxLength={MAX_FIELD}
          rows={Math.min(12, Math.max(3, text.split('\n').length + 1))}
          className="min-h-0"
          aria-label={label}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              void save();
            } else if (event.key === 'Escape') {
              event.preventDefault();
              event.stopPropagation();
              setEditing(false);
            }
          }}
        />
        <div className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 text-xs text-muted-foreground">{t('architect.brief.editHint')}</span>
          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
            {t('architect.brief.cancel')}
          </Button>
          <Button type="button" size="sm" loading={saving} disabled={!editable} onClick={() => void save()}>
            {t('architect.brief.save')}
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="relative pe-8">
      {value ? (
        VIEW[field] === 'markdown' ? (
          <MarkdownView text={value} bare small />
        ) : (
          <p className="whitespace-pre-wrap break-words text-sm leading-6">{value}</p>
        )
      ) : (
        <p className="text-sm text-muted-foreground">{t('architect.brief.none')}</p>
      )}
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="absolute end-0 top-0 size-7"
        disabled={!editable}
        aria-label={t('architect.brief.edit', { field: label })}
        title={t('architect.brief.edit', { field: label })}
        onClick={() => setEditing(true)}
      >
        <Pencil className="size-3.5" aria-hidden />
      </Button>
    </div>
  );
}

/**
 * E-9: the brief the architect fills in conversation, one accordion entry per field; every field
 * can be edited directly. Below it the prompts the draft gives its agents, read as Markdown.
 */
export function BriefPanel({
  brief,
  draft,
  editable,
  onSave,
}: {
  brief: Brief;
  draft: Draft | null;
  /** False while the architect answers: its turn would overwrite the edit. */
  editable: boolean;
  /** Saves one field; an empty chat gets its session first. */
  onSave: (field: BriefField, value: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const openIds = useArchitectUi((state) => state.briefOpen);
  const setOpenIds = useArchitectUi((state) => state.setBriefOpen);

  const prompts = (draft?.nodes ?? [])
    .map((node) => ({ node, text: typeof node.data?.systemPrompt === 'string' ? node.data.systemPrompt.trim() : '' }))
    .filter((item) => item.text);
  const ids = [...BRIEF_FIELDS, ...prompts.map((item) => `prompt:${item.node.ref}`)];
  const allOpen = ids.every((id) => openIds.includes(id));
  const filled = BRIEF_FIELDS.filter((field) => (brief[field] ?? '').trim()).length;

  function toggle(id: string) {
    setOpenIds(openIds.includes(id) ? openIds.filter((item) => item !== id) : [...openIds, id]);
  }

  return (
    <section className="flex max-h-[50%] min-h-0 shrink-0 flex-col" aria-label={t('architect.brief.title')}>
      <div className="flex items-center gap-2 px-3 pb-1 pt-2">
        <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{t('architect.brief.title')}</h2>
        <span className="text-[11px] text-muted-foreground">{t('architect.brief.filled', { count: filled, total: BRIEF_FIELDS.length })}</span>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="ms-auto size-6"
          aria-label={allOpen ? t('architect.brief.collapseAll') : t('architect.brief.expandAll')}
          title={allOpen ? t('architect.brief.collapseAll') : t('architect.brief.expandAll')}
          onClick={() => setOpenIds(allOpen ? [] : ids)}
        >
          {allOpen ? <ChevronsDownUp className="size-3.5" aria-hidden /> : <ChevronsUpDown className="size-3.5" aria-hidden />}
        </Button>
      </div>
      <div className="min-h-0 overflow-y-auto">
        {filled === 0 ? <p className="px-3 pb-2 text-xs text-muted-foreground">{t('architect.brief.empty')}</p> : null}
        <ul className="border-t">
          {BRIEF_FIELDS.map((field) => {
            const value = brief[field] ?? '';
            return (
              <Entry
                key={field}
                id={field}
                label={t(`architect.brief.${field}`)}
                preview={value ? previewOf(value) : <span className="text-muted-foreground">—</span>}
                open={openIds.includes(field)}
                onToggle={() => toggle(field)}
              >
                <FieldBody field={field} value={value} editable={editable} onSave={onSave} />
              </Entry>
            );
          })}
        </ul>
        {prompts.length > 0 ? (
          <>
            <h2 className="border-t px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {t('architect.brief.prompts')}
            </h2>
            <ul className="border-t">
              {prompts.map(({ node, text }) => {
                const id = `prompt:${node.ref}`;
                const name = String(node.data.displayName || node.ref);
                return (
                  <Entry
                    key={id}
                    id={id.replace(/[^\w-]/g, '-')}
                    label={name}
                    labelClassName="max-w-[45%] font-medium text-foreground"
                    preview={<span className="text-muted-foreground">{t(`network.palette.${node.type}`, { defaultValue: node.type })}</span>}
                    meta={t('architect.brief.chars', { count: text.length })}
                    open={openIds.includes(id)}
                    onToggle={() => toggle(id)}
                  >
                    <div className="grid gap-1">
                      <div className="max-h-80 overflow-y-auto rounded-md border bg-muted/30 px-3 py-2">
                        <MarkdownView text={text} bare small />
                      </div>
                      <p className="text-xs text-muted-foreground">{t('architect.brief.promptHint')}</p>
                    </div>
                  </Entry>
                );
              })}
            </ul>
          </>
        ) : null}
      </div>
    </section>
  );
}
