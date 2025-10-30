import {Component, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ActivatedRoute, Router} from '@angular/router';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {CronjobTaskFormComponent} from '../ui/cronjob-task-form.component';
import {Task} from '../models/cronjob.model';

@Component({
  selector: 'cronjob-task-edit-page',
  standalone: true,
  imports: [CommonModule, CronjobTaskFormComponent],
  template: `<h2>编辑任务</h2>
  <div *ngIf="task; else loadingTpl">
    <cronjob-task-form [value]="task" (save)="update($event)" (cancel)="back()"></cronjob-task-form>
  </div>
  <ng-template #loadingTpl>加载任务中...</ng-template>`
})
export class TaskEditPageComponent implements OnInit {
  task: Task | null = null;
  constructor(private api: CronjobsApiService, private route: ActivatedRoute, private router: Router) {}
  ngOnInit(){
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.api.getTask(id).subscribe({ next: t => this.task = t, error: err => console.error('load task error', err) });
  }
  update(payload: any){
    if(!this.task) return;
    this.api.updateTask(this.task.id, payload).subscribe({
      next: () => this.router.navigate(['/cronjobs/task', this.task!.id]),
      error: err => console.error('update task error', err)
    });
  }
  back(){ this.router.navigate(['/cronjobs/task', this.task?.id]); }
}

