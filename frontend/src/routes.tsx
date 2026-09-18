import { Navigate, createBrowserRouter } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { NotFoundPage } from '@/components/layout/NotFoundPage';
import { HistoryPage } from '@/modules/history';
import { NetworkPage } from '@/modules/network';
import { ALL_MODULES } from '@/modules/registry';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      ...ALL_MODULES.map((module) => ({
        path: module.path.replace(/^\//, ''),
        element: <module.component />,
      })),
      { path: 'network/:id', element: <NetworkPage /> },
      { path: 'history/:runId', element: <HistoryPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
