import { Fragment, type ReactNode } from 'react';

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

function safeHref(value: string): string | null {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)) return trimmed;
  return null;
}

function isSpecial(text: string, index: number): boolean {
  const char = text[index];
  return char === '`' || char === '*' || char === '_' || char === '~' || char === '[' || char === '!';
}

function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let index = 0;
  let key = 0;
  while (index < text.length) {
    if (text.startsWith('**', index) || text.startsWith('__', index)) {
      const mark = text.slice(index, index + 2);
      const end = text.indexOf(mark, index + 2);
      if (end > index + 2) {
        out.push(<strong key={key++}>{renderInline(text.slice(index + 2, end))}</strong>);
        index = end + 2;
        continue;
      }
    }
    if (text.startsWith('~~', index)) {
      const end = text.indexOf('~~', index + 2);
      if (end > index + 2) {
        out.push(<del key={key++}>{renderInline(text.slice(index + 2, end))}</del>);
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
      const end = text.indexOf(mark, index + 1);
      if (end > index + 1) {
        out.push(<em key={key++}>{renderInline(text.slice(index + 1, end))}</em>);
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
          out.push(<img key={key++} src={href} alt={alt} className="my-2 max-w-full rounded-md" />);
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
            <a key={key++} href={href} target="_blank" rel="noreferrer noopener" className="underline underline-offset-2">
              {renderInline(text.slice(index + 1, close))}
            </a>,
          );
          index = urlEnd + 1;
          continue;
        }
      }
    }
    const start = index;
    index += 1;
    while (index < text.length && !isSpecial(text, index)) index += 1;
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
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
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

export function MarkdownView({ text }: { text: string }) {
  const blocks = parseBlocks(text);
  return (
    <div className="w-full min-w-0 space-y-3 rounded-md border bg-muted/30 p-4 text-sm leading-6">
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          const Tag = `h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
          return (
            <Tag key={index} className={`${HEADING[block.level - 1]} font-semibold tracking-tight`}>
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
