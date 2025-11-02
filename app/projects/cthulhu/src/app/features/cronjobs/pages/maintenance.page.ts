// Maintenance page
import {Component} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzFormModule} from 'ng-zorro-antd/form';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';

@Component({
  selector: 'cron-maintenance-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzFormModule, NzInputModule, NzButtonModule, NzMessageModule],
  template: `
    <div class="maintenance-page">
      <h2>运行记录维护</h2>
      <div class="actions">
        <button nz-button nzType="default" (click)="refreshCache()">刷新任务缓存</button>
      </div>
      <div class="cleanup-section">
        <h3>清理运行记录</h3>
        <form (ngSubmit)="submitCleanup()">
          <label>模式:
            <select [(ngModel)]="mode" name="mode">
              <option value="age">按年龄(age)</option>
              <option value="count">按保留数量(count)</option>
              <option value="ids">按指定ID(ids)</option>
            </select>
          </label>
          <div *ngIf="mode==='age'">
            <label>Task ID (可选): <input nz-input [(ngModel)]="taskId" name="taskId" /></label>
            <label>最大年龄秒: <input nz-input type="number" [(ngModel)]="maxAgeSeconds" name="maxAgeSeconds" /></label>
          </div>
          <div *ngIf="mode==='count'">
            <label>Task ID (可选): <input nz-input [(ngModel)]="taskId" name="taskId2" /></label>
            <label>保留数量 keep: <input nz-input type="number" [(ngModel)]="keep" name="keep" /></label>
          </div>
            <div *ngIf="mode==='ids'">
              <label>ID 列表(英文逗号): <input nz-input [(ngModel)]="idsRaw" name="idsRaw" /></label>
            </div>
          <button nz-button nzType="primary" type="submit">执行清理</button>
        </form>
      </div>
      <div *ngIf="lastCleanup" class="result">已删除: {{lastCleanup?.deleted}}</div>
    </div>
  `,
  styles: [`
    .maintenance-page { padding:24px; background:#fff; border-radius:8px; }
    form { display:flex; flex-direction:column; gap:8px; max-width:400px; }
    label { display:flex; flex-direction:column; font-weight:600; }
    .result { margin-top:12px; font-weight:600; }
  `]
})
export class CronMaintenancePageComponent {
  mode: 'age' | 'count' | 'ids' = 'age';
  taskId: number | null = null;
  maxAgeSeconds = 86400;
  keep = 1000;
  idsRaw = '';
  lastCleanup: any | null = null;
  constructor(private api: CronjobsApiService, private msg: NzMessageService) {}
  refreshCache(){ this.api.refreshCache().subscribe({ next: ()=> this.msg.success('刷新成功'), error: ()=> this.msg.error('刷新失败') }); }
  submitCleanup(){
    let payload: any = { mode: this.mode };
    if(this.mode==='age'){ payload.max_age_seconds = this.maxAgeSeconds; if(this.taskId) payload.task_id = this.taskId; }
    else if(this.mode==='count'){ payload.keep = this.keep; if(this.taskId) payload.task_id = this.taskId; }
    else if(this.mode==='ids'){ payload.ids = this.idsRaw.split(',').map(s=> Number(s.trim())).filter(n=> !isNaN(n)); }
    this.api.cleanupRuns(payload).subscribe({ next: r=> { this.lastCleanup = r; this.msg.success('清理完成'); }, error: ()=> this.msg.error('清理失败') });
  }
}

