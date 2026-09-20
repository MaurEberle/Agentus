import { useEffect, useRef, type JSX } from 'react';
import { useBlocker, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useSettingsQuery } from '@/modules/settings/api';
import { SETTINGS_SECTIONS, parseSettingsSection, type SettingsSectionId } from '@/modules/settings/model';
import { AboutSection } from '@/modules/settings/sections/AboutSection';
import { AppearanceSection } from '@/modules/settings/sections/AppearanceSection';
import { CredentialsSection } from '@/modules/settings/sections/CredentialsSection';
import { DataSection } from '@/modules/settings/sections/DataSection';
import { HelpChatSection } from '@/modules/settings/sections/HelpChatSection';
import { McpSection } from '@/modules/settings/sections/McpSection';
import { RuntimeSection } from '@/modules/settings/sections/RuntimeSection';
import { useSettingsDraft } from '@/modules/settings/store';
import { useAppStore } from '@/store';

const SECTION_COMPONENTS: Record<SettingsSectionId, () => JSX.Element> = {
  appearance: AppearanceSection,
  credentials: CredentialsSection,
  runtime: RuntimeSection,
  'help-chat': HelpChatSection,
  mcp: McpSection,
  data: DataSection,
  about: AboutSection,
};

export function SettingsModule() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { data: settings } = useSettingsQuery();
  const hydrate = useSettingsDraft((state) => state.hydrate);
  const reset = useSettingsDraft((state) => state.reset);
  const isDirty = useSettingsDraft((state) => state.isDirty(settings));
  const setHelpChatFabVisible = useAppStore((state) => state.setHelpChatFabVisible);

  const rawHash = location.hash.replace(/^#/, '');
  const section = parseSettingsSection(location.hash);

  useEffect(() => {
    if (!rawHash) {
      navigate({ pathname: '/settings', hash: 'appearance' }, { replace: true });
      return;
    }
    if (rawHash === 'chatbot') {
      navigate({ pathname: '/settings', hash: 'help-chat' }, { replace: true });
      return;
    }
    if (!(SETTINGS_SECTIONS as readonly string[]).includes(rawHash)) {
      navigate({ pathname: '/settings', hash: 'appearance' }, { replace: true });
    }
  }, [navigate, rawHash]);

  useEffect(() => {
    if (!settings) return;
    const draft = useSettingsDraft.getState();
    if (!draft.runtime || !draft.isDirty(settings)) {
      hydrate(settings);
    }
    setHelpChatFabVisible(settings.helpChatFabVisible);
  }, [hydrate, setHelpChatFabVisible, settings]);

  const dirtyRef = useRef(isDirty);
  dirtyRef.current = isDirty;
  const allowLeaveRef = useRef(false);
  const leaveToRef = useRef<string | null>(null);

  const blocker = useBlocker(({ currentLocation, nextLocation }) => {
    const fromHash = currentLocation.hash.replace(/^#/, '');
    const toHash = nextLocation.hash.replace(/^#/, '');
    const sectionRedirect =
      currentLocation.pathname === nextLocation.pathname &&
      currentLocation.pathname === '/settings' &&
      !fromHash &&
      (toHash === 'appearance' || toHash === 'help-chat' || toHash === 'chatbot');
    const block =
      !allowLeaveRef.current &&
      !sectionRedirect &&
      dirtyRef.current &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.hash !== nextLocation.hash);
    if (block) leaveToRef.current = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
    return block;
  });

  function stay() {
    leaveToRef.current = null;
    if (blocker.state === 'blocked') blocker.reset?.();
  }

  function leave() {
    if (settings) reset(settings);
    const blocked = blocker.state === 'blocked';
    const leaveTo = leaveToRef.current;
    leaveToRef.current = null;
    allowLeaveRef.current = true;
    if (blocked) blocker.proceed?.();
    else if (leaveTo) navigate(leaveTo);
    queueMicrotask(() => {
      allowLeaveRef.current = false;
    });
  }

  function go(id: SettingsSectionId) {
    navigate({ pathname: '/settings', hash: id });
  }

  const Section = SECTION_COMPONENTS[section];

  return (
    <div className="flex h-full min-h-0 flex-col md:flex-row">
      <nav className="hidden w-56 shrink-0 overflow-auto border-r p-2 md:block" aria-label={t('settings.title')}>
        {SETTINGS_SECTIONS.map((id) => (
          <Button
            key={id}
            type="button"
            variant="ghost"
            aria-current={section === id ? 'page' : undefined}
            className={cn('w-full justify-start', section === id && 'bg-accent text-accent-foreground')}
            onClick={() => go(id)}
          >
            {t(`settings.nav.${id}`)}
          </Button>
        ))}
      </nav>
      <div className="border-b p-3 md:hidden">
        <Select value={section} onValueChange={(value) => go(value as SettingsSectionId)}>
          <SelectTrigger aria-label={t('settings.title')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SETTINGS_SECTIONS.map((id) => (
              <SelectItem key={id} value={id}>
                {t(`settings.nav.${id}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="min-h-0 min-w-0 flex-1 overflow-auto p-4 md:p-6">
        <Section />
      </div>
      <AlertDialog
        open={blocker.state === 'blocked'}
        onOpenChange={(open) => {
          if (!open) stay();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.unsaved.title')}</AlertDialogTitle>
            <AlertDialogDescription>{t('settings.unsaved.body')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button type="button" variant="outline" onClick={stay}>
              {t('settings.unsaved.stay')}
            </Button>
            <Button type="button" onClick={leave}>
              {t('settings.unsaved.leave')}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
