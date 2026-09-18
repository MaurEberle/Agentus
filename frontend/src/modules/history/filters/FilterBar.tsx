import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toDateInput } from '@/modules/history/model/format';
import type { HistoryFilter, RangeKey } from '@/modules/history/model/types';
import { RUN_OUTCOMES } from '@/modules/history/model/types';
import { cn } from '@/lib/utils';

export function FilterBar({
  filter,
  networks,
  models,
  onChange,
  onReset,
}: {
  filter: HistoryFilter;
  networks: Array<{ id: string; name: string }>;
  models: string[];
  onChange: (patch: Partial<HistoryFilter>) => void;
  onReset: () => void;
}) {
  const { t } = useTranslation();
  const filtersOn = Boolean(
    filter.range !== '7d' ||
      filter.networkId ||
      filter.model ||
      filter.q.trim() ||
      filter.outcomes.length,
  );

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="w-36">
        <Label className="text-xs">{t('history.filter.range')}</Label>
        <Select value={filter.range} onValueChange={(value) => onChange({ range: value as RangeKey, page: 1 })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="today">{t('history.filter.today')}</SelectItem>
            <SelectItem value="7d">{t('history.filter.days7')}</SelectItem>
            <SelectItem value="30d">{t('history.filter.days30')}</SelectItem>
            <SelectItem value="custom">{t('history.filter.custom')}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {filter.range === 'custom' ? (
        <>
          <div>
            <Label className="text-xs" htmlFor="history-from">
              {t('history.filter.from')}
            </Label>
            <Input
              id="history-from"
              type="date"
              value={toDateInput(filter.from)}
              onChange={(event) => onChange({ from: event.target.value, range: 'custom', page: 1 })}
            />
          </div>
          <div>
            <Label className="text-xs" htmlFor="history-to">
              {t('history.filter.to')}
            </Label>
            <Input
              id="history-to"
              type="date"
              value={toDateInput(filter.to)}
              onChange={(event) => onChange({ to: event.target.value, range: 'custom', page: 1 })}
            />
          </div>
        </>
      ) : null}
      <div className="w-44">
        <Label className="text-xs">{t('history.filter.network')}</Label>
        <Select
          value={filter.networkId || 'all'}
          onValueChange={(value) => onChange({ networkId: value === 'all' ? '' : value, page: 1 })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('history.filter.allNetworks')}</SelectItem>
            {networks.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-48">
        <Label className="text-xs">{t('history.filter.model')}</Label>
        <Select
          value={filter.model || 'all'}
          onValueChange={(value) => onChange({ model: value === 'all' ? '' : value, page: 1 })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('history.filter.allModels')}</SelectItem>
            {models.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="min-w-[10rem] flex-1">
        <Label className="text-xs" htmlFor="history-q">
          {t('history.filter.search')}
        </Label>
        <Input
          id="history-q"
          value={filter.q}
          onChange={(event) => onChange({ q: event.target.value, page: 1 })}
          placeholder={t('history.filter.searchHint')}
        />
      </div>
      <div className="flex flex-wrap items-center gap-1 pb-1">
        {RUN_OUTCOMES.map((outcome) => {
          const active = filter.outcomes.includes(outcome);
          return (
            <Button
              key={outcome}
              type="button"
              size="sm"
              variant={active ? 'default' : 'outline'}
              className={cn('h-8')}
              onClick={() => {
                const outcomes = active
                  ? filter.outcomes.filter((item) => item !== outcome)
                  : [...filter.outcomes, outcome];
                onChange({ outcomes, page: 1 });
              }}
            >
              {t(`history.outcome.${outcome}`)}
            </Button>
          );
        })}
      </div>
      {filtersOn ? (
        <Button type="button" size="sm" variant="ghost" className="h-8" onClick={onReset}>
          {t('history.filter.reset')}
        </Button>
      ) : null}
    </div>
  );
}
