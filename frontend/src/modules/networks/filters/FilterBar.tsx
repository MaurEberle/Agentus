import { ArrowDownAZ, ArrowUpAZ } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { useNetworksUi, type NetworksSortKey } from '@/modules/networks/store';

export function FilterBar({ tags }: { tags: string[] }) {
  const { t } = useTranslation();
  const query = useNetworksUi((state) => state.query);
  const sortKey = useNetworksUi((state) => state.sortKey);
  const sortDir = useNetworksUi((state) => state.sortDir);
  const tagFilter = useNetworksUi((state) => state.tagFilter);
  const onlyValid = useNetworksUi((state) => state.onlyValid);
  const onlyActive = useNetworksUi((state) => state.onlyActive);
  const setQuery = useNetworksUi((state) => state.setQuery);
  const setSortKey = useNetworksUi((state) => state.setSortKey);
  const toggleSortDir = useNetworksUi((state) => state.toggleSortDir);
  const toggleTag = useNetworksUi((state) => state.toggleTag);
  const setOnlyValid = useNetworksUi((state) => state.setOnlyValid);
  const setOnlyActive = useNetworksUi((state) => state.setOnlyActive);

  const sorts: NetworksSortKey[] = ['name', 'updatedAt', 'lastUsedAt'];

  return (
    <div className="flex flex-col gap-2 border-b px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('networks.filter.search')}
          className="max-w-sm"
          aria-label={t('networks.filter.search')}
        />
        <div className="flex flex-wrap items-center gap-1">
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
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" size="sm" variant="outline">
              {t('networks.filter.tags')}
              {tagFilter.length ? ` (${tagFilter.length})` : ''}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {tags.length === 0 ? (
              <p className="px-2 py-1.5 text-sm text-muted-foreground">{t('networks.filter.noTags')}</p>
            ) : (
              tags.map((tag) => (
                <DropdownMenuCheckboxItem
                  key={tag}
                  checked={tagFilter.includes(tag)}
                  onSelect={(event) => {
                    event.preventDefault();
                    toggleTag(tag);
                  }}
                >
                  {tag}
                </DropdownMenuCheckboxItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        <p className="text-xs text-muted-foreground">{t('networks.filter.tagsHint')}</p>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={onlyValid} onCheckedChange={(value) => setOnlyValid(value === true)} />
          <span>{t('networks.filter.onlyValid')}</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={onlyActive} onCheckedChange={(value) => setOnlyActive(value === true)} />
          <span>{t('networks.filter.onlyActive')}</span>
        </label>
      </div>
    </div>
  );
}
