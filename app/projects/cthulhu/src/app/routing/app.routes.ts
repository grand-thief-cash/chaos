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
      { path: '**', redirectTo: 'cronjobs' }
    ]
  }
];
