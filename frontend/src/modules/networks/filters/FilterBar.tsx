import { ArrowDownAZ, ArrowUpAZ } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { TagCloud } from '@/components/tags/TagCloud';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { useNetworksUi, type NetworksSortKey } from '@/modules/networks/store';

export function FilterBar({ tags, tagSets }: { tags: string[]; tagSets: readonly (readonly string[])[] }) {
  const { t } = useTranslation();
  const query = useNetworksUi((state) => state.query);
  const sortKey = useNetworksUi((state) => state.sortKey);
  const sortDir = useNetworksUi((state) => state.sortDir);
  const tagFilter = useNetworksUi((state) => state.tagFilter);
  const tagMode = useNetworksUi((state) => state.tagMode);
  const onlyValid = useNetworksUi((state) => state.onlyValid);
  const onlyActive = useNetworksUi((state) => state.onlyActive);
  const setQuery = useNetworksUi((state) => state.setQuery);
  const setSortKey = useNetworksUi((state) => state.setSortKey);
  const toggleSortDir = useNetworksUi((state) => state.toggleSortDir);
  const toggleTag = useNetworksUi((state) => state.toggleTag);
  const clearTags = useNetworksUi((state) => state.clearTags);
  const setTagMode = useNetworksUi((state) => state.setTagMode);
  const setOnlyValid = useNetworksUi((state) => state.setOnlyValid);
  const setOnlyActive = useNetworksUi((state) => state.setOnlyActive);

  const sorts: NetworksSortKey[] = ['name', 'updatedAt', 'lastUsedAt'];

  return (
    <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t('networks.filter.search')}
        className="max-w-xs"
        aria-label={t('networks.filter.search')}
      />
      <TagCloud
        tags={tags}
        tagSets={tagSets}
        selected={tagFilter}
        mode={tagMode}
        onToggle={toggleTag}
        onClear={clearTags}
        onModeChange={setTagMode}
        label={t('networks.filter.tags')}
      />
      <div className="flex items-center gap-1">
        {sorts.map((key) => (
          <Button
            key={key}
            type="button"
            size="sm"
            variant={sortKey === key ? 'secondary' : 'outline'}
            onClick={() => setSortKey(key)}
          >
            {t(`networks.filter.sort.${key}`)}
          </Button>
        ))}
        <Button type="button" size="icon" variant="outline" onClick={toggleSortDir} aria-label={t('networks.filter.direction')}>
          {sortDir === 'asc' ? <ArrowUpAZ className="size-4" /> : <ArrowDownAZ className="size-4" />}
        </Button>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={onlyValid} onCheckedChange={(value) => setOnlyValid(value === true)} />
        <span>{t('networks.filter.onlyValid')}</span>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={onlyActive} onCheckedChange={(value) => setOnlyActive(value === true)} />
        <span>{t('networks.filter.onlyActive')}</span>
      </label>
    </div>
  );
}
