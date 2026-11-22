import { useMemo } from 'react';
import { FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { notify } from '@/lib/notifications';
import { saveExportFile } from '@/lib/saveFile';
import { fileStamp, safeFilePart, shortId } from '@/lib/format';
import { LogDetailBody } from '@/modules/monitoring/log/LogDetailBody';
import { LogViewSwitch } from '@/modules/monitoring/log/LogViewSwitch';
import { RunLogList } from '@/modules/monitoring/log/RunLogList';
import { RunSummaryCard } from '@/modules/monitoring/log/RunSummaryCard';
import { useRunLog } from '@/modules/monitoring/log/useRunLog';
import { logHasExtra } from '@/modules/monitoring/model/graph';
import { logsToMarkdown } from '@/modules/monitoring/model/logView';
import { maskText } from '@/modules/monitoring/model/mask';
import { DetailOverlay } from '@/modules/monitoring/overlay/DetailOverlay';
import type { LogEvent, RunDetail } from '@/modules/history/model/types';
import { useHistoryUi } from '@/modules/history/store';

function nodeOptions(detail: RunDetail): Array<{ id: string; name: string }> {
  if (detail.graphSnapshot) {
    return detail.graphSnapshot.nodes.map((node) => ({
      id: node.id,
      name:
        typeof node.data.displayName === 'string' && node.data.displayName.trim() ? node.data.displayName : node.type,
    }));
  }
  return (detail.steps ?? []).map((step) => ({ id: step.nodeId, name: step.nodeName ?? step.nodeId }));
}

export function ArchiveLog({ logs, detail }: { logs: LogEvent[]; detail: RunDetail }) {
  const { t, i18n } = useTranslation();
  const view = useHistoryUi((state) => state.logView);
  const query = useHistoryUi((state) => state.logQuery);
  const nodeId = useHistoryUi((state) => state.logNodeId);
  const errorsOnly = useHistoryUi((state) => state.logErrorsOnly);
  const selectedLogId = useHistoryUi((state) => state.selectedLogId);
  const setLogView = useHistoryUi((state) => state.setLogView);
  const setLogQuery = useHistoryUi((state) => state.setLogQuery);
  const setLogNodeId = useHistoryUi((state) => state.setLogNodeId);
  const setLogErrorsOnly = useHistoryUi((state) => state.setLogErrorsOnly);
  const setSelectedLogId = useHistoryUi((state) => state.setSelectedLogId);

  const options = useMemo(() => nodeOptions(detail), [detail]);
  const names = useMemo(() => new Map(options.map((node) => [node.id, node.name] as const)), [options]);
  const { ctx, entries, lineOf, summary } = useRunLog(logs, names, { view, query, nodeId, errorsOnly });
  const selected = logs.find((item) => item.id === selectedLogId) ?? null;

  async function exportText() {
    const title = `${detail.networkName ?? t('monitoring.log.exportTitle')} · ${shortId(detail.runId)}`;
    const text = maskText(logsToMarkdown(entries, ctx, { title, summary }));
    try {
      const saved = await saveExportFile(
        `${safeFilePart(detail.networkName ?? 'network')}-${shortId(detail.runId)}-${fileStamp()}.md`,
        new Blob([text], { type: 'text/markdown' }),
      );
      if (saved) notify({ titleKey: 'history.notify.exported', variant: 'success', persist: false });
    } catch {
      notify({ titleKey: 'history.notify.exportError', variant: 'error' });
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <LogViewSwitch value={view} onChange={setLogView} />
        <div className="grid min-w-[8rem] flex-1 gap-1.5">
          <Label className="text-xs" htmlFor="history-log-q">
            {t('history.log.search')}
          </Label>
          <Input
            id="history-log-q"
            className="h-8"
            value={query}
            onChange={(event) => setLogQuery(event.target.value)}
            placeholder={t('runLog.views.searchHint')}
          />
        </div>
        <div className="grid w-40 gap-1.5">
          <Label className="text-xs">{t('history.log.node')}</Label>
          <Select value={nodeId ?? 'all'} onValueChange={(value) => setLogNodeId(value === 'all' ? null : value)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('history.log.allNodes')}</SelectItem>
              {options.map((node) => (
                <SelectItem key={node.id} value={node.id}>
                  {node.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <label className="flex h-8 items-center gap-2 text-sm">
          <Checkbox checked={errorsOnly} onCheckedChange={(value) => setLogErrorsOnly(value === true)} />
          {t('history.log.errorsOnly')}
        </label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="text-sm"
          onClick={() => void exportText()}
          disabled={entries.length === 0}
        >
          <FileText className="size-3.5" />
          {t('monitoring.log.exportText')}
        </Button>
      </div>
      {summary ? <RunSummaryCard event={summary} locale={i18n.language} /> : null}
      <div className="max-h-[min(32rem,60vh)] min-h-[10rem] overflow-auto rounded-md border bg-muted/20 font-log text-xs">
        <RunLogList
          entries={entries}
          lineOf={lineOf}
          locale={i18n.language}
          onOpen={setSelectedLogId}
          live={false}
          expandAll={query.trim().length > 0 || nodeId !== null}
          emptyText={t('history.log.empty')}
        />
      </div>
      <DetailOverlay
        open={Boolean(selected && logHasExtra(selected))}
        onOpenChange={(open) => {
          if (!open) setSelectedLogId(null);
        }}
        title={t('history.log.detailTitle')}
      >
        {selected ? <LogDetailBody event={selected} ctx={ctx} /> : null}
      </DetailOverlay>
    </div>
  );
}
