import { Fragment, type MouseEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { getChromeHost } from '@/lib/chromeHost';
import { cn } from '@/lib/utils';

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'code'; text: string }
  | { type: 'quote'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'hr' }
  | { type: 'table'; header: string[]; rows: string[][] };

const HEADING = ['text-2xl', 'text-xl', 'text-lg', 'text-base', 'text-sm', 'text-sm'] as const;
// Narrow places (the help chat) keep headings close to the body text.
const HEADING_SMALL = ['text-base', 'text-base', 'text-sm', 'text-sm', 'text-sm', 'text-sm'] as const;

function safeHref(value: string): string | null {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)) return trimmed;
  return null;
}

function isSpecial(text: string, index: number): boolean {
  const char = text[index];
  return char === '`' || char === '*' || char === '_' || char === '~' || char === '[' || char === '!';
}

const WORD = /[\p{L}\p{N}]/u;
const BARE_URL = /https?:\/\/[^\s<>"'`]+/y;

/** A bare https URL starting at ``index`` (not inside a word), without the sentence's punctuation. */
function urlAt(text: string, index: number): string | null {
  if (text[index] !== 'h' || (index > 0 && WORD.test(text[index - 1]))) return null;
  BARE_URL.lastIndex = index;
  const found = BARE_URL.exec(text);
  if (!found) return null;
  let url = found[0];
  while (/[.,;:!?)\]]$/.test(url)) {
    // A closing bracket stays when the URL opened one, as in Wikipedia links.
    if (url.endsWith(')') && (url.match(/\(/g)?.length ?? 0) >= (url.match(/\)/g)?.length ?? 0)) break;
    url = url.slice(0, -1);
  }
  return /^https?:\/\/[^/]/.test(url) ? url : null;
}

/** In the desktop window links open in the system browser; in a browser tab, in a new tab. */
function openLink(event: MouseEvent<HTMLAnchorElement>, href: string) {
  const openExternal = getChromeHost()?.openExternal;
  if (!openExternal) return;
  event.preventDefault();
  void openExternal(href);
}

function Anchor({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="break-words underline underline-offset-2"
      onClick={(event) => openLink(event, href)}
    >
      {children}
    </a>
  );
}

/** GitHub's note boxes ("> [!IMPORTANT]"), as model cards and READMEs use them. */
const CALLOUT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(?:\n|$)/i;
const CALLOUT_TONE: Record<string, string> = {
  note: 'border-primary/60 bg-primary/5',
  tip: 'border-primary/60 bg-primary/5',
  important: 'border-primary bg-primary/10',
  warning: 'border-warning bg-warning/10',
  caution: 'border-destructive bg-destructive/10',
};

/**
 * Where a run of ``mark`` (at ``index``) closes, or -1. Underscores inside a word, as in
 * ``writer_agent`` or ``file_access``, are text, not emphasis (CommonMark).
 */
function closing(text: string, index: number, mark: string): number {
  const underscore = mark[0] === '_';
  if (underscore && index > 0 && WORD.test(text[index - 1])) return -1;
  let end = text.indexOf(mark, index + mark.length);
  while (underscore && end > 0 && WORD.test(text[end + mark.length] ?? '')) {
    end = text.indexOf(mark, end + mark.length);
  }
  return end;
}

/** ``inLink``: text inside a link's label, where a bare URL must not become a second link. */
function renderInline(text: string, inLink = false): ReactNode[] {
  const out: ReactNode[] = [];
  let index = 0;
  let key = 0;
  while (index < text.length) {
    if (text.startsWith('**', index) || text.startsWith('__', index)) {
      const mark = text.slice(index, index + 2);
      const end = closing(text, index, mark);
      if (end > index + 2) {
        out.push(<strong key={key++}>{renderInline(text.slice(index + 2, end), inLink)}</strong>);
        index = end + 2;
        continue;
      }
    }
    if (text.startsWith('~~', index)) {
      const end = text.indexOf('~~', index + 2);
      if (end > index + 2) {
        out.push(<del key={key++}>{renderInline(text.slice(index + 2, end), inLink)}</del>);
        index = end + 2;
        continue;
      }
    }
    if (text[index] === '`') {
      const end = text.indexOf('`', index + 1);
      if (end > index) {
        out.push(
          <code key={key++} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
            {text.slice(index + 1, end)}
          </code>,
        );
        index = end + 1;
        continue;
      }
    }
    if ((text[index] === '*' || text[index] === '_') && text[index + 1] !== text[index]) {
      const mark = text[index];
      const end = closing(text, index, mark);
      if (end > index + 1) {
        out.push(<em key={key++}>{renderInline(text.slice(index + 1, end), inLink)}</em>);
        index = end + 1;
        continue;
      }
    }
    if (text[index] === '!' && text[index + 1] === '[') {
      const close = text.indexOf(']', index + 2);
      if (close > index && text[close + 1] === '(') {
        const urlEnd = text.indexOf(')', close + 2);
        const href = urlEnd > close + 2 ? safeHref(text.slice(close + 2, urlEnd)) : null;
        if (href) {
          const alt = text.slice(index + 2, close);
          out.push(
            <img key={key++} src={href} alt={alt} loading="lazy" referrerPolicy="no-referrer" className="my-2 inline-block max-w-full rounded-md" />,
          );
          index = urlEnd + 1;
          continue;
        }
      }
    }
    if (text[index] === '[') {
      const close = text.indexOf(']', index + 1);
      if (close > index && text[close + 1] === '(') {
        const urlEnd = text.indexOf(')', close + 2);
        const href = urlEnd > close + 2 ? safeHref(text.slice(close + 2, urlEnd)) : null;
        if (href) {
          out.push(
            <Anchor key={key++} href={href}>
              {renderInline(text.slice(index + 1, close), true)}
            </Anchor>,
          );
          index = urlEnd + 1;
          continue;
        }
      }
    }
    const bare = inLink ? null : urlAt(text, index);
    if (bare) {
      out.push(
        <Anchor key={key++} href={bare}>
          {bare}
        </Anchor>,
      );
      index += bare.length;
      continue;
    }
    const start = index;
    index += 1;
    while (index < text.length && !isSpecial(text, index) && (inLink || !urlAt(text, index))) index += 1;
    out.push(<Fragment key={key++}>{text.slice(start, index)}</Fragment>);
  }
  return out;
}

