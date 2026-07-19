import { Routes } from '@angular/router';
import { WorkbenchShellComponent } from './pages/workbench-shell.component';
import { MarketDataPageComponent } from './pages/market-data.page';
import { FeaturePlatformShellComponent } from '../feature-platform/pages/feature-platform-shell.component';
import { FEATURE_PLATFORM_ROUTES } from '../feature-platform/feature-platform.routes';

export const WORKBENCH_ROUTES: Routes = [
  {
    path: '',
    component: WorkbenchShellComponent,
    data: {
      breadcrumb: 'Workbench',
      menuGroup: { title: 'Workbench', icon: 'line-chart' },
    },
    children: [
      { path: '', redirectTo: 'market-data', pathMatch: 'full' },
      {
        path: 'market-data',
        component: MarketDataPageComponent,
        data: { breadcrumb: 'Market Data', menu: { label: 'Market Data', order: 1 } },
      },
      {
        path: 'features',
        component: FeaturePlatformShellComponent,
        data: { breadcrumb: 'Feature Platform', menu: { label: 'Feature Platform', order: 2 } },
        children: FEATURE_PLATFORM_ROUTES,
      },
    ],
  },
];
