import { useEffect, useMemo, useState } from 'react';
import { CircleAlert, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '@/api/client';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { notify } from '@/lib/notifications';
import { applySession, loadNetwork, useClosingQuery, type ClosingPreview } from '@/modules/architect/api';
import { DiffList } from '@/modules/network/versions/DiffList';
import { useNetworkEditor } from '@/modules/network/store';

const TYPE_ORDER = ['orchestrator', 'agent', 'router', 'llm', 'tool', 'mcp', 'knowledge', 'chat_input', 'end'];

function Structure({ preview }: { preview: ClosingPreview }) {
  const { t } = useTranslation();
  const counts = Object.entries(preview.stats.counts).sort(
    ([a], [b]) => TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b),
  );
  return (
    <section className="grid gap-1.5 text-sm">
      <h3 className="font-medium">{t('architect.closing.structure')}</h3>
      <p className="text-muted-foreground">
        {counts.map(([type, count]) => `${count} × ${t(`network.palette.${type}`, { defaultValue: type })}`).join(' · ')}
      </p>
      {preview.stats.models.length > 0 ? (
        <p className="text-muted-foreground">
          <span className="text-foreground">{t('architect.closing.models')}: </span>
          {preview.stats.models.join(', ')}
        </p>
      ) : null}
      {preview.stats.tools.length > 0 ? (
        <p className="text-muted-foreground">
          <span className="text-foreground">{t('architect.closing.tools')}: </span>
          {preview.stats.tools.join(', ')}
        </p>
      ) : null}
    </section>
  );
}

/**
 * The closing dialog (netz-architekt 3, step 7): summary, changes, risks, options. Creating or
 * changing a network happens only here, on the user's click (E-5).
 */
