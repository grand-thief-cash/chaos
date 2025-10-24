import {Routes} from '@angular/router';
import {CronjobsShellComponent} from "./pages/cronjobs-shell.component";
import {CronjobsOverviewComponent} from "./pages/cronjobs-overview.component";


export const CRONJOBS_ROUTES: Routes = [
  {
    path: '',
    component: CronjobsShellComponent,
    data: {
      breadcrumb: 'Cron Jobs', menuGroup: { title: 'Cron Jobs', icon: 'user' }
    },
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'overview' },
      {
        path: 'overview',
        component: CronjobsOverviewComponent,
        data: { breadcrumb: 'Overview', menu: { label: 'Overview', order: 1 } }
      }
    ]
  }
];
