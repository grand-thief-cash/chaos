import { Routes } from '@angular/router';
import { WorkbenchShellComponent } from './pages/workbench-shell.component';
import { MarketDataPageComponent } from './pages/market-data.page';
import { FactorEngineComponent } from './pages/factor-engine.page';
import { RegimeEngineComponent } from './pages/regime-engine.page';

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
        path: 'factors',
        component: FactorEngineComponent,
        data: { breadcrumb: 'Factor Engine', menu: { label: 'Factor Engine', order: 2 } },
      },
      {
        path: 'regime',
        component: RegimeEngineComponent,
        data: { breadcrumb: 'Regime Engine', menu: { label: 'Regime Engine', order: 3 } },
      },
    ],
  },
];
