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
  <cronjob-task-form (save)="create($event)" (cancel)="back()"></cronjob-task-form>`
})
export class TaskCreatePageComponent {
  constructor(private api: CronjobsApiService, private router: Router) {}
  create(payload: any){
    this.api.createTask(payload).subscribe({
      next: (res)=> this.router.navigate(['/cronjobs/task', res.id]),
      error: err => console.error('create task error', err)
    });
  }
  back(){ this.router.navigate(['/cronjobs/tasks']); }
}

