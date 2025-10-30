import {Routes} from '@angular/router';
import {CronjobsShellComponent} from './pages/cronjobs-shell.component';
import {TaskListPageComponent} from './pages/task-list.page';
import {TaskDetailPageComponent} from './pages/task-detail.page';
import {TaskCreatePageComponent} from './pages/task-create.page';
import {TaskEditPageComponent} from './pages/task-edit.page';


export const CRONJOBS_ROUTES: Routes = [
  {
    path: '',
    component: CronjobsShellComponent,
    data: { breadcrumb: 'Cron Jobs', menuGroup: { title: 'Cron Jobs', icon: 'clock-circle' } },
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'tasks' },
      { path: 'tasks', component: TaskListPageComponent, data: { breadcrumb: 'Tasks', menu: { label: '任务列表', order: 1 } } },
      { path: 'task/new', component: TaskCreatePageComponent, data: { breadcrumb: 'New Task' } },
      { path: 'task/:id', component: TaskDetailPageComponent, data: { breadcrumb: 'Detail' } },
      { path: 'task/:id/edit', component: TaskEditPageComponent, data: { breadcrumb: 'Edit Task' } }
    ]
  }
];
