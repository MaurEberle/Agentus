export interface PromptListItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface PromptDetail extends PromptListItem {
  body: string;
}

export interface PromptDraft {
  name: string;
  description: string;
  tags: string[];
  body: string;
}

export interface PromptFile {
  fileName: string;
  ok: boolean;
  draft?: PromptDraft;
}

function asDraft(name: string, description: string, body: string, tags: string[] = []): PromptDraft | null {
  const trimmed = name.trim();
  if (!trimmed || !body.trim()) return null;
  return { name: trimmed, description: description.trim(), tags, body: body.trim() };
}

function tagsOf(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
}

export function parseAgentusPrompt(fileName: string, value: unknown): PromptFile[] {
  if (!value || typeof value !== 'object') return [{ fileName, ok: false }];
  const record = value as Record<string, unknown>;
  const many = Array.isArray(record.items) ? record.items : null;
  if (many) {
    return many.flatMap((item, index) => parseAgentusPrompt(`${fileName}#${index + 1}`, item));
  }
  if (typeof record.body !== 'string' || typeof record.name !== 'string') return [{ fileName, ok: false }];
  const draft = asDraft(record.name, typeof record.description === 'string' ? record.description : '', record.body, tagsOf(record.tags));
  return draft ? [{ fileName, ok: true, draft }] : [{ fileName, ok: false }];
}

export function parsePrompty(fileName: string, text: string): PromptFile {
  const source = text.replace(/^\uFEFF/, '');
  let body = source;
  let name = fileName.replace(/\.prompty$/i, '').split(/[\\/]/).pop() || 'Prompt';
  let description = '';
  if (source.startsWith('---')) {
    const end = source.indexOf('\n---', 3);
    if (end < 0) return { fileName, ok: false };
    const front = source.slice(3, end);
    body = source.slice(end + 4).replace(/^\r?\n/, '');
    for (const line of front.split(/\r?\n/)) {
      const match = /^(name|description):\s*(.*)$/.exec(line.trim());
      if (!match) continue;
      const value = match[2].replace(/^["']|["']$/g, '').trim();
      if (match[1] === 'name' && value) name = value;
      if (match[1] === 'description') description = value;
    }
  }
  const draft = asDraft(name, description, body);
  return draft ? { fileName, ok: true, draft } : { fileName, ok: false };
}

export function parseFabric(fileName: string, text: string): PromptFile {
  const parts = fileName.split(/[\\/]/).filter(Boolean);
  const systemIndex = parts.lastIndexOf('system.md');
  const folder = systemIndex > 0 ? parts[systemIndex - 1] : parts[0] || 'Fabric';
  const draft = asDraft(folder, '', text);
  return draft ? { fileName, ok: true, draft } : { fileName, ok: false };
}

export function parsePromptFile(fileName: string, text: string): PromptFile[] {
  const lower = fileName.toLowerCase();
  if (lower.endsWith('system.md')) return [parseFabric(fileName, text)];
  if (lower.endsWith('.prompty')) return [parsePrompty(fileName, text)];
  if (lower.endsWith('.json')) {
    try {
      return parseAgentusPrompt(fileName, JSON.parse(text) as unknown);
    } catch {
      return [{ fileName, ok: false }];
    }
  }
  return [{ fileName, ok: false }];
}
