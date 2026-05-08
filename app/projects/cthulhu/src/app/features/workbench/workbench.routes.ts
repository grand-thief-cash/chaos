import { Routes } from '@angular/router';
import { WorkbenchShellComponent } from './pages/workbench-shell.component';
import { WorkbenchResearchPageComponent } from './pages/workbench-research.page';
import { MarketDataPageComponent } from './pages/market-data.page';
import { IndustryExplorerPageComponent } from './pages/industry-explorer.page';
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
      { path: '', redirectTo: 'research', pathMatch: 'full' },
      {
        path: 'research',
        component: WorkbenchResearchPageComponent,
        data: { breadcrumb: 'Strategy Research', menu: { label: 'Strategy Research', order: 1 } },
      },
      {
        path: 'market-data',
        component: MarketDataPageComponent,
        data: { breadcrumb: 'Market Data', menu: { label: 'Market Data', order: 2 } },
      },
      {
        path: 'industry',
        component: IndustryExplorerPageComponent,
        data: { breadcrumb: 'Industry Explorer', menu: { label: 'Industry Explorer', order: 3 } },
      },
      {
        path: 'factors',
        component: FactorEngineComponent,
        data: { breadcrumb: 'Factor Engine', menu: { label: 'Factor Engine', order: 4 } },
      },
      {
        path: 'regime',
        component: RegimeEngineComponent,
        data: { breadcrumb: 'Regime Engine', menu: { label: 'Regime Engine', order: 5 } },
      },
    ],
  },
];
