import { Routes } from '@angular/router';
import { AtlasShellComponent } from './pages/atlas-shell.component';
import { AtlasDashboardComponent } from './pages/dashboard.component';
import { GraphExplorerComponent } from './pages/graph-explorer.component';
import { EventImpactComponent } from './pages/event-impact.component';
import { CompanyReviewComponent } from './pages/company-review.component';
import { DocumentManagementComponent } from './pages/document-management.component';

export const ATLAS_ROUTES: Routes = [
  {
    path: '',
    component: AtlasShellComponent,
    data: {
      breadcrumb: 'Atlas',
      menuGroup: { title: 'Atlas KG', icon: 'deployment-unit' },
    },
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        component: AtlasDashboardComponent,
        data: { breadcrumb: 'Dashboard', menu: { label: 'Dashboard', order: 1 } },
      },
      {
        path: 'graph',
        component: GraphExplorerComponent,
        data: { breadcrumb: 'Graph Explorer', menu: { label: 'Graph Explorer', order: 2 } },
      },
      {
        path: 'events',
        component: EventImpactComponent,
        data: { breadcrumb: 'Events & Impact', menu: { label: 'Events & Impact', order: 3 } },
      },
      {
        path: 'company',
        component: CompanyReviewComponent,
        data: { breadcrumb: 'Company Review', menu: { label: 'Company Review', order: 4 } },
      },
      {
        path: 'documents',
        component: DocumentManagementComponent,
        data: { breadcrumb: 'Documents', menu: { label: 'Documents', order: 5 } },
      },
    ],
  },
];

