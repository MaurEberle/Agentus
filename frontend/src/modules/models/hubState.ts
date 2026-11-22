import type { DownloadJob, InstalledModel } from '@/modules/models/model';

/** Same comparison as Ollama and the backend (`tag_key`): case-insensitive, without ":latest". */
export function tagKey(name: string): string {
  const text = name.trim().toLowerCase();
  return text.endsWith(':latest') ? text.slice(0, -':latest'.length) : text;
}

/** Hugging Face repo of a pulled model: "hf.co/owner/repo:Q4_K_M" → "owner/repo", lower case. */
export function hubRepo(name: string): string | null {
  const match = /^(?:hf\.co|huggingface\.co)\/([^/:\s]+\/[^/:\s]+)(?::\S*)?$/i.exec(name.trim());
  return match ? match[1].toLowerCase() : null;
}

const ACTIVE_DOWNLOADS: ReadonlySet<string> = new Set(['running', 'queued', 'paused']);
// Which download a repo row shows when several quants of it are in the queue.
const DOWNLOAD_RANK: Record<string, number> = { running: 0, queued: 1, paused: 2 };

export function downloadPercent(job: DownloadJob): number | null {
  if (!job.total || job.total <= 0 || job.completed == null) return null;
  return Math.min(100, Math.floor((job.completed / job.total) * 100));
}

/** "Lädt 45 %", "Wartet", "Pausiert". */
export function downloadLabel(t: (key: string, vars?: Record<string, unknown>) => string, job: DownloadJob): string {
  const percent = job.status === 'running' ? downloadPercent(job) : null;
  if (percent != null) return t('models.hub.state.running', { percent });
  return t(`models.downloads.status.${job.status}`);
}

export type HubLocalState = {
  /** Tag keys of installed models, or null while the list is unknown. */
  installedKeys: Set<string> | null;
  /** Installed tags per Hugging Face repo. */
  installedByRepo: Map<string, string[]>;
  /** Queued, running or paused download per tag key. */
  downloadByKey: Map<string, DownloadJob>;
  /** The most active download per Hugging Face repo. */
  downloadByRepo: Map<string, DownloadJob>;
};

/** What is installed or downloading, for the hub list and the install button. */
export function hubLocalState(
  installed: { items: InstalledModel[]; messageKey?: string } | undefined,
  downloads: DownloadJob[] | undefined,
): HubLocalState {
  // A failed list (Ollama not reachable) is unknown, not empty.
  const known = installed && !installed.messageKey ? installed.items : null;
  const installedKeys = known ? new Set(known.map((item) => tagKey(item.name))) : null;
  const installedByRepo = new Map<string, string[]>();
  for (const item of known ?? []) {
    const repo = hubRepo(item.name);
    if (repo) installedByRepo.set(repo, [...(installedByRepo.get(repo) ?? []), item.name]);
  }
  const downloadByKey = new Map<string, DownloadJob>();
  const downloadByRepo = new Map<string, DownloadJob>();
  for (const job of downloads ?? []) {
    if (!ACTIVE_DOWNLOADS.has(job.status)) continue;
    downloadByKey.set(tagKey(job.model), job);
    const repo = hubRepo(job.model);
    if (!repo) continue;
    const shown = downloadByRepo.get(repo);
    if (!shown || DOWNLOAD_RANK[job.status] < DOWNLOAD_RANK[shown.status]) downloadByRepo.set(repo, job);
  }
  return { installedKeys, installedByRepo, downloadByKey, downloadByRepo };
}
