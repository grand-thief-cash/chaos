import { Routes } from '@angular/router';
import { BiShellComponent } from './pages/bi-shell.component';
import { StockListPageComponent } from './pages/stock-list.page';
import { CompanyOverviewPageComponent } from './pages/company-overview.page';
import { RawDataExplorerPageComponent } from './pages/raw-data-explorer.page';
import { MetricDictionaryPageComponent } from './pages/metric-dictionary.page';
import { DupontAnalysisPageComponent } from './pages/dupont-analysis.page';
import { FinancialSummaryPageComponent } from './pages/financial-summary.page';
import { ProfitabilityAnalysisPageComponent } from './pages/profitability-analysis.page';
import { FinancialAbilityPlaceholderPageComponent } from './pages/financial-ability-placeholder.page';

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
        path: 'company/:security_id',
        component: CompanyOverviewPageComponent,
        data: { breadcrumb: 'Company' },
      },
      {
        path: 'company/:security_id/raw/:dataset/:type',
        component: RawDataExplorerPageComponent,
        data: { breadcrumb: 'Raw Data' },
      },
      {
        path: 'financial-summary',
        component: FinancialSummaryPageComponent,
        data: { breadcrumb: 'Financial Summary', menu: { label: '财务综合分析', order: 2 } },
      },
      {
        path: 'financial-ability',
        data: { breadcrumb: 'Financial Ability', menu: { label: '财务能力分析', order: 3 } },
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'profitability' },
          {
            path: 'profitability',
            component: ProfitabilityAnalysisPageComponent,
            data: { breadcrumb: 'Profitability Analysis', menu: { label: '盈利能力分析', order: 1 } },
          },
          {
            path: 'growth',
            component: FinancialAbilityPlaceholderPageComponent,
            data: { breadcrumb: 'Growth Ability Analysis', title: '发展能力分析', menu: { label: '发展能力分析', order: 2 } },
          },
          {
            path: 'operation',
            component: FinancialAbilityPlaceholderPageComponent,
            data: { breadcrumb: 'Operation Ability Analysis', title: '营运能力分析', menu: { label: '营运能力分析', order: 3 } },
          },
          {
            path: 'solvency',
            component: FinancialAbilityPlaceholderPageComponent,
            data: { breadcrumb: 'Solvency Ability Analysis', title: '偿债能力分析', menu: { label: '偿债能力分析', order: 4 } },
          },
        ],
      },
      {
        path: 'dupont',
        component: DupontAnalysisPageComponent,
        data: { breadcrumb: 'Dupont Analysis', menu: { label: '杜邦分析', order: 2 } },
      },
      {
        path: 'metrics',
        component: MetricDictionaryPageComponent,
        data: { breadcrumb: 'Metric Dictionary', menu: { label: '指标字典', order: 2 } },
      },
    ],
  },
];
