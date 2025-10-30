import {Component, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsStore} from '../state/cronjobs.store';
import {RouterLink} from '@angular/router';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzPopconfirmModule} from 'ng-zorro-antd/popconfirm';
import {NzPaginationModule} from 'ng-zorro-antd/pagination';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {FormsModule} from '@angular/forms';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';

@Component({
  selector: 'cron-task-list-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NzTableModule, NzButtonModule, NzBadgeModule, NzPopconfirmModule, NzPaginationModule, NzInputModule, NzSelectModule, NzMessageModule],
  template: `
  <div *ngIf="store.loadingTasks(); else listTpl" class="loading">加载中...</div>
  <ng-template #listTpl>
    <div class="header">
      <h2>定时任务列表</h2>
      <div class="actions">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
        <button nz-button nzType="default" (click)="refreshCache()">刷新缓存</button>
        <button nz-button nzType="primary" [routerLink]="['/cronjobs/task','new']">新建任务</button>
      </div>
    </div>
    <div class="filters">
      <input nz-input placeholder="搜索名称" [(ngModel)]="search" (ngModelChange)="onSearch($event)" />
      <nz-select [(ngModel)]="status" (ngModelChange)="onStatus($event)" style="width:140px;" nzAllowClear>
        <nz-option nzValue="ALL" nzLabel="全部状态"></nz-option>
        <nz-option nzValue="ENABLED" nzLabel="启用"></nz-option>
        <nz-option nzValue="DISABLED" nzLabel="禁用"></nz-option>
      </nz-select>
    </div>
    <nz-table [nzData]="store.pagedTasks()" nzBordered *ngIf="store.filteredTasks().length; else emptyTpl">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>Cron</th>
          <th>状态</th>
          <th>并发</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let t of store.pagedTasks()">
          <td>{{t.id}}</td>
          <td><a [routerLink]="['/cronjobs/task', t.id]">{{t.name}}</a></td>
          <td>{{t.cron_expr}}</td>
          <td>
            <nz-badge [nzStatus]="t.status==='ENABLED' ? 'success' : 'default'" [nzText]="t.status==='ENABLED'?'启用':'禁用'"></nz-badge>
          </td>
          <td>{{t.max_concurrency}}</td>
          <td class="ops">
            <button nz-button nzSize="small" (click)="toggle(t)">{{t.status==='ENABLED'?'禁用':'启用'}}</button>
            <button nz-button nzSize="small" (click)="trigger(t)">触发</button>
            <button nz-button nzSize="small" [routerLink]="['/cronjobs/task', t.id, 'edit']">编辑</button>
            <button nz-button nzSize="small" nzDanger nz-popconfirm nzPopconfirmTitle="确认删除该任务?" (nzOnConfirm)="remove(t)">删除</button>
          </td>
        </tr>
      </tbody>
    </nz-table>
    <ng-template #emptyTpl><div class="empty">暂无任务</div></ng-template>
    <div class="pager" *ngIf="store.filteredTasks().length">
      <nz-pagination [nzTotal]="store.filteredTasks().length" [nzPageIndex]="store.taskPageIndex()" [nzPageSize]="store.taskPageSize()"
        (nzPageIndexChange)="onPage($event)" (nzPageSizeChange)="onPageSize($event)" [nzShowSizeChanger]="true"></nz-pagination>
    </div>
  </ng-template>
  `,
  styles: [`
    .header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
    .actions { display:flex; gap:8px; }
    .ops { display:flex; gap:4px; flex-wrap:wrap; }
    .empty { padding: 32px; text-align:center; color:#888; }
    .pager { margin-top: 16px; display:flex; justify-content:center; }
    .filters { display:flex; gap:8px; margin-bottom: 12px; }
  `]
})
export class TaskListPageComponent implements OnInit {
  search = '';
  status = 'ALL';
  constructor(public store: CronjobsStore, private msg: NzMessageService) {}
  ngOnInit(){ this.store.loadTasks(); }
  reload(){ this.store.loadTasks(true); }
  toggle(t: any){
    const obs = t.status==='ENABLED'? this.store.disable(t.id): this.store.enable(t.id);
    obs.subscribe(()=> this.store.loadTasks(true));
  }
  trigger(t: any){ this.store.trigger(t.id).subscribe(()=> this.store.loadRuns(t.id, true)); }
  refreshCache(){ this.store.refreshCache().subscribe(()=> this.store.loadTasks(true)); }
  remove(t: any){ this.store.delete(t.id).subscribe({ next: ()=> { this.msg.success('删除成功');
    this.store.loadTasks(true); }, error: ()=> this.msg.error('删除失败'), }); }
  onSearch(v: string){ this.store.setTaskSearch(v||''); }
  onStatus(v: any){ this.store.setTaskStatusFilter(v||'ALL'); }
  onPage(i: number){ this.store.setTaskPage(i); }
  onPageSize(size: number){ this.store.setTaskPageSize(size); }
}
