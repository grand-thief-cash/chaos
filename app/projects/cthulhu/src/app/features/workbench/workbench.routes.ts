import { Routes } from '@angular/router';
import { WorkbenchShellComponent } from './pages/workbench-shell.component';
import { MarketDataPageComponent } from './pages/market-data.page';
import { TTradingPageComponent } from './pages/t-trading.page';
import { ValuationMatrixPageComponent } from './pages/valuation-matrix.page';
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
        data: { breadcrumb: 'Feature Platform', menu: { label: 'Feature Platform', order: 4 } },
        children: FEATURE_PLATFORM_ROUTES,
      },
      {
        path: 't-trading',
        component: TTradingPageComponent,
        data: { breadcrumb: '做 T Review', menu: { label: '做 T Review', order: 2 } },
      },
      {
        path: 'valuation-matrix',
        component: ValuationMatrixPageComponent,
        data: { breadcrumb: '估值矩阵', menu: { label: '估值矩阵', order: 3 } },
      },
    ],
  },
];
