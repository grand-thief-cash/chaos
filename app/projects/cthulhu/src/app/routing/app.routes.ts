import {Routes} from '@angular/router';
import {AppLayoutComponent} from '../shared/ui/layout/app-layout.component';

export const routes: Routes = [
  {
    path: '',
    component: AppLayoutComponent,
    data: { breadcrumb: 'Home' },
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'cronjobs' },
      {
        path: 'cronjobs',
        loadChildren: () => import('../features/cronjobs/cronjobs.routes').then(m => m.CRONJOBS_ROUTES)
      },
      {
        path: 'artemis',
        loadChildren: () => import('../features/artemis/artemis.routes').then(m => m.ARTEMIS_ROUTES)
      },
      {
        path: 'phoenixa',
        loadChildren: () => import('../features/phoenixa/phoenixa.routes').then(m => m.PHOENIXA_ROUTES)
      },
      {
        path: 'workbench',
        loadChildren: () => import('../features/workbench/workbench.routes').then(m => m.WORKBENCH_ROUTES)
      },
      {
        path: 'atlas',
        loadChildren: () => import('../features/atlas/atlas.routes').then(m => m.ATLAS_ROUTES)
      },
      {
        path: 'bi',
        loadChildren: () => import('../features/bi/bi.routes').then(m => m.BI_ROUTES)
      },
      { path: '**', redirectTo: 'cronjobs' }
    ]
  }
];
