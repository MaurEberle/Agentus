import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  describeLog,
  filterEntries,
  findSummary,
  groupLogs,
  searchText,
  type LogContext,
  type LogLine,
  type LogView,
} from '@/modules/monitoring/model/logView';
import type { LogEvent } from '@/modules/monitoring/model/types';

type Described = { line: LogLine; text: string };

/** Shared by the live log and the history: sentences, groups, filters, summary line. */
export function useRunLog(
  logs: LogEvent[],
  names: Map<string, string>,
  filter: { view: LogView; query: string; nodeId: string | null; errorsOnly: boolean },
) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const ctx = useMemo<LogContext>(() => ({ t, locale, names: (id) => names.get(id) }), [locale, names, t]);
  // Log events never change once they arrived; the cache lives as long as the language and names.
  const cache = useMemo(() => {
    void ctx;
    return new WeakMap<LogEvent, Described>();
  }, [ctx]);
  const described = useCallback(
    (event: LogEvent): Described => {
      let hit = cache.get(event);
      if (!hit) {
        const line = describeLog(event, ctx);
        hit = { line, text: searchText(event, line) };
        cache.set(event, hit);
      }
      return hit;
    },
    [cache, ctx],
  );
  const lineOf = useCallback((event: LogEvent) => described(event).line, [described]);
  const textOf = useCallback((event: LogEvent) => described(event).text, [described]);
  const grouped = useMemo(() => groupLogs(logs), [logs]);
  const { view, query, nodeId, errorsOnly } = filter;
  const entries = useMemo(
    () => filterEntries(grouped, { view, query, nodeId, errorsOnly }, textOf),
    [errorsOnly, grouped, nodeId, query, textOf, view],
  );
  const summary = useMemo(() => findSummary(logs), [logs]);
  return { ctx, entries, lineOf, summary };
}
