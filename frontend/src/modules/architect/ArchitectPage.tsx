import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ApiError, apiFetch, queryClient } from '@/api/client';
import { notify } from '@/lib/notifications';
import { saveExportFile } from '@/lib/saveFile';
import {
  architectKeys,
  createSession,
  deleteSession,
  dismissProposal,
  exportSession,
  loadNetwork,
  patchSession,
  refreshArchitect,
  sendMessage,
  startSession,
  stopSession,
  StartRefused,
  undoSession,
  useArchitectStatusQuery,
  useSessionQuery,
  useSessionsQuery,
  type ArchitectMessage,
  type ArchitectState,
  type BriefField,
  type LoadPurpose,
  type SessionDetail,
} from '@/modules/architect/api';
import { BriefPanel } from '@/modules/architect/BriefPanel';
import { ChatPane, type LiveTool } from '@/modules/architect/ChatPane';
import { ClosingDialog } from '@/modules/architect/ClosingDialog';
import { DraftPanel } from '@/modules/architect/DraftPanel';
import { LoadNetworkDialog } from '@/modules/architect/LoadNetworkDialog';
import { ProposalCard } from '@/modules/architect/ProposalCard';
import { ModelBar } from '@/modules/architect/ModelBar';
import { SessionList } from '@/modules/architect/SessionList';
import { StartDialog } from '@/modules/architect/StartDialog';
import { SESSIONS_WIDTH, useArchitectUi, type ModelPick } from '@/modules/architect/store';
import { WidthGrip } from '@/modules/monitoring/PaneGrips';

type Refusal = { refused: StartRefused; pick: ModelPick; sessionId: string };

