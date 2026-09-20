# Agentus Network — Frontend

Web-UI-Rahmen (Vite + React) für die lokale Agentnetz-App. Fachmodule hängen in die Registry und die Routen ein. Die UI spricht die Python-API unter `/api` an (Vite-Proxy → `127.0.0.1:8765`).

## Stack

- Vite, React 18, TypeScript `strict`
- React Router (Layout + `<Outlet />`)
- Tailwind CSS + shadcn/ui (New York)
- Lucide, `next-themes` (light / dark / system)
- i18next (`de` Default, `en`, `es`)
- `@xyflow/react` (Dependency + Styles; Editor kommt im Modul-Prompt)
- Zustand (`useAppStore`) für Session, Notifications, UI-Prefs
- TanStack Query für Serverdaten
- Sonner-Toasts über `notify()`

## Scripts

```bash
npm i
npm run dev
npm run typecheck
npm run lint
npm run build
```

Dev-Server: `http://localhost:5173`. API-Proxy: `/api` → `http://127.0.0.1:8765`.

## Umgebung

| Variable | Default | Bedeutung |
|----------|---------|-----------|
| `VITE_API_BASE` | `/api` | Fetch-Basis in `src/api/client.ts` (Vite-Proxy / gleicher Origin im Freeze) |

## i18n

- Dateien: `src/i18n/locales/de.json`, `en.json`, `es.json`
- Sprachenliste: `src/i18n/languages.ts` (`de`, `en`, `es`)
- Keine sichtbaren Strings in Komponenten — nur Keys
- Language-Switcher in Header (`md+`), Burger (`< md`) und Einstellungen → Darstellung
- Locale in `localStorage` (`i18nextLng`), setzt `document.documentElement.lang`
- Notification-Center übersetzt Keys beim Rendern (Sprachwechsel aktualisiert die Liste)

## React Flow

`@xyflow/react` ist installiert. Styles werden in `src/main.tsx` importiert. Den Canvas nicht in der Shell bauen — das macht `frontend_module_agents.md`.

## Zustand + TanStack Query

Zwei Ebenen, nicht vermischen:

1. **Client/Session** — `useAppStore` in `src/store/`
   - Slices: `session.ts` (aktives Netz, `serviceStatus`), `notifications.ts`, `ui.ts` (FAB, Sidebar)
   - Selektoren: `useAppStore((s) => s.activeNetworkId)`
   - Persist nur UI-Prefs (`helpChatFabVisible`, `sidebarCollapsed`) — nicht Theme, Locale, Session
2. **Serverdaten** — `QueryClientProvider` in `App.tsx`, Fetch in `src/api/client.ts`
   - Keys z. B. `['session']`, `['networks']`, `['settings']`
   - JSON camelCase, Vertrag: `prompts/build_prompts/python_backend/python_backend_api.md`

Start / Stopp / Schnellwahl schreiben den Session-Slice und rufen `notify()`. Monitoring/Editor lesen denselben Slice.

## Notifications

```ts
import { notify } from '@/lib/notifications';

notify({
  titleKey: 'notify.runRunning.title',
  descriptionKey: 'notify.runRunning.desc',
  variant: 'success', // success | info | warning | error
  values: { name: 'Demo-Netz' },
  persist: true, // default: Toast + Center; `false` = nur Toast
});
```

Toaster sitzt in der Shell (oben rechts ab `md`, unten Mitte auf schmal). Die Glocke zeigt Unread-Badge, Liste, gelesen und leeren.

## WebView2-Titelleiste / `chromeHost`

`src/lib/chromeHost.ts` beschreibt `minimize`, `maximize`, `restore`, `close`, `isMaximized`, optional `pickFolder`.

- Fehlt `window.chromeHost` (Vite im Browser): Window-Buttons werden nicht gerendert.
- Header-Hintergrund ist Drag-Region (`app-drag`). pywebview/WebView2 zieht am CSS-Selektor `.app-drag`, nicht an `-webkit-app-region`. Buttons, Selects, Glocke, Nav sind `app-no-drag` und liegen nicht in der Drag-Hierarchie.
- Module importieren `chromeHost` nicht.

## Modul in die Registry

1. Ordner `src/modules/<id>/` mit Page-Komponente
2. Eintrag in `src/modules/registry.ts`: `{ id, titleKey, path, icon, component }`
3. i18n-Key unter `nav.*` in `de.json` / `en.json` / `es.json`
4. Sidebar-Reihenfolge: `dashboard`, `network`, `networks`, `monitoring`, `history`
5. `settings` nur im Header (und Burger), nicht doppelt in der Desktop-Sidebar
6. **Nicht** anlegen: `overview`, `runtime`, `stats`, `chat` — Hilfe ist ein FAB (`frontend_module_chat.md`)
