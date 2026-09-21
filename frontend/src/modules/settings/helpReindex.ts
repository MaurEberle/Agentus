import { useEffect, useSyncExternalStore } from 'react';
import i18n from '@/i18n';
import { notify } from '@/lib/notifications';
import {
  reindexHelpChat,
  reindexHelpChatStatus,
  type HelpReindexResult,
} from '@/modules/settings/api';

type Phase = 'idle' | 'running';

let phase: Phase = 'idle';
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return phase === 'running';
}

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function report(result: HelpReindexResult) {
  const failed = result.state !== 'ready';
  const reported = result.messageKey;
  notify({
    titleKey:
      !failed
        ? 'settings.notify.reindexed'
        : reported && i18n.exists(reported)
          ? reported
          : 'help.index.failed',
    variant: failed ? 'error' : 'success',
  });
}

async function poll(jobId: string | undefined) {
  const deadline = Date.now() + 30 * 60 * 1000;
  while (Date.now() < deadline) {
    await sleep(1500);
    let status: HelpReindexResult;
    try {
      status = await reindexHelpChatStatus();
    } catch {
      continue;
    }
    if (jobId && status.id && status.id !== jobId) continue;
    if (!jobId && status.state === 'running' && status.id) jobId = status.id;
    if (status.state === 'running' || status.state === 'idle') continue;
    report(status);
    return;
  }
  notify({ titleKey: 'help.index.failed', variant: 'error' });
}

async function run(start: boolean) {
  try {
    if (!start) {
      const current = await reindexHelpChatStatus();
      if (current.state !== 'running') return;
      await poll(current.id);
      return;
    }
    const started = await reindexHelpChat();
    if (started.state !== 'running') {
      report(started);
      return;
    }
    await poll(started.id);
  } catch {
    let sawRunning = false;
    let jobId: string | undefined;
    for (let attempt = 0; attempt < 8 && !sawRunning; attempt += 1) {
      await sleep(1000);
      try {
        const status = await reindexHelpChatStatus();
        if (status.state === 'running') {
          sawRunning = true;
          jobId = status.id;
        }
      } catch {
        continue;
      }
    }
    if (!sawRunning) {
      notify({ titleKey: 'help.index.failed', variant: 'error' });
      return;
    }
    await poll(jobId);
  } finally {
    phase = 'idle';
    emit();
  }
}

function track(start: boolean) {
  if (phase === 'running') return;
  phase = 'running';
  emit();
  void run(start);
}

export function startHelpReindex() {
  track(true);
}

export function useHelpReindexRunning() {
  const running = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  useEffect(() => {
    void reindexHelpChatStatus()
      .then((status) => {
        if (status.state === 'running') track(false);
      })
      .catch(() => undefined);
  }, []);
  return running;
}