export function ClosingDialog({
  sessionId,
  open,
  onOpenChange,
}: {
  sessionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useClosingQuery(sessionId, open);
  const preview = query.data;
  const [setActive, setSetActive] = useState(false);
  const [toLibrary, setToLibrary] = useState(false);
  const [openEditor, setOpenEditor] = useState(false);
  const [busy, setBusy] = useState<'apply' | 'force' | 'reload' | null>(null);
  const [conflict, setConflict] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setSetActive(false);
    setToLibrary(false);
    setOpenEditor(false);
    setConflict(false);
    setFailure(null);
  }, [open]);

  const editorDirty = useMemo(() => {
    if (!open || !preview?.target) return false;
    const editor = useNetworkEditor.getState();
    return editor.document.id === preview.target.id && editor.isDirty();
  }, [open, preview?.target]);

  const update = preview?.mode === 'update';
  const showConflict = Boolean(update && (conflict || preview?.changedSince));
  const nothingToSave = Boolean(update && preview?.diff?.empty);
  const blocked = !preview || !preview.check.ok || preview.running || nothingToSave;

  async function apply(force: boolean) {
    if (!sessionId || !preview) return;
    setBusy(force ? 'force' : 'apply');
    setFailure(null);
    try {
      const result = await applySession(sessionId, {
        mode: preview.mode,
        setActive,
        promptsToLibrary: toLibrary,
        force,
      });
      notify({
        titleKey: result.mode === 'create' ? 'architect.closing.created' : 'architect.closing.updated',
        values: { name: result.name, version: String(result.version) },
        variant: 'success',
      });
      if (result.promptsAdded > 0) {
        notify({ titleKey: 'architect.closing.promptsAdded', values: { count: String(result.promptsAdded) }, variant: 'success' });
      }
      onOpenChange(false);
      if (openEditor) navigate(`/network/${result.networkId}`);
    } catch (error) {
      const key = error instanceof ApiError ? error.messageKey : undefined;
      if (key === 'networks.conflict') {
        setConflict(true);
        void query.refetch();
      } else {
        setFailure(key === 'run.busy' ? 'architect.closing.running' : key ? `architect.closing.error.${key.replace(/\./g, '_')}` : 'architect.failed');
      }
    } finally {
      setBusy(null);
    }
  }

  async function reload() {
    if (!sessionId || !preview?.target) return;
    setBusy('reload');
    try {
      await loadNetwork(sessionId, preview.target.id, 'change');
      notify({ titleKey: 'architect.load.done', values: { name: preview.target.name }, variant: 'success' });
      onOpenChange(false);
    } catch {
      setFailure('architect.failed');
    } finally {
      setBusy(null);
    }
  }

  const title = preview
    ? update
      ? t('architect.closing.titleUpdate', { name: preview.target?.name ?? preview.name })
      : t('architect.closing.titleCreate', { name: preview.name || t('architect.draft.unnamed') })
    : t('architect.closing.title');

  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" closeLabel={t('architect.closing.cancel')}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {preview ? preview.summary || preview.description || t('architect.closing.lead') : t('architect.closing.loading')}
          </DialogDescription>
        </DialogHeader>
        {query.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{t('architect.closing.loadFailed')}</AlertDescription>
          </Alert>
        ) : null}
        {preview ? (
          <div className="grid gap-4">
            {!preview.check.ok ? (
              <Alert variant="destructive">
                <AlertDescription>{t('architect.closing.invalid', { count: preview.check.errors.length })}</AlertDescription>
              </Alert>
            ) : null}
            {preview.running ? (
              <Alert variant="destructive">
                <AlertDescription>{t('architect.closing.running')}</AlertDescription>
              </Alert>
            ) : null}
            <Structure preview={preview} />
            {update && preview.diff ? (
              <section className="grid gap-1.5 text-sm">
                <h3 className="font-medium">{t('architect.closing.changes', { version: preview.target?.version ?? '' })}</h3>
                <DiffList diff={preview.diff} />
              </section>
            ) : null}
            {preview.risks.length > 0 ? (
              <section className="grid gap-1.5 text-sm">
                <h3 className="font-medium">{t('architect.closing.risks')}</h3>
                <ul className="grid gap-1">
                  {preview.risks.map((risk, index) => (
                    <li key={index} className="flex gap-1.5 text-warning">
                      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                      <span>
                        {t(`architect.risk.${(risk.key ?? '').replace(/^risk\./, '')}`, { ref: risk.ref ?? '', defaultValue: risk.text })}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {editorDirty ? (
              <Alert>
                <AlertDescription className="flex gap-1.5 text-warning">
                  <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  <span>{t('architect.closing.editorDirty')}</span>
                </AlertDescription>
              </Alert>
            ) : null}
            {showConflict ? (
              <Alert>
                <AlertDescription className="grid gap-1">
                  <span className="font-medium text-warning">
                    {t('architect.closing.changedSince', { version: preview.target?.version ?? '' })}
                  </span>
                  <span className="text-muted-foreground">{t('architect.closing.conflictHint')}</span>
                </AlertDescription>
              </Alert>
            ) : null}
            <fieldset className="grid gap-2 text-sm">
              <legend className="mb-1 font-medium">{t('architect.closing.options')}</legend>
              <label className="flex items-start gap-2">
                <Checkbox
                  checked={setActive}
                  disabled={preview.networkRunning}
                  onCheckedChange={(value) => setSetActive(value === true)}
                  className="mt-0.5"
                />
                <span>
                  {t('architect.closing.setActive')}
                  {preview.networkRunning ? (
                    <span className="block text-xs text-muted-foreground">{t('architect.closing.setActiveBusy')}</span>
                  ) : null}
                </span>
              </label>
              <label className="flex items-start gap-2">
                <Checkbox
                  checked={toLibrary}
                  disabled={preview.prompts.length === 0}
                  onCheckedChange={(value) => setToLibrary(value === true)}
                  className="mt-0.5"
                />
                <span>
                  {t('architect.closing.prompts', { count: preview.prompts.length })}
                  {preview.prompts.length > 0 ? (
                    <span className="block text-xs text-muted-foreground">
                      {preview.prompts.map((item) => item.name ?? item.ref).join(', ')}
                    </span>
                  ) : null}
                </span>
              </label>
              <label className="flex items-start gap-2">
                <Checkbox checked={openEditor} onCheckedChange={(value) => setOpenEditor(value === true)} className="mt-0.5" />
                <span>{t('architect.closing.openEditor')}</span>
              </label>
            </fieldset>
            <p className="text-xs text-muted-foreground">
              {update ? t('architect.closing.versionNoteUpdate') : t('architect.closing.versionNoteCreate')}
            </p>
            {nothingToSave ? <p className="text-xs text-muted-foreground">{t('architect.closing.nothing')}</p> : null}
            {failure ? (
              <Alert variant="destructive">
                <AlertDescription>{t(failure, { defaultValue: t('architect.failed') })}</AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy !== null} onClick={() => onOpenChange(false)}>
            {t('architect.closing.cancel')}
          </Button>
          {showConflict ? (
            <>
              <Button type="button" variant="outline" loading={busy === 'reload'} disabled={busy !== null} onClick={() => void reload()}>
                {t('architect.closing.reload')}
              </Button>
              <Button type="button" loading={busy === 'force'} disabled={blocked || busy !== null} onClick={() => void apply(true)}>
                {t('architect.closing.force')}
              </Button>
            </>
          ) : (
            <Button type="button" loading={busy === 'apply'} disabled={blocked || busy !== null} onClick={() => void apply(false)}>
              {update ? t('architect.closing.update') : t('architect.closing.create')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
