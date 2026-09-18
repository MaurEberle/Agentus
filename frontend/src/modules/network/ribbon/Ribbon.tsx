import {
  CheckCircle2,
  Copy,
  Download,
  FolderOpen,
  Library,
  Redo2,
  Save,
  Undo2,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Switch } from '@/components/ui/switch';
import { useNetworkEditor } from '@/modules/network/store';

export function Ribbon({
  dirty,
  valid,
  isActive,
  isRunning,
  readOnly,
  onNew,
  onSave,
  onSaveAs,
  onLoad,
  onDuplicate,
  onExport,
  onValidate,
  onLibrary,
}: {
  dirty: boolean;
  valid: boolean;
  isActive: boolean;
  isRunning: boolean;
  readOnly: boolean;
  onNew: () => void;
  onSave: () => void;
  onSaveAs: () => void;
  onLoad: () => void;
  onDuplicate: () => void;
  onExport: () => void;
  onValidate: () => void;
  onLibrary: () => void;
}) {
  const { t } = useTranslation();
  const document = useNetworkEditor((state) => state.document);
  const snap = useNetworkEditor((state) => state.snap);
  const showGrid = useNetworkEditor((state) => state.showGrid);
  const showMinimap = useNetworkEditor((state) => state.showMinimap);
  const setSnap = useNetworkEditor((state) => state.setSnap);
  const setShowGrid = useNetworkEditor((state) => state.setShowGrid);
  const setShowMinimap = useNetworkEditor((state) => state.setShowMinimap);
  const undo = useNetworkEditor((state) => state.undo);
  const redo = useNetworkEditor((state) => state.redo);
  const canUndo = useNetworkEditor((state) => state.past.length > 0);
  const canRedo = useNetworkEditor((state) => state.future.length > 0);

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-card px-2 py-1.5">
      <p className="max-w-[12rem] truncate text-sm font-medium md:max-w-xs">
        {document.name.trim() || t('network.untitled')}
        {dirty ? ' •' : ''}
      </p>
      <Badge variant={valid ? 'default' : 'destructive'}>
        {valid ? t('network.badge.valid') : t('network.badge.invalid')}
      </Badge>
      {isActive ? <Badge>{t('network.badge.active')}</Badge> : null}
      {isRunning ? <Badge variant="warning">{t('network.badge.running')}</Badge> : null}
      <div className="flex flex-wrap items-center gap-1">
        <Button type="button" size="sm" variant="outline" onClick={onNew}>
          {t('network.ribbon.new')}
        </Button>
        <Button type="button" size="sm" onClick={onSave} disabled={readOnly}>
          <Save />
          {t('network.ribbon.save')}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onSaveAs} disabled={readOnly}>
          {t('network.ribbon.saveAs')}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onLoad}>
          <FolderOpen />
          {t('network.ribbon.load')}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onDuplicate} disabled={!document.id}>
          <Copy />
          {t('network.ribbon.duplicate')}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onExport}>
          <Download />
          {t('network.ribbon.export')}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onValidate}>
          <CheckCircle2 />
          {t('network.ribbon.validate')}
        </Button>
        <Button type="button" size="icon" variant="ghost" onClick={undo} disabled={!canUndo} aria-label={t('network.ribbon.undo')}>
          <Undo2 />
        </Button>
        <Button type="button" size="icon" variant="ghost" onClick={redo} disabled={!canRedo} aria-label={t('network.ribbon.redo')}>
          <Redo2 />
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onLibrary}>
          <Library />
          {t('network.ribbon.library')}
        </Button>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" size="sm" variant="ghost">
            {t('network.ribbon.view')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem className="gap-2" onSelect={(event) => event.preventDefault()}>
            <Switch checked={snap} onCheckedChange={setSnap} />
            {t('network.view.snap')}
          </DropdownMenuItem>
          <DropdownMenuItem className="gap-2" onSelect={(event) => event.preventDefault()}>
            <Switch checked={showGrid} onCheckedChange={setShowGrid} />
            {t('network.view.grid')}
          </DropdownMenuItem>
          <DropdownMenuItem className="gap-2" onSelect={(event) => event.preventDefault()}>
            <Switch checked={showMinimap} onCheckedChange={setShowMinimap} />
            {t('network.view.minimap')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
