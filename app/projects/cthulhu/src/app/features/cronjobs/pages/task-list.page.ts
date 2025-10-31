import {Component, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsStore} from '../state/cronjobs.store';
import {Router, RouterLink} from '@angular/router';
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
        <button nz-button nzType="default" (click)="toggleFilters()">{{showFilters? '收起筛选':'展开筛选'}}</button>
        <button nz-button nzType="default" (click)="refreshCache()">刷新缓存</button>
        <button nz-button nzType="primary" [routerLink]="['/cronjobs/tasks','new']">新建任务</button>
      </div>
    </div>
    <div class="filters" *ngIf="showFilters">
      <div class="filter-grid">
        <div class="f-item">
          <label>名称</label>
          <input nz-input placeholder="模糊匹配" [(ngModel)]="search" />
        </div>
        <div class="f-item">
          <label>描述</label>
          <input nz-input placeholder="模糊匹配" [(ngModel)]="desc" />
        </div>
        <div class="f-item">
          <label>状态</label>
          <nz-select [(ngModel)]="status" nzAllowClear nzPlaceHolder="全部" style="width:100%">
            <nz-option nzValue="ALL" nzLabel="全部"></nz-option>
            <nz-option nzValue="ENABLED" nzLabel="启用"></nz-option>
            <nz-option nzValue="DISABLED" nzLabel="禁用"></nz-option>
          </nz-select>
        </div>
        <div class="f-item wide">
          <label>创建时间</label>
          <div class="range">
            <input nz-input type="datetime-local" [(ngModel)]="createdFrom" />
            <span class="dash">-</span>
            <input nz-input type="datetime-local" [(ngModel)]="createdTo" />
          </div>
        </div>
        <div class="f-item wide">
          <label>更新时间</label>
            <div class="range">
              <input nz-input type="datetime-local" [(ngModel)]="updatedFrom" />
              <span class="dash">-</span>
              <input nz-input type="datetime-local" [(ngModel)]="updatedTo" />
            </div>
        </div>
      </div>
      <div class="filter-actions">
        <button nz-button nzType="primary" (click)="apply()">查询</button>
        <button nz-button nzType="default" (click)="clearFilters()">重置</button>
      </div>
    </div>
    <nz-table [nzData]="store.pagedTasks()" nzBordered *ngIf="store.pagedTasks().length; else emptyTpl">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>Cron</th>
          <th>状态</th>
          <th>并发</th>
          <th>创建时间</th>
          <th>更新时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let t of store.pagedTasks()">
          <td>{{t.id}}</td>
          <td><a [routerLink]="['/cronjobs/tasks', t.id]">{{t.name}}</a><div class="desc" *ngIf="t.description">{{t.description}}</div></td>
          <td>{{t.cron_expr}}</td>
          <td>
            <nz-badge [nzStatus]="t.status==='ENABLED' ? 'success' : 'default'" [nzText]="t.status==='ENABLED'?'启用':'禁用'"></nz-badge>
          </td>
          <td>{{t.max_concurrency}}</td>
          <td>{{t.created_at | date:'yyyy-MM-dd HH:mm:ss'}}</td>
          <td>{{t.updated_at | date:'yyyy-MM-dd HH:mm:ss'}}</td>
          <td class="ops">
            <button nz-button nzSize="small" (click)="toggle(t)">{{t.status==='ENABLED'?'禁用':'启用'}}</button>
            <button nz-button nzSize="small" (click)="trigger(t)">触发</button>
            <button nz-button nzSize="small" [routerLink]="['/cronjobs/tasks', t.id, 'edit']">编辑</button>
            <button nz-button nzSize="small" (click)="clone(t)">基于此创建</button>
            <button nz-button nzSize="small" nzDanger nz-popconfirm nzPopconfirmTitle="确认删除该任务?" (nzOnConfirm)="remove(t)">删除</button>
          </td>
        </tr>
      </tbody>
    </nz-table>
    <ng-template #emptyTpl><div class="empty">暂无任务</div></ng-template>
    <div class="pager" *ngIf="store.taskTotal() > 0">
      <nz-pagination [nzTotal]="store.taskTotal()" [nzPageIndex]="store.taskPageIndex()" [nzPageSize]="store.taskPageSize()"
        (nzPageIndexChange)="onPage($event)" (nzPageSizeChange)="onPageSize($event)" [nzShowSizeChanger]="true"></nz-pagination>
    </div>
  </ng-template>
  `,
  styles: [`
    .header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; }
    .ops { display:flex; gap:4px; flex-wrap:wrap; }
    .empty { padding: 32px; text-align:center; color:#888; }
    .pager { margin-top: 16px; display:flex; justify-content:center; }
    .filters { border:1px solid #eee; padding:12px; border-radius:6px; margin-bottom: 12px; display:flex; flex-direction:column; gap:12px; }
    .filter-grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(220px,1fr)); gap:12px 16px; }
    .f-item { display:flex; flex-direction:column; gap:4px; }
    .f-item.wide { grid-column: span 2; min-width: 440px; }
    @media (max-width: 820px){ .f-item.wide { grid-column: span 1; min-width:unset; } }
    .f-item label { font-size:12px; color:#555; font-weight:500; }
    .range { display:flex; align-items:center; gap:4px; }
    .range input { flex:1; }
    .dash { color:#999; }
    .filter-actions { display:flex; gap:8px; }
  `]
})
export class TaskListPageComponent implements OnInit {
  search = '';
  desc = '';
  status = 'ALL';
  createdFrom = '';
  createdTo = '';
  updatedFrom = '';
  updatedTo = '';
  showFilters = true;
  constructor(public store: CronjobsStore, private msg: NzMessageService, private router: Router) {}
  ngOnInit(){ this.store.loadTasks(); }
  toggleFilters(){ this.showFilters = !this.showFilters; }
  reload(){ this.store.loadTasks(true); }
  toggle(t: any){
    const obs = t.status==='ENABLED'? this.store.disable(t.id): this.store.enable(t.id);
    obs.subscribe(()=> this.store.loadTasks(true));
  }
  trigger(t: any){ this.store.trigger(t.id).subscribe(()=> this.store.loadRuns(t.id, true)); }
  refreshCache(){ this.store.refreshCache().subscribe(()=> this.store.loadTasks(true)); }
  remove(t: any){ this.store.delete(t.id).subscribe({ next: ()=> { this.msg.success('删除成功');
    this.store.loadTasks(true); }, error: ()=> this.msg.error('删除失败'), }); }
  onPage(i: number){ this.store.setTaskPage(i); }
  onPageSize(size: number){ this.store.setTaskPageSize(size); }
  apply(){
    this.store.applyFilters({
      name: this.search,
      desc: this.desc,
      status: this.status as any,
      createdFrom: this.toRFC3339(this.createdFrom),
      createdTo: this.toRFC3339(this.createdTo),
      updatedFrom: this.toRFC3339(this.updatedFrom),
      updatedTo: this.toRFC3339(this.updatedTo)
    });
  }
  clearFilters(){
    this.search=''; this.desc=''; this.status='ALL'; this.createdFrom=''; this.createdTo=''; this.updatedFrom=''; this.updatedTo='';
    this.store.resetFilters();
  }
  clone(t: any){
    // 过滤掉不应复制的字段
    const allowedKeys = [
      'name','description','cron_expr','timezone','exec_type','http_method','target_url','headers_json','body_template','timeout_seconds','retry_policy_json','max_concurrency','concurrency_policy','callback_method','callback_timeout_sec','overlap_action','failure_action','status'
    ];
    const template: any = {};
    for(const k of allowedKeys){ template[k] = t[k]; }
    // 名称附加后缀避免重复
    if(template.name) template.name = template.name + ' copy';
    // 状态统一初始为 ENABLED
    template.status = 'ENABLED';
    // 导航状态传递模板
    this.router.navigate(['/cronjobs/tasks','new'], { state: { template } });
  }
  private toRFC3339(local: string): string | undefined {
    if(!local) return undefined;
    const d = new Date(local);
    if (isNaN(d.getTime())) return undefined;
    return d.toISOString();
  }
}
