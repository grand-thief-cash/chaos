import { Routes } from '@angular/router';

export const FEATURE_PLATFORM_ROUTES: Routes = [
  { path: '', redirectTo: 'registry', pathMatch: 'full' },
  {
    path: 'registry',
    loadComponent: () => import('./pages/registry-page.component').then((m) => m.RegistryPageComponent),
    data: { breadcrumb: 'Registry', menu: { label: 'Registry', order: 1 } },
  },
  {
    path: 'definitions/:featureCode',
    loadComponent: () => import('./pages/definition-detail-page.component').then((m) => m.DefinitionDetailPageComponent),
    data: { breadcrumb: 'Definition', menu: { label: 'Definition', hide: true } },
  },
  {
    path: 'lineage/:featureCode',
    loadComponent: () => import('./pages/lineage-page.component').then((m) => m.LineagePageComponent),
    data: { breadcrumb: 'Lineage', menu: { label: 'Lineage', hide: true } },
  },
  {
    path: 'runs',
    loadComponent: () => import('./pages/runs-page.component').then((m) => m.RunsPageComponent),
    data: { breadcrumb: 'Runs', menu: { label: 'Runs', order: 2 } },
  },
  {
    path: 'runs/:runId',
    loadComponent: () => import('./pages/run-detail-page.component').then((m) => m.RunDetailPageComponent),
    data: { breadcrumb: 'Run Detail', menu: { label: 'Run Detail', hide: true } },
  },
  {
    path: 'values',
    loadComponent: () => import('./pages/values-page.component').then((m) => m.ValuesPageComponent),
    data: { breadcrumb: 'Values', menu: { label: 'Values', order: 3 } },
  },
  {
    path: 'compute',
    loadComponent: () => import('./pages/manual-compute-page.component').then((m) => m.ManualComputePageComponent),
    data: { breadcrumb: 'Manual Compute', menu: { label: 'Manual Compute', order: 4 } },
  },
];
