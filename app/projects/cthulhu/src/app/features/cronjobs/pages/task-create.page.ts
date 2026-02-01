import {Component} from '@angular/core';
import {CommonModule} from '@angular/common';
import {Router} from '@angular/router';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {CronjobTaskFormComponent} from '../ui/cronjob-task-form.component';

@Component({
  selector: 'cronjob-task-create-page',
  standalone: true,
  imports: [CommonModule, CronjobTaskFormComponent],
  template: `<h2>新建任务</h2>
  <cronjob-task-form [value]="template" (save)="create($event)" (cancel)="back()" [api]="api"></cronjob-task-form>`
})
export class TaskCreatePageComponent {
  template: any = history.state?.template || null;
  api: CronjobsApiService;
  constructor(api: CronjobsApiService, private router: Router) { this.api = api; }
  create(payload: any){
    this.api.createTask(payload).subscribe({
      next: (res)=> this.router.navigate(['/cronjobs/tasks', res.id]),
      error: err => console.error('create task error', err)
    });
  }
  back(){ this.router.navigate(['/cronjobs/tasks']); }
}
// 传递 api 给表单组件以便其拉取 target_service 列表
