import { Routes } from '@angular/router';
import { WorkbenchShellComponent } from './pages/workbench-shell.component';
import { WorkbenchResearchPageComponent } from './pages/workbench-research.page';
import { MarketDataPageComponent } from './pages/market-data.page';

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
    ],
  },
];
