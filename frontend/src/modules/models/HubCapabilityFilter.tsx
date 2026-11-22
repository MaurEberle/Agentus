import { Check, ChevronDown, Minus, X, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { HubCapabilities, HubCapability, HubCapabilityRule } from '@/modules/models/store';

const CAPABILITIES: HubCapability[] = ['tools', 'thinking', 'vision'];
type Choice = HubCapabilityRule | 'any';
const CHOICES: { value: Choice; icon: LucideIcon }[] = [
  { value: 'must', icon: Check },
  { value: 'any', icon: Minus },
  { value: 'never', icon: X },
];

/** Capabilities as three-way switches: must have, either (off), must not have. Combinable. */
export function HubCapabilityFilter({
  value,
  onChoose,
}: {
  value: HubCapabilities;
  /** 'any' clears the rule for that capability. */
  onChoose: (key: HubCapability, choice: HubCapabilityRule | 'any') => void;
}) {
  const { t } = useTranslation();
  const must = CAPABILITIES.filter((key) => value[key] === 'must');
  const never = CAPABILITIES.filter((key) => value[key] === 'never');
  const summary = [...must, ...never]
    .map((key) => `${t(`models.badges.${key}`)}: ${t(`models.hub.ruleHint.${value[key]}`)}`)
    .join(', ');

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 w-auto shrink-0 gap-1.5 px-2.5 text-sm font-normal shadow-sm"
          aria-label={summary ? `${t('models.hub.capabilities')}: ${summary}` : t('models.hub.capabilities')}
        >
          <span>{t('models.hub.capabilities')}</span>
          {must.length > 0 ? (
            <span className="inline-flex h-5 items-center gap-0.5 rounded-full bg-primary px-1.5 text-[11px] font-medium text-primary-foreground">
              <Check className="size-3" aria-hidden />
              {must.length}
            </span>
          ) : null}
          {never.length > 0 ? (
            <span className="inline-flex h-5 items-center gap-0.5 rounded-full bg-destructive px-1.5 text-[11px] font-medium text-destructive-foreground">
              <X className="size-3" aria-hidden />
              {never.length}
            </span>
          ) : null}
          <ChevronDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-3">
        <div className="grid grid-cols-[auto_auto] items-center gap-x-4 gap-y-2">
          {CAPABILITIES.map((key) => {
            const current: Choice = value[key] ?? 'any';
            return (
              <div key={key} className="contents">
                <span className="text-sm">{t(`models.badges.${key}`)}</span>
                <div
                  role="radiogroup"
                  aria-label={t(`models.badges.${key}`)}
                  className="inline-flex h-7 items-stretch rounded-md border border-input p-0.5"
                >
                  {CHOICES.map(({ value: choice, icon: Icon }) => {
                    const on = current === choice;
                    return (
                      <button
                        key={choice}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        title={t(`models.hub.ruleHint.${choice}`)}
                        onClick={() => onChoose(key, choice)}
                        className={cn(
                          'flex items-center gap-1 rounded px-2 text-xs transition-colors',
                          !on && 'text-muted-foreground hover:bg-muted hover:text-foreground',
                          on && choice === 'must' && 'bg-primary text-primary-foreground',
                          on && choice === 'any' && 'bg-muted font-medium text-foreground',
                          on && choice === 'never' && 'bg-destructive text-destructive-foreground',
                        )}
                      >
                        <Icon className="size-3.5" aria-hidden />
                        {t(`models.hub.rule.${choice}`)}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
