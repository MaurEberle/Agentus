import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { notify } from '@/lib/notifications';
import {
  deleteMcpServer,
  pingMcpServer,
  setMcpEnabled,
  upsertMcpServer,
  useCredentialsQuery,
  useMcpRecipesQuery,
  useMcpServersQuery,
} from '@/modules/settings/api';
import type { CredentialKind, McpRecipe, McpTransport } from '@/modules/settings/model';
import { isForbiddenDataRoot } from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

type PresetForm = {
  recipe: McpRecipe;
  credentialIds: string[];
  rootPath: string;
};

type CustomForm = {
  name: string;
  transport: McpTransport;
  command: string;
  args: string;
  url: string;
};

const emptyCustom = (): CustomForm => ({
  name: '',
  transport: 'stdio',
  command: '',
  args: '',
  url: '',
});

export function McpSection() {
  const { t } = useTranslation();
  const { data: recipesData } = useMcpRecipesQuery();
  const { data: serversData } = useMcpServersQuery();
  const { data: credentialsData } = useCredentialsQuery();
  const recipes = recipesData?.items ?? [];
  const servers = serversData?.items ?? [];
  const credentials = credentialsData?.items ?? [];
  const [preset, setPreset] = useState<PresetForm | null>(null);
  const [custom, setCustom] = useState<CustomForm | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const configuredRecipeIds = useMemo(
    () => new Set((serversData?.items ?? []).map((item) => item.recipeId).filter(Boolean)),
    [serversData],
  );

  const [savingPreset, setSavingPreset] = useState(false);
  const [savingCustom, setSavingCustom] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [pingingId, setPingingId] = useState<string | null>(null);

  async function savePreset() {
    if (!preset) return;
    if (preset.recipe.needsRoot && isForbiddenDataRoot(preset.rootPath)) {
      notify({ titleKey: 'settings.data.invalidRoot', variant: 'error' });
      return;
    }
    setSavingPreset(true);
    try {
      await upsertMcpServer({
        recipeId: preset.recipe.id,
        name: t(preset.recipe.titleKey),
        transport: preset.recipe.transport,
        credentialIds: preset.credentialIds.filter(Boolean),
        rootPath: preset.recipe.needsRoot ? preset.rootPath : undefined,
        enabled: true,
      });
      notify({ titleKey: 'settings.notify.mcpSaved', variant: 'success' });
      setPreset(null);
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setSavingPreset(false);
    }
  }

  async function saveCustom() {
    if (!custom?.name.trim()) return;
    setSavingCustom(true);
    try {
      await upsertMcpServer({
        name: custom.name.trim(),
        transport: custom.transport,
        command: custom.transport === 'stdio' ? custom.command : undefined,
        args: custom.transport === 'stdio' ? custom.args.split(/\s+/).filter(Boolean) : undefined,
        url: custom.transport === 'http' ? custom.url : undefined,
        enabled: false,
      });
      notify({ titleKey: 'settings.notify.mcpSaved', variant: 'success' });
      setCustom(null);
    } catch {
      notify({ titleKey: 'settings.notify.saveError', variant: 'error' });
    } finally {
      setSavingCustom(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <SectionHeader title={t('settings.nav.mcp')} description={t('settings.mcp.lead')} />
      <div className="flex justify-end">
        <Button type="button" variant="outline" onClick={() => setCustom(emptyCustom())}>
          {t('settings.mcp.customCreate')}
        </Button>
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium">{t('settings.mcp.recipes')}</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {recipes.map((recipe) => {
            const added = configuredRecipeIds.has(recipe.id);
            return (
              <div key={recipe.id} className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="text-sm font-medium">{t(recipe.titleKey)}</p>
                  <p className="text-xs text-muted-foreground">{recipe.transport}</p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={added ? 'secondary' : 'outline'}
                  disabled={added}
                  onClick={() =>
                    setPreset({
                      recipe,
                      credentialIds: recipe.credentialKinds.map(() => ''),
                      rootPath: '',
                    })
                  }
                >
                  {added ? t('settings.mcp.added') : t('settings.mcp.enable')}
                </Button>
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium">{t('settings.mcp.servers')}</h2>
        {servers.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('settings.mcp.empty')}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('settings.credentials.name')}</TableHead>
                <TableHead>{t('settings.mcp.transport')}</TableHead>
                <TableHead>{t('settings.mcp.enabled')}</TableHead>
                <TableHead>{t('settings.mcp.status')}</TableHead>
                <TableHead className="text-right">{t('settings.common.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {servers.map((server) => (
                <TableRow key={server.id}>
                  <TableCell>
                    <div className="font-medium">{server.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {server.recipeId ?? t('settings.mcp.custom')}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{server.transport}</Badge>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={server.enabled}
                      onCheckedChange={(checked) =>
                        void setMcpEnabled(server.id, checked).then(() =>
                          notify({ titleKey: 'settings.notify.mcpSaved', variant: 'success' }),
                        )
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Badge variant={server.status === 'ok' ? 'default' : 'secondary'}>
                      {t(`settings.mcp.statusName.${server.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="space-x-2 text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={pingingId === server.id}
                      onClick={() => {
                        setPingingId(server.id);
                        void pingMcpServer(server.id)
                          .then((result) =>
                            notify({
                              titleKey: result.messageKey ?? 'settings.mcp.pingOk',
                              variant: result.status === 'ok' ? 'success' : 'warning',
                            }),
                          )
                          .finally(() => setPingingId(null));
                      }}
                    >
                      {t('settings.mcp.probe')}
                    </Button>
                    {!server.recipeId ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => setDeleteId(server.id)}>
                        {t('settings.common.delete')}
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog open={preset !== null} onOpenChange={(open) => !open && setPreset(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{preset ? t(preset.recipe.titleKey) : t('settings.mcp.enable')}</DialogTitle>
            <DialogDescription>{t('settings.mcp.presetHint')}</DialogDescription>
          </DialogHeader>
          {preset?.recipe.id === 'office' ? (
            <Alert>
              <AlertDescription>{t('settings.mcp.officeHint')}</AlertDescription>
            </Alert>
          ) : null}
          {preset?.recipe.credentialKinds.map((kind, index) => (
            <div key={`${kind}-${index}`} className="grid gap-1.5">
              <Label>{t(`settings.credentials.kindName.${kind}`)}</Label>
              <Select
                value={preset.credentialIds[index] || 'none'}
                onValueChange={(value) => {
                  const next = [...preset.credentialIds];
                  next[index] = value === 'none' ? '' : value;
                  setPreset({ ...preset, credentialIds: next });
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('settings.helpChat.credentialEmpty')}</SelectItem>
                  {credentials
                    .filter((item) => item.kind === (kind as CredentialKind))
                    .map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          ))}
          {preset?.recipe.needsRoot ? (
            <div className="grid gap-1.5">
              <Label htmlFor="mcp-root">{t('settings.mcp.rootPath')}</Label>
              <Input
                id="mcp-root"
                value={preset.rootPath}
                onChange={(event) => setPreset({ ...preset, rootPath: event.target.value })}
              />
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPreset(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button type="button" onClick={() => void savePreset()} loading={savingPreset}>
              {t('settings.common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={custom !== null} onOpenChange={(open) => !open && setCustom(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{t('settings.mcp.customCreate')}</DialogTitle>
            <DialogDescription>{t('settings.mcp.untrusted')}</DialogDescription>
          </DialogHeader>
          {custom ? (
            <div className="grid gap-3">
              <Alert>
                <AlertDescription>{t('settings.mcp.untrusted')}</AlertDescription>
              </Alert>
              <div className="grid gap-1.5">
                <Label htmlFor="custom-name">{t('settings.credentials.name')}</Label>
                <Input
                  id="custom-name"
                  value={custom.name}
                  onChange={(event) => setCustom({ ...custom, name: event.target.value })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label>{t('settings.mcp.transport')}</Label>
                <Select
                  value={custom.transport}
                  onValueChange={(value) => setCustom({ ...custom, transport: value as McpTransport })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stdio">stdio</SelectItem>
                    <SelectItem value="http">http</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {custom.transport === 'stdio' ? (
                <>
                  <div className="grid gap-1.5">
                    <Label htmlFor="custom-cmd">{t('settings.mcp.command')}</Label>
                    <Input
                      id="custom-cmd"
                      value={custom.command}
                      onChange={(event) => setCustom({ ...custom, command: event.target.value })}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="custom-args">{t('settings.mcp.args')}</Label>
                    <Textarea
                      id="custom-args"
                      value={custom.args}
                      onChange={(event) => setCustom({ ...custom, args: event.target.value })}
                    />
                  </div>
                </>
              ) : (
                <div className="grid gap-1.5">
                  <Label htmlFor="custom-url">{t('settings.mcp.url')}</Label>
                  <Input
                    id="custom-url"
                    value={custom.url}
                    onChange={(event) => setCustom({ ...custom, url: event.target.value })}
                  />
                </div>
              )}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCustom(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button type="button" onClick={() => void saveCustom()} loading={savingCustom}>
              {t('settings.common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteId !== null} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{t('settings.mcp.deleteTitle')}</DialogTitle>
            <DialogDescription>{t('settings.mcp.deleteBody')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteId(null)}>
              {t('settings.common.cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              loading={deleting}
              onClick={() => {
                if (!deleteId) return;
                setDeleting(true);
                void deleteMcpServer(deleteId)
                  .then(() => {
                    setDeleteId(null);
                    notify({ titleKey: 'settings.notify.mcpDeleted', variant: 'success' });
                  })
                  .finally(() => setDeleting(false));
              }}
            >
              {t('settings.common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
