import { Routes } from '@angular/router';
import { BiShellComponent } from './pages/bi-shell.component';
import { BiOverviewPageComponent } from './pages/bi-overview.page';
import { CompanyFinancialEntryPageComponent } from './pages/company-financial-entry.page';
import { CompanyFinancialShellPageComponent } from './pages/company-financial-shell.page';
import { FinancialDashboardPageComponent } from './pages/financial-dashboard.page';
import { DupontAnalysisPageComponent } from './pages/dupont-analysis.page';
import { FinancialQualityPageComponent } from './pages/financial-quality.page';
import { FinancialInsightPageComponent } from './pages/financial-insight.page';
import { MetricDictionaryPageComponent } from './pages/metric-dictionary.page';
import { PeerComparisonPageComponent } from './pages/peer-comparison.page';

export const BI_ROUTES: Routes = [
  {
    path: '',
    component: BiShellComponent,
    data: { breadcrumb: 'BI', menuGroup: { title: 'BI', icon: 'line-chart' } },
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'overview' },
      {
        path: 'overview',
        component: BiOverviewPageComponent,
        data: { breadcrumb: 'Overview', menu: { label: '总览', order: 1 } },
      },
      {
        path: 'financial',
        component: CompanyFinancialEntryPageComponent,
        data: { breadcrumb: 'Company Financial', menu: { label: '公司财务', order: 2 } },
      },
      {
        path: 'metrics',
        component: MetricDictionaryPageComponent,
        data: { breadcrumb: 'Metric Dictionary', menu: { label: '指标字典', order: 3 } },
      },
      {
        path: 'financial/compare',
        component: PeerComparisonPageComponent,
        data: { breadcrumb: 'Peer Comparison', menu: { label: '同行对比', order: 4 } },
      },
      {
        path: 'meta',
        children: [
          { path: 'metrics', redirectTo: '/bi/metrics', pathMatch: 'full' },
        ],
      },
      {
        path: 'financial/company/:symbol',
        component: CompanyFinancialShellPageComponent,
        data: { breadcrumb: 'Company' },
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'overview' },
          { path: 'overview', component: FinancialDashboardPageComponent, data: { breadcrumb: 'Overview' } },
          { path: 'dupont', component: DupontAnalysisPageComponent, data: { breadcrumb: 'Dupont' } },
          { path: 'quality', component: FinancialQualityPageComponent, data: { breadcrumb: 'Quality' } },
          { path: 'insight', component: FinancialInsightPageComponent, data: { breadcrumb: 'Insight' } },
        ],
      },
    ],
  },
];


