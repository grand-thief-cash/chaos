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
      {
        path: 'tasks',
        data: { breadcrumb: 'Tasks', menu: { label: '任务列表', order: 1 } },
        children: [
          { path: '', component: TaskListPageComponent },
          { path: 'new', component: TaskCreatePageComponent, data: { breadcrumb: 'New Task' } },
          { path: ':id', component: TaskDetailPageComponent, data: { breadcrumb: 'Detail' }, children: [
            { path: 'runs', children: [
              { path: ':runId', loadComponent: () => import('./pages/run-detail.page').then(m=> m.RunDetailPageComponent), data: { breadcrumb: 'Run Detail' } }
            ] }
          ] },
          { path: ':id/edit', component: TaskEditPageComponent, data: { breadcrumb: 'Edit Task' } }
        ]
      },
      { path: 'runs/active', loadComponent: () => import('./pages/runs-active.page').then(m=> m.RunsActivePageComponent), data: { breadcrumb: 'Active Runs', menu: { label: '活跃运行', order: 2 } } },
      { path: 'runs/summary', loadComponent: () => import('./pages/runs-summary.page').then(m=> m.RunsSummaryPageComponent), data: { breadcrumb: 'Runs Summary', menu: { label: '运行汇总', order: 3 } } },
      { path: 'runs/progress', loadComponent: () => import('./pages/runs-progress.page').then(m=> m.RunsProgressPageComponent), data: { breadcrumb: 'Runs Progress', menu: { label: '运行进度', order: 4 } } },
      { path: 'maintenance', loadComponent: () => import('./pages/maintenance.page').then(m=> m.CronMaintenancePageComponent), data: { breadcrumb: 'Maintenance', menu: { label: '维护', order: 99 } } }
    ]
  }
];
