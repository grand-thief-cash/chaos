import {Routes} from '@angular/router';
import {ArtemisShellComponent} from './artemis.component';
// Pages
import {TaskListComponent, TaskUnitsComponent, TaskYamlComponent} from './pages';

export const ARTEMIS_ROUTES: Routes = [
  {
    path: '',
    component: ArtemisShellComponent,
    data: { breadcrumb: 'Artemis', menuGroup: { title: 'Artemis', icon: 'appstore' } },
    children: [
      { path: '', redirectTo: 'tasks', pathMatch: 'full' },
      { path: 'tasks', component: TaskListComponent, data: { breadcrumb: 'Tasks', menu: { label: 'Task List', order: 1 } } },
      { path: 'config', component: TaskYamlComponent, data: { breadcrumb: 'Config', menu: { label: 'Task Config', order: 2 } } },
      { path: 'units', component: TaskUnitsComponent, data: { breadcrumb: 'Units', menu: { label: 'Task Units', order: 3 } } }
    ]
  }
];
