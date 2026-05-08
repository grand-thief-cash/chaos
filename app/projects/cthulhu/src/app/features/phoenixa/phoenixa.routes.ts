import {Routes} from '@angular/router';
import {PhoenixAShellComponent} from './phoenixa.component';
import {BufferStatsComponent} from './pages';

export const PHOENIXA_ROUTES: Routes = [
  {
    path: '',
    component: PhoenixAShellComponent,
    data: { breadcrumb: 'PhoenixA', menuGroup: { title: 'PhoenixA', icon: 'database' } },
    children: [
      { path: '', redirectTo: 'buffer', pathMatch: 'full' },
      { path: 'buffer', component: BufferStatsComponent, data: { breadcrumb: 'Write Buffer', menu: { label: 'Write Buffer', order: 1 } } }
    ]
  }
];