export function ArchitectPage() {
  const { t } = useTranslation();
  const selectedId = useArchitectUi((state) => state.selectedId);
  const fresh = useArchitectUi((state) => state.fresh);
  const select = useArchitectUi((state) => state.select);
  const startNew = useArchitectUi((state) => state.startNew);
  const share = useArchitectUi((state) => state.share);
  const setShare = useArchitectUi((state) => state.setShare);
  const sessionsWidth = useArchitectUi((state) => state.sessionsWidth);
  const setSessionsWidth = useArchitectUi((state) => state.setSessionsWidth);
  const pageRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState(1200);

  // The session list's grip turns its share of the page into px.
  useEffect(() => {
    const element = pageRef.current;
    if (!element) return undefined;
    const measure = () => setPageWidth(Math.max(1, element.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const pick = useArchitectUi((state) => state.pick);
  const setPick = useArchitectUi((state) => state.setPick);
  const status = useArchitectStatusQuery();
  const sessions = useSessionsQuery();
  const detail = useSessionQuery(selectedId);
  const activeId = status.data?.active?.sessionId ?? null;
  const sessionActive = Boolean(selectedId && activeId === selectedId);

  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState('');
  const [liveTools, setLiveTools] = useState<LiveTool[]>([]);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [closingOpen, setClosingOpen] = useState(false);
  const [loadOpen, setLoadOpen] = useState(false);
  const [workBusy, setWorkBusy] = useState<'load' | 'undo' | 'dismiss' | null>(null);
  const handle = useRef<{ abort: () => void } | null>(null);

  // Open the running session, else the latest one; an empty chat from "Neu" stays empty.
  useEffect(() => {
    if (selectedId || fresh || !sessions.data) return;
    const next = activeId ?? sessions.data[0]?.id ?? null;
    if (next) select(next);
  }, [selectedId, fresh, activeId, sessions.data, select]);

  // A picked session brings its model into the bar.
  const picked = detail.data;
  useEffect(() => {
    if (!picked) return;
    setPick({ provider: picked.provider, model: picked.model, credentialId: picked.credentialId ?? null });
  }, [picked?.id, setPick]); // eslint-disable-line react-hooks/exhaustive-deps

  /** The picked session, or a new one for the empty chat (read in or brief before the start). */
  async function ensureSession(model: ModelPick | null = pick): Promise<string> {
    if (selectedId) return selectedId;
    const created = await createSession({
      provider: model?.provider || 'ollama',
      model: model?.model ?? '',
      credentialId: model?.credentialId ?? null,
    });
    select(created.id);
    return created.id;
  }

  /** ``target`` null starts a new session; "Neu" passes it because the selection has not caught up yet. */
  async function start(
    model: ModelPick,
    options: { forceSlow?: boolean; confirmRunning?: boolean } = {},
    target: string | null = selectedId,
  ) {
    setBusy(true);
    setError(null);
    let id = target;
    try {
      if (!id) {
        const created = await createSession({ provider: model.provider, model: model.model, credentialId: model.credentialId });
        id = created.id;
        select(id);
      }
      await startSession(id, { provider: model.provider, model: model.model, credentialId: model.credentialId, ...options });
      setRefusal(null);
    } catch (caught) {
      if (caught instanceof StartRefused && id) setRefusal({ refused: caught, pick: model, sessionId: id });
      else setError('architect.failed');
    } finally {
      setBusy(false);
    }
  }

  /**
   * "Neu": an empty chat. While a session runs, the new one starts right away on the same model,
   * which stays loaded; otherwise the user picks a model and starts (or reads a network in first).
   */
  function newChat() {
    if (sending || busy) return;
    const current = picked;
    const untouched =
      current && current.messages.length === 0 && !current.draft && !current.source && Object.keys(current.brief ?? {}).length === 0;
    if (fresh || (untouched && (!activeId || activeId === current.id))) return;
    setError(null);
    startNew();
    const running = activeId ? (sessions.data ?? []).find((item) => item.id === activeId) : undefined;
    if (running?.model) {
      void start({ provider: running.provider, model: running.model, credentialId: running.credentialId ?? null }, {}, null);
    }
  }

  async function saveBrief(field: BriefField, value: string) {
    const id = await ensureSession();
    const brief = queryClient.getQueryData<SessionDetail>(architectKeys.session(id))?.brief ?? picked?.brief ?? {};
    await patchSession(id, { brief: { ...brief, [field]: value } });
  }

  async function stop() {
    if (!selectedId) return;
    setBusy(true);
    try {
      handle.current?.abort();
      await stopSession(selectedId);
    } finally {
      setBusy(false);
    }
  }

  function finish() {
    setSending(false);
    setPendingUser(null);
    setStreaming('');
    setLiveTools([]);
    handle.current = null;
  }

  function send(text: string) {
    if (!selectedId) return;
    const id = selectedId;
    setSending(true);
    setStreaming('');
    setLiveTools([]);
    setPendingUser(text);
    setError(null);
    handle.current = sendMessage(id, text, {
      onDelta: (chunk) => setStreaming((current) => current + chunk),
      onTool: (event) =>
        setLiveTools((list) => {
          const index = list.findIndex((item) => item.id === event.id);
          if (index < 0) return [...list, event];
          const copy = [...list];
          copy[index] = event;
          return copy;
        }),
      onState: (state: ArchitectState) => {
        const before = queryClient.getQueryData<SessionDetail>(architectKeys.session(id))?.proposal;
        queryClient.setQueryData<SessionDetail>(architectKeys.session(id), (current) => (current ? { ...current, ...state } : current));
        // A new closing proposal opens the dialog right away (netz-architekt 3, step 7).
        const next = state.proposal;
        if (next && next.kind !== 'load' && (!before || before.kind === 'load' || before.createdAt !== next.createdAt)) {
          setClosingOpen(true);
        }
      },
      onDone: (message: ArchitectMessage) => {
        // Keep both messages on screen until the refetch brings the stored ones.
        queryClient.setQueryData<SessionDetail>(architectKeys.session(id), (current) =>
          current
            ? {
                ...current,
                messages: [
                  ...current.messages,
                  { id: `local-${Date.now()}`, role: 'user', content: text, createdAt: message.createdAt, tools: [] },
                  message,
                ],
              }
            : current,
        );
        finish();
      },
      onError: (key) => {
        setError(key);
        finish();
      },
      onAborted: finish,
    });
  }

  async function keepAlive() {
    if (!selectedId) return;
    await apiFetch(`/architect/sessions/${selectedId}/touch`, { method: 'POST' });
    await refreshArchitect(selectedId);
  }

  /** E-6, E-10, E-12: read a network in. When the architect asked for it, it goes on by itself. */
  async function readIn(networkId: string, purpose: LoadPurpose, name: string, asked: boolean) {
    setWorkBusy('load');
    try {
      // An empty chat gets its session here; the model follows with the start.
      await loadNetwork(await ensureSession(), networkId, purpose);
      setLoadOpen(false);
      notify({ titleKey: 'architect.load.done', values: { name }, variant: 'success' });
      if (asked && sessionActive && !sending) send(t('architect.load.sent', { name }));
    } catch (caught) {
      const key = caught instanceof ApiError ? caught.messageKey : undefined;
      notify({ titleKey: key === 'architect.busy' ? 'architect.busy' : 'architect.load.failed', variant: 'error' });
    } finally {
      setWorkBusy(null);
    }
  }

  async function dismiss() {
    if (!selectedId) return;
    setWorkBusy('dismiss');
    try {
      await dismissProposal(selectedId);
    } finally {
      setWorkBusy(null);
    }
  }

  async function undo() {
    if (!selectedId) return;
    setWorkBusy('undo');
    try {
      const result = await undoSession(selectedId);
      notify({
        titleKey: 'architect.undo.done',
        values: { from: String(result.restoredFrom), version: String(result.version) },
        variant: 'success',
      });
    } catch (caught) {
      const key = caught instanceof ApiError ? caught.messageKey : undefined;
      notify({
        titleKey:
          key === 'networks.conflict'
            ? 'architect.undo.conflict'
            : key === 'networks.versionNotFound'
              ? 'architect.undo.gone'
              : key === 'run.busy'
                ? 'architect.closing.running'
                : 'architect.failed',
        variant: 'error',
      });
    } finally {
      setWorkBusy(null);
    }
  }

  async function exportMarkdown(id: string) {
    const exported = await exportSession(id);
    await saveExportFile(exported.name, new Blob([exported.markdown], { type: 'text/markdown' })).catch(() => false);
  }

  const active = status.data?.active;
  const idleLeft =
    sessionActive && active && !active.generating
      ? Math.max(0, active.idleLimitSeconds - active.idleSeconds) <= active.idleWarnSeconds
        ? Math.max(0, active.idleLimitSeconds - active.idleSeconds)
        : null
      : null;
  const state: ArchitectState | null = picked ?? null;
  const messages = useMemo(() => picked?.messages ?? [], [picked]);
  const proposal = state?.proposal ?? null;
  const cloud = Boolean(picked && picked.provider !== 'ollama');
  const hasDraft = Boolean(state?.draft?.nodes?.length);
  const banner =
    proposal && !sending ? (
      <ProposalCard
        proposal={proposal}
        busy={workBusy === 'load' || workBusy === 'dismiss'}
        cloud={cloud}
        hasDraft={hasDraft}
        onLoad={() => {
          if (proposal.kind === 'load') void readIn(proposal.networkId, proposal.purpose, proposal.name, true);
        }}
        onOpenClosing={() => setClosingOpen(true)}
        onDismiss={() => void dismiss()}
      />
    ) : null;

  return (
    <div ref={pageRef} data-split-row className="flex h-full min-h-0 overflow-hidden">
      <SessionList
        width={sessionsWidth}
        sessions={sessions.data ?? []}
        selectedId={selectedId}
        activeId={activeId}
        onSelect={(id) => {
          if (!sending) select(id);
        }}
        fresh={fresh}
        onNew={newChat}
        onDelete={setConfirmDelete}
        onExport={(id) => void exportMarkdown(id)}
      />
      {/* The grip works in shares of the page; the list keeps a width in px. */}
      <WidthGrip
        label={t('architect.sessions.resize')}
        share={sessionsWidth / pageWidth}
        min={Math.round((SESSIONS_WIDTH.min / pageWidth) * 100)}
        max={Math.round((SESSIONS_WIDTH.max / pageWidth) * 100)}
        marker={false}
        onChange={(next) => setSessionsWidth(next * pageWidth)}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <ModelBar status={status.data} sessionActive={sessionActive} busy={busy || sending} onStart={(pick) => void start(pick)} onStop={() => void stop()} />
        {picked?.catalogChanged ? <p className="border-b bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">{t('architect.catalogChanged')}</p> : null}
        <div data-split-row className="flex min-h-0 flex-1">
          <div className="flex min-h-0 min-w-0 flex-col" style={{ width: `${share * 100}%` }}>
            <ChatPane
              messages={messages}
              streaming={streaming}
              liveTools={liveTools}
              pendingUser={pendingUser}
              sending={sending}
              active={sessionActive}
              idleLeft={idleLeft}
              error={error}
              banner={banner}
              onSend={send}
              onAbort={() => handle.current?.abort()}
              onKeepAlive={() => void keepAlive()}
            />
          </div>
          <WidthGrip label={t('architect.split')} share={share} onChange={setShare} />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col border-l">
            <BriefPanel
              key={selectedId ?? 'new'}
              brief={state?.brief ?? {}}
              draft={state?.draft ?? null}
              editable={!sending && workBusy === null}
              onSave={saveBrief}
            />
            <DraftPanel
              state={state}
              layoutWidth={share}
              actions={{
                disabled: sending || workBusy !== null,
                undoBusy: workBusy === 'undo',
                onLoad: () => setLoadOpen(true),
                onClose: () => setClosingOpen(true),
                onUndo: () => void undo(),
              }}
            />
          </div>
        </div>
      </div>
      <ClosingDialog sessionId={selectedId} open={closingOpen} onOpenChange={setClosingOpen} />
      <LoadNetworkDialog
        open={loadOpen}
        hasDraft={hasDraft}
        cloud={cloud}
        busy={workBusy === 'load'}
        onOpenChange={setLoadOpen}
        onConfirm={(networkId, purpose, name) => void readIn(networkId, purpose, name, false)}
      />
      <StartDialog
        refusal={refusal?.refused ?? null}
        onCancel={() => setRefusal(null)}
        onConfirm={(options) => {
          if (refusal) void start(refusal.pick, options, refusal.sessionId);
        }}
      />
      <AlertDialog open={confirmDelete !== null} onOpenChange={(open) => (open ? undefined : setConfirmDelete(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('architect.sessions.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('architect.sessions.deleteBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('architect.start.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                const id = confirmDelete;
                setConfirmDelete(null);
                if (!id) return;
                if (id === selectedId) select(null);
                void deleteSession(id);
              }}
            >
              {t('architect.sessions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