function isTableStart(lines: string[], index: number): boolean {
  const line = lines[index];
  const next = lines[index + 1];
  return Boolean(
    line?.trim().startsWith('|') &&
      next &&
      /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(next.trim()),
  );
}

function blockStart(lines: string[], index: number): boolean {
  const line = lines[index] ?? '';
  return (
    /^(```|~~~)/.test(line.trim()) ||
    /^(#{1,6})\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^[-*+]\s+/.test(line) ||
    /^\d+[.)]\s+/.test(line) ||
    /^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim()) ||
    isTableStart(lines, index)
  );
}

function cells(line: string): string[] {
  // "\|" is a pipe inside a cell, not a border.
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/(?<!\\)\|$/, '')
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

function parseBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const fence = /^(```|~~~)/.exec(line.trim());
    if (fence) {
      const mark = fence[1];
      const body: string[] = [];
      index += 1;
      while (index < lines.length && lines[index].trim() !== mark) {
        body.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: 'code', text: body.join('\n') });
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: heading[2].replace(/\s+#+\s*$/, '').trim(),
      });
      index += 1;
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim())) {
      blocks.push({ type: 'hr' });
      index += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'quote', text: quote.join('\n') });
      continue;
    }
    if (/^[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^[-*+]\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ul', items });
      continue;
    }
    if (/^\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+[.)]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\d+[.)]\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ol', items });
      continue;
    }
    if (isTableStart(lines, index)) {
      const header = cells(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        rows.push(cells(lines[index]));
        index += 1;
      }
      blocks.push({ type: 'table', header, rows });
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !blockStart(lines, index)) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraph.join('\n') });
  }
  return blocks;
}

function linesOf(text: string): ReactNode {
  return text.split('\n').map((part, index) => (
    <Fragment key={index}>
      {index > 0 ? <br /> : null}
      {renderInline(part)}
    </Fragment>
  ));
}

/** ``bare`` drops the framed box, for text that already sits in a bubble; ``small`` shrinks headings. */
export function MarkdownView({ text, bare = false, small = false }: { text: string; bare?: boolean; small?: boolean }) {
  const { t } = useTranslation();
  const blocks = parseBlocks(text);
  return (
    <div
      className={
        bare
          ? 'w-full min-w-0 space-y-2 break-words text-sm leading-6'
          : 'w-full min-w-0 space-y-3 rounded-md border bg-muted/30 p-4 text-sm leading-6'
      }
    >
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          const Tag = `h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
          return (
            <Tag key={index} className={`${(small ? HEADING_SMALL : HEADING)[block.level - 1]} font-semibold tracking-tight`}>
              {renderInline(block.text)}
            </Tag>
          );
        }
        if (block.type === 'code') {
          return (
            <pre key={index} className="overflow-auto rounded-md border bg-background p-3 font-mono text-xs leading-5">
              {block.text}
            </pre>
          );
        }
        if (block.type === 'quote') {
          const callout = CALLOUT.exec(block.text);
          if (callout) {
            const kind = callout[1].toLowerCase();
            return (
              <div key={index} role="note" className={cn('rounded-md border-s-4 px-3 py-2', CALLOUT_TONE[kind])}>
                <p className="text-xs font-semibold uppercase tracking-wide">{t(`markdown.callout.${kind}`)}</p>
                <div>{linesOf(block.text.slice(callout[0].length))}</div>
              </div>
            );
          }
          return (
            <blockquote key={index} className="border-s-2 ps-3 text-muted-foreground">
              {linesOf(block.text)}
            </blockquote>
          );
        }
        if (block.type === 'ul' || block.type === 'ol') {
          const Tag = block.type === 'ul' ? 'ul' : 'ol';
          return (
            <Tag key={index} className={block.type === 'ul' ? 'list-disc space-y-1 ps-5' : 'list-decimal space-y-1 ps-5'}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{linesOf(item)}</li>
              ))}
            </Tag>
          );
        }
        if (block.type === 'hr') return <hr key={index} className="border-border" />;
        if (block.type === 'table') {
          return (
            <div key={index} className="overflow-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr>
                    {block.header.map((cell, cellIndex) => (
                      <th key={cellIndex} className="border-b px-2 py-1 font-semibold">
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="border-b px-2 py-1 align-top">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={index}>{linesOf(block.text)}</p>;
      })}
    </div>
  );
}
