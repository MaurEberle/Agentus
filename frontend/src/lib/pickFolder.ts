import { getChromeHost } from '@/lib/chromeHost';

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

type FolderOpener = () => Promise<string | null>;

let opener: FolderOpener | null = null;

export function registerFolderPicker(fn: FolderOpener): () => void {
  opener = fn;
  return () => {
    if (opener === fn) opener = null;
  };
}

export async function fsPluginReady(): Promise<boolean> {
  try {
    const response = await fetch('/__agentus/fs?ready=1', { method: 'GET' });
    if (!response.ok) return false;
    const body = (await response.json()) as { ok?: boolean };
    return body.ok === true;
  } catch {
    return false;
  }
}

export async function fetchFolderRoots(): Promise<FsRoot[]> {
  const response = await fetch('/__agentus/fs?roots=1', { method: 'GET' });
  if (!response.ok) throw new Error('roots failed');
  const body = (await response.json()) as { roots?: FsRoot[] };
  return Array.isArray(body.roots) ? body.roots : [];
}

export async function fetchFolderList(path: string, signal?: AbortSignal): Promise<FsList> {
  const response = await fetch(`/__agentus/fs?path=${encodeURIComponent(path)}`, { method: 'GET', signal });
  if (!response.ok) throw new Error('list failed');
  return (await response.json()) as FsList;
}

export async function pickFolderPath(): Promise<string | null> {
  const host = getChromeHost();
  if (host?.pickFolder) return host.pickFolder();
  if (opener) return opener();
  return null;
}
