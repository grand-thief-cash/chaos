import { Routes } from '@angular/router';
import { BiShellComponent } from './pages/bi-shell.component';
import { StockListPageComponent } from './pages/stock-list.page';
import { CompanyOverviewPageComponent } from './pages/company-overview.page';
import { RawDataExplorerPageComponent } from './pages/raw-data-explorer.page';
import { MetricDictionaryPageComponent } from './pages/metric-dictionary.page';

export const BI_ROUTES: Routes = [
  {
    path: '',
    component: BiShellComponent,
    data: { breadcrumb: 'BI', menuGroup: { title: 'BI', icon: 'line-chart' } },
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'stocks' },
      {
        path: 'stocks',
        component: StockListPageComponent,
        data: { breadcrumb: 'Stock List', menu: { label: '股票列表', order: 1 } },
      },
      {
        path: 'company/:symbol',
        component: CompanyOverviewPageComponent,
        data: { breadcrumb: 'Company' },
      },
      {
        path: 'company/:symbol/raw/:dataset/:type',
        component: RawDataExplorerPageComponent,
        data: { breadcrumb: 'Raw Data' },
      },
      {
        path: 'metrics',
        component: MetricDictionaryPageComponent,
        data: { breadcrumb: 'Metric Dictionary', menu: { label: '指标字典', order: 2 } },
      },
    ],
  },
];
