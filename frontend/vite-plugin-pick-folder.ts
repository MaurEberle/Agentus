import { accessSync, existsSync } from 'node:fs';
import { readdir, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join, parse, resolve } from 'node:path';
import type { IncomingMessage, ServerResponse } from 'node:http';
import type { Plugin } from 'vite';

export type FsRoot = {
  id: 'home' | 'desktop' | 'documents' | 'downloads' | 'drive';
  path: string;
  letter?: string;
};

export type FsEntry = { name: string; path: string };

export type FsList = {
  path: string;
  parent: string | null;
  entries: FsEntry[];
  error?: 'invalid' | 'denied' | 'not-dir';
};

function sendJson(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(body));
}

function requestUrl(req: IncomingMessage): URL {
  const raw = (req as IncomingMessage & { originalUrl?: string }).originalUrl ?? req.url ?? '/';
  return new URL(raw, 'http://127.0.0.1');
}

function normalizeDir(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const resolved = resolve(trimmed);
  if (!isAbsolute(resolved)) return null;
  return resolved;
}

function parentOf(dir: string): string | null {
  const root = parse(dir).root;
  if (root && dir.replace(/[\\/]+$/, '').toLowerCase() === root.replace(/[\\/]+$/, '').toLowerCase()) {
    return null;
  }
  const parent = dirname(dir);
  return parent === dir ? null : parent;
}

function existingDir(path: string): string | null {
  try {
    if (existsSync(path)) return path;
  } catch {
    return null;
  }
  return null;
}

export function listFsRoots(): { roots: FsRoot[] } {
  const home = homedir();
  const special: Array<{ id: FsRoot['id']; rel: string }> = [
    { id: 'home', rel: '' },
    { id: 'desktop', rel: 'Desktop' },
    { id: 'documents', rel: 'Documents' },
    { id: 'downloads', rel: 'Downloads' },
  ];
  const roots: FsRoot[] = [];
  for (const item of special) {
    const path = item.rel ? join(home, item.rel) : home;
    if (existingDir(path)) roots.push({ id: item.id, path });
  }
  for (let code = 67; code <= 90; code += 1) {
    const letter = String.fromCharCode(code);
    const path = `${letter}:\\`;
    try {
      accessSync(path);
      roots.push({ id: 'drive', path, letter });
    } catch {
      /* drive not present */
    }
  }
  return { roots };
}

export async function listFsDir(raw: string): Promise<FsList> {
  const path = normalizeDir(raw);
  if (!path) return { path: '', parent: null, entries: [], error: 'invalid' };
  const parent = parentOf(path);
  try {
    const info = await stat(path);
    if (!info.isDirectory()) return { path, parent, entries: [], error: 'not-dir' };
    const dirents = await readdir(path, { withFileTypes: true });
    const entries: FsEntry[] = [];
    for (const dirent of dirents) {
      if (dirent.name === '.' || dirent.name === '..') continue;
      const child = join(path, dirent.name);
      let isDir = dirent.isDirectory();
      if (!isDir && dirent.isSymbolicLink()) {
        try {
          isDir = (await stat(child)).isDirectory();
        } catch {
          isDir = false;
        }
      }
      if (!isDir) continue;
      entries.push({ name: dirent.name, path: child });
    }
    entries.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
    return { path, parent, entries };
  } catch {
    return { path, parent, entries: [], error: 'denied' };
  }
}

function handleRequest(req: IncomingMessage, res: ServerResponse, next: () => void) {
  const url = requestUrl(req);
  if (url.pathname !== '/__agentus/fs') {
    next();
    return;
  }
  if (req.method === 'GET' || req.method === 'HEAD') {
    if (url.searchParams.get('ready') === '1') {
      sendJson(res, 200, { ok: true });
      return;
    }
    if (url.searchParams.get('roots') === '1') {
      sendJson(res, 200, listFsRoots());
      return;
    }
    const path = url.searchParams.get('path') ?? '';
    void listFsDir(path).then((body) => sendJson(res, 200, body));
    return;
  }
  res.statusCode = 405;
  res.end();
}

export function pickFolderPlugin(): Plugin {
  return {
    name: 'agentus-pick-folder',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(handleRequest);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handleRequest);
    },
  };
}
