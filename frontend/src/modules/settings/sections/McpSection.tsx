import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { ApiError } from '@/api/client';
import { pickFolderPath } from '@/lib/pickFolder';
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
import type { CredentialKind, McpRecipe, McpServerListItem, McpTransport } from '@/modules/settings/model';
import { isForbiddenDataRoot } from '@/modules/settings/model';
import { SectionHeader } from '@/modules/settings/sections/SectionHeader';

type PresetForm = {
  recipe: McpRecipe;
  serverId?: string;
  name: string;
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

function recipeTitle(t: (key: string, opts?: { defaultValue?: string }) => string, recipe: McpRecipe) {
  return t(`mcp.recipe.${recipe.id}`, { defaultValue: t(recipe.titleKey) });
}

function serverLabel(
  t: (key: string, opts?: { defaultValue?: string }) => string,
  server: McpServerListItem,
) {
  if (server.recipeId) return t(`mcp.recipe.${server.recipeId}`, { defaultValue: server.name });
  return server.name;
}

function notifyKey(err: unknown, fallback: string) {
  if (err instanceof ApiError && err.messageKey) return err.messageKey;
  return fallback;
}

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
  const [savingPreset, setSavingPreset] = useState(false);
  const [savingCustom, setSavingCustom] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [pingingId, setPingingId] = useState<string | null>(null);
  const [pickingRoot, setPickingRoot] = useState(false);

  const serversByRecipe = useMemo(() => {
    const map = new Map<string, McpServerListItem>();
    for (const item of servers) {
      if (item.recipeId && !map.has(item.recipeId)) map.set(item.recipeId, item);
    }
    return map;
  }, [servers]);

  function openPreset(recipe: McpRecipe, existing?: McpServerListItem) {
    const kinds = recipe.credentialKinds ?? [];
    const ids = existing?.credentialIds ?? kinds.map(() => '');
    setPreset({
      recipe,
      serverId: existing?.id,
      name: existing?.name || recipeTitle(t, recipe),
      credentialIds: kinds.map((_, index) => ids[index] ?? ''),
      rootPath: existing?.rootPath ?? '',
    });
  }

  async function savePreset() {
    if (!preset) return;
    const kinds = preset.recipe.credentialKinds ?? [];
    if (kinds.some((_, index) => !preset.credentialIds[index])) {
      notify({ titleKey: 'mcp.credential.required', variant: 'error' });
      return;
    }
    if (preset.recipe.needsRoot && isForbiddenDataRoot(preset.rootPath)) {
      notify({ titleKey: 'mcp.root.invalid', variant: 'error' });
      return;
    }
    setSavingPreset(true);
    try {
      await upsertMcpServer({
        id: preset.serverId,
        recipeId: preset.serverId ? undefined : preset.recipe.id,
        name: preset.name.trim() || recipeTitle(t, preset.recipe),
        transport: preset.recipe.transport,
        credentialIds: preset.credentialIds.filter(Boolean),
        rootPath: preset.recipe.needsRoot ? preset.rootPath : undefined,
        enabled: preset.serverId ? undefined : true,
      });
      notify({ titleKey: 'settings.notify.mcpSaved', variant: 'success' });
      setPreset(null);
    } catch (err) {
      notify({ titleKey: notifyKey(err, 'settings.notify.saveError'), variant: 'error' });
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
    } catch (err) {
      notify({ titleKey: notifyKey(err, 'settings.notify.saveError'), variant: 'error' });
    } finally {
      setSavingCustom(false);
    }
  }

  async function pickRoot() {
    if (!preset) return;
    setPickingRoot(true);
    try {
      const path = await pickFolderPath();
      if (path) setPreset({ ...preset, rootPath: path });
    } finally {
      setPickingRoot(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <SectionHeader title={t('settings.nav.mcp')} description={t('settings.mcp.lead')} />
      <p className="text-sm text-muted-foreground">{t('settings.mcp.credentialsLead')}</p>
      <div className="flex justify-end">
        <Button type="button" variant="outline" onClick={() => setCustom(emptyCustom())}>
          {t('settings.mcp.customCreate')}
        </Button>
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium">{t('settings.mcp.recipes')}</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {recipes.map((recipe) => {
            const existing = serversByRecipe.get(recipe.id);
            return (
              <div key={recipe.id} className="flex flex-col gap-2 rounded-md border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{recipeTitle(t, recipe)}</p>
                    <p className="text-xs text-muted-foreground">{t(`settings.mcp.hint.${recipe.id}`)}</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={existing ? 'secondary' : 'outline'}
                    onClick={() => openPreset(recipe, existing)}
                  >
                    {existing ? t('settings.common.edit') : t('settings.mcp.enable')}
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="secondary">{recipe.transport}</Badge>
                  {recipe.runtime && recipe.runtime !== 'none' ? (
                    <Badge variant="secondary">{recipe.runtime}</Badge>
                  ) : null}
                  {(recipe.credentialKinds ?? []).length === 0 ? (
                    <Badge variant="outline">{t('settings.mcp.needsNone')}</Badge>
                  ) : (
                    recipe.credentialKinds.map((kind) => (
                      <Badge key={kind} variant="outline">
                        {t(`settings.credentials.kindName.${kind}`)}
                      </Badge>
                    ))
                  )}
                  {recipe.needsRoot ? <Badge variant="outline">{t('settings.mcp.needsRoot')}</Badge> : null}
                </div>
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
              {servers.map((server) => {
                const recipe = recipes.find((item) => item.id === server.recipeId);
                return (
                  <TableRow key={server.id}>
                    <TableCell>
                      <div className="font-medium">{serverLabel(t, server)}</div>
                      <div className="text-xs text-muted-foreground">
                        {server.recipeId ? t(`mcp.recipe.${server.recipeId}`) : t('settings.mcp.custom')}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{server.transport}</Badge>
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={server.enabled}
                        onCheckedChange={(checked) =>
                          void setMcpEnabled(server.id, checked)
                            .then(() => notify({ titleKey: 'settings.notify.mcpSaved', variant: 'success' }))
                            .catch((err) =>
                              notify({ titleKey: notifyKey(err, 'settings.notify.saveError'), variant: 'error' }),
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
                      {recipe ? (
                        <Button type="button" size="sm" variant="ghost" onClick={() => openPreset(recipe, server)}>
                          {t('settings.common.edit')}
                        </Button>
                      ) : null}
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
                            .catch((err) =>
                              notify({ titleKey: notifyKey(err, 'settings.mcp.pingError'), variant: 'error' }),
                            )
                            .finally(() => setPingingId(null));
                        }}
                      >
                        {t('settings.mcp.probe')}
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => setDeleteId(server.id)}>
                        {t('settings.common.delete')}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog open={preset !== null} onOpenChange={(open) => !open && setPreset(null)}>
        <DialogContent closeLabel={t('settings.common.close')}>
          <DialogHeader>
            <DialogTitle>{preset ? recipeTitle(t, preset.recipe) : t('settings.mcp.enable')}</DialogTitle>
            <DialogDescription>
              {preset ? t(`settings.mcp.hint.${preset.recipe.id}`) : t('settings.mcp.presetHint')}
            </DialogDescription>
          </DialogHeader>
          {preset?.recipe.id === 'office' ? (
            <Alert>
              <AlertDescription>{t('settings.mcp.officeHint')}</AlertDescription>
            </Alert>
          ) : null}
          {preset && (preset.recipe.runtime ?? 'none') !== 'none' ? (
            <p className="text-xs text-muted-foreground">
              {t('settings.mcp.runtimeNeed', { runtime: preset.recipe.runtime })}
            </p>
          ) : null}
          {preset?.recipe.credentialKinds.length ? (
            <p className="text-xs text-muted-foreground">
              {t('settings.mcp.credentialHelp')}{' '}
              <Link to="/settings#credentials" className="underline">
                {t('settings.nav.credentials')}
              </Link>
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">{t('settings.mcp.needsNone')}</p>
          )}
          {preset?.recipe.credentialKinds.map((kind, index) => {
            const matching = credentials.filter((item) => item.kind === (kind as CredentialKind));
            return (
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
                    {matching.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t(`settings.credentials.kindHint.${kind}`)}</p>
                {matching.length === 0 ? (
                  <p className="text-xs text-destructive">{t('settings.mcp.noCredentialOfKind')}</p>
                ) : null}
              </div>
            );
          })}
          {preset?.recipe.needsRoot ? (
            <div className="grid gap-1.5">
              <Label htmlFor="mcp-root">{t('settings.mcp.rootPath')}</Label>
              <div className="flex gap-2">
                <Input
                  id="mcp-root"
                  value={preset.rootPath}
                  spellCheck={false}
                  className="min-w-0 font-mono text-xs"
                  onChange={(event) => setPreset({ ...preset, rootPath: event.target.value })}
                />
                <Button type="button" size="sm" variant="outline" loading={pickingRoot} onClick={() => void pickRoot()}>
                  {t('settings.mcp.pickRoot')}
                </Button>
              </div>
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
