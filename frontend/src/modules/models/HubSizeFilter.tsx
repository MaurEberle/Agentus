import { ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import { billions } from '@/modules/models/hubSize';

/**
 * Slider stops in billions; the handles move stop by stop, so the stops decide the room.
 * Most of the track goes to 14–80B, where local models are usually weighed against each
 * other; below and above it the steps are coarse. Exact values go in the fields.
 */
const STOPS = [1, 3, 4, 8, 12, 14, 20, 24, 27, 30, 32, 35, 40, 50, 60, 70, 80, 120, 235, 400];
const LAST = STOPS.length + 1; // positions: 0 = no minimum, 1..STOPS.length = stops, LAST = no maximum
const TICKS = [3, 8, 14, 24, 32, 50, 70, 235];
const THUMB_PX = 16;

const PRESETS: { key: string; min: string; max: string }[] = [
  { key: 'any', min: '', max: '' },
  { key: '3', min: '', max: '3' },
  { key: '8', min: '3', max: '8' },
  { key: '14', min: '8', max: '14' },
  { key: '32', min: '14', max: '32' },
  { key: '70', min: '32', max: '70' },
  { key: 'xl', min: '70', max: '' },
];

function nearestStop(value: number): number {
  let best = 0;
  for (let index = 1; index < STOPS.length; index += 1) {
    if (Math.abs(Math.log(STOPS[index] / value)) < Math.abs(Math.log(STOPS[best] / value))) best = index;
  }
  return best + 1;
}

function position(raw: string, open: number): number {
  const value = billions(raw);
  return value && Number(value) > 0 ? nearestStop(Number(value)) : open;
}

/** Thumb centre for a share of the track: native thumbs stop half a thumb short of each end. */
function along(share: number): string {
  return `calc(${share * 100}% + ${(0.5 - share) * THUMB_PX}px)`;
}

const RANGE =
  'pointer-events-none absolute inset-0 h-5 w-full cursor-pointer appearance-none bg-transparent focus-visible:outline-none ' +
  '[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:appearance-none ' +
  // Preflight's border-style: solid does not reach the thumb pseudo-elements.
  '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-solid [&::-webkit-slider-thumb]:border-primary ' +
  '[&::-webkit-slider-thumb]:bg-background [&::-webkit-slider-thumb]:shadow ' +
  'focus-visible:[&::-webkit-slider-thumb]:ring-2 focus-visible:[&::-webkit-slider-thumb]:ring-ring ' +
  '[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:rounded-full ' +
  '[&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-solid [&::-moz-range-thumb]:border-primary [&::-moz-range-thumb]:bg-background';

/**
 * Parameter range: presets for the usual classes, a two-handle slider on a log scale,
 * and two fields for exact bounds (decimals allowed). Empty means open on that side.
 */
export function HubSizeFilter({
  min,
  max,
  gpu,
  onChange,
}: {
  min: string;
  max: string;
  /** "Only what fits the GPU": the largest model at Q4_K_M (null without a GPU) and the VRAM shown. */
  gpu: { maxB: number | null; vram: string; on: boolean; onChange: (on: boolean) => void };
  /** `now`: search right away (a preset); otherwise once typing or dragging settles. */
  onChange: (next: { min: string; max: string }, now: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const number = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 });
  const low = billions(min);
  const high = billions(max);
  const active = Boolean(low || high);
  const lo = position(min, 0);
  const hi = Math.max(position(max, LAST), lo + 1);
  const shown = (raw: string | null) => (raw ? number.format(Number(raw)) : '');
  const label = !active
    ? t('models.hub.sizes.any')
    : !low
      ? t('models.hub.range.upTo', { max: shown(high) })
      : !high
        ? t('models.hub.range.from', { min: shown(low) })
        : t('models.hub.range.between', { min: shown(low), max: shown(high) });
  const gpuOn = gpu.on && gpu.maxB != null;
  const pill = [active ? label : '', gpuOn ? t('models.hub.fit.pill') : ''].filter(Boolean).join(' · ');
  const preset = PRESETS.find(
    (item) => (billions(item.min) ?? '') === (low ?? '') && (billions(item.max) ?? '') === (high ?? ''),
  )?.key;

  const fromPosition = (index: number, open: number) => (index === open ? '' : String(STOPS[index - 1]));

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 w-auto shrink-0 gap-1.5 px-2.5 text-sm font-normal shadow-sm"
          aria-label={`${t('models.hub.size')}: ${pill || label}`}
        >
          <span>{t('models.hub.size')}</span>
          {pill ? (
            <span className="inline-flex h-5 items-center rounded-full bg-primary px-1.5 text-[11px] font-medium text-primary-foreground">
              {pill}
            </span>
          ) : null}
          <ChevronDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 p-3">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-medium">{t('models.hub.detail.parameters')}</span>
          <span className="text-sm tabular-nums text-muted-foreground">{label}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1" role="group" aria-label={t('models.hub.size')}>
          {PRESETS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={preset === item.key}
              onClick={() => onChange({ min: item.min, max: item.max }, true)}
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-xs font-medium',
                preset === item.key
                  ? 'border-transparent bg-primary text-primary-foreground'
                  : 'border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )}
            >
              {t(`models.hub.sizes.${item.key}`)}
            </button>
          ))}
        </div>
        <div className="relative mt-4 h-5">
          <div className="absolute inset-x-2 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted" />
          <div
            className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-primary"
            style={{ left: along(lo / LAST), right: `calc(100% - ${along(hi / LAST)})` }}
          />
          <input
            type="range"
            min={0}
            max={LAST}
            step={1}
            value={lo}
            aria-label={t('models.hub.sizes.from')}
            aria-valuetext={low ? `${shown(low)} B` : t('models.hub.sizes.any')}
            onChange={(event) => onChange({ min: fromPosition(Math.min(Number(event.target.value), hi - 1), 0), max }, false)}
            className={cn(RANGE, lo > LAST / 2 ? 'z-20' : 'z-10')}
          />
          <input
            type="range"
            min={0}
            max={LAST}
            step={1}
            value={hi}
            aria-label={t('models.hub.sizes.to')}
            aria-valuetext={high ? `${shown(high)} B` : t('models.hub.sizes.any')}
            onChange={(event) => onChange({ min, max: fromPosition(Math.max(Number(event.target.value), lo + 1), LAST) }, false)}
            className={cn(RANGE, 'z-10')}
          />
        </div>
        <div className="relative mt-1 h-4 text-[10px] tabular-nums text-muted-foreground" aria-hidden>
          <span className="absolute -translate-x-1/2" style={{ left: along(0) }}>0</span>
          {TICKS.map((tick) => (
            <span key={tick} className="absolute -translate-x-1/2" style={{ left: along(nearestStop(tick) / LAST) }}>
              {number.format(tick)}
            </span>
          ))}
          <span className="absolute -translate-x-1/2" style={{ left: along(1) }}>∞</span>
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">{t('models.hub.sizes.from')}</span>
            <Input
              value={min}
              onChange={(event) => onChange({ min: event.target.value, max }, false)}
              inputMode="decimal"
              placeholder="0"
              aria-invalid={min.trim() !== '' && billions(min) == null}
              className="h-8 w-16 tabular-nums"
            />
            <span className="text-muted-foreground">B</span>
          </label>
          <span className="text-muted-foreground" aria-hidden>
            –
          </span>
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">{t('models.hub.sizes.to')}</span>
            <Input
              value={max}
              onChange={(event) => onChange({ min, max: event.target.value }, false)}
              inputMode="decimal"
              placeholder="∞"
              aria-invalid={max.trim() !== '' && billions(max) == null}
              className="h-8 w-16 tabular-nums"
            />
            <span className="text-muted-foreground">B</span>
          </label>
        </div>
        <label className="mt-3 flex items-start gap-2.5 border-t pt-3">
          <Switch
            checked={gpuOn}
            disabled={gpu.maxB == null}
            onCheckedChange={(value) => gpu.onChange(value === true)}
            className="mt-0.5"
          />
          <span className="grid gap-0.5">
            <span className="text-sm">{t('models.hub.fit.only')}</span>
            <span className="text-xs text-muted-foreground">
              {gpu.maxB == null
                ? t('models.hub.fit.noGpu')
                : t('models.hub.fit.onlyHint', { max: number.format(gpu.maxB), vram: gpu.vram })}
            </span>
          </span>
        </label>
      </PopoverContent>
    </Popover>
  );
}
