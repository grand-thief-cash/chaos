import {Component, computed, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ActivatedRoute, Router, RouterLink, RouterOutlet} from '@angular/router';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';
import {NzPaginationModule} from 'ng-zorro-antd/pagination';
import {RUN_STATUS_BADGE} from '../cronjobs.constants';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {CronjobsStore} from '../state/cronjobs.store';

@Component({
  selector: 'cron-task-detail-page',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterOutlet, NzButtonModule, NzBadgeModule, NzTableModule, NzPaginationModule, NzMessageModule],
  template: `
  <div *ngIf="!showingRunDetail && task(); else loadingOrChild" class="task-detail">
    <h2>任务详情: {{task()?.name}} <small>#{{task()?.id}}</small></h2>
    <div class="meta">
      <div><strong>Cron:</strong> {{task()?.cron_expr}}</div>
      <div><strong>Status:</strong> {{task()?.status}}</div>
      <div><strong>并发限制:</strong> {{task()?.max_concurrency}} ({{task()?.concurrency_policy}})</div>
      <div><strong>执行类型:</strong> {{task()?.exec_type}}</div>
      <div><strong>重叠策略:</strong> {{task()?.overlap_action}}</div>
      <div><strong>失败策略:</strong> {{task()?.failure_action}}</div>
      <div><strong>目标:</strong> {{task()?.http_method}} {{task()?.target_url}}</div>
      <div><strong>描述:</strong> {{task()?.description}}</div>
    </div>
    <div class="actions">
      <button nz-button nzType="default" (click)="reloadRuns()">刷新运行记录</button>
      <button nz-button nzType="default" (click)="manualTrigger()">手动触发</button>
      <button nz-button nzType="default" (click)="goToRunProgress()">查看运行进度</button>
      <button nz-button nzType="default" (click)="toggleStatus()">{{task()?.status==='ENABLED'?'禁用':'启用'}}</button>
      <button nz-button nzType="primary" [routerLink]="['/cronjobs/tasks', task()?.id, 'edit']">编辑</button>
      <button nz-button nzType="link" [routerLink]="['/cronjobs/tasks']">返回列表</button>
    </div>
    <h3>运行统计</h3>
    <div *ngIf="statsLoading(); else statsTpl">统计加载中...</div>
    <ng-template #statsTpl>
      <div *ngIf="stats(); else noStatsTpl" class="stats">
        <div><strong>总运行数:</strong> {{stats()?.total_runs}}</div>
        <div><strong>平均等待(ms):</strong> {{stats()?.avg_wait_ms}}</div>
        <div><strong>平均执行(ms):</strong> {{stats()?.avg_exec_ms}}</div>
        <div class="dist">
          <div *ngFor="let kv of distEntries()">
            <nz-badge [nzStatus]="RUN_STATUS_BADGE[kv.key].status || 'default'" [nzText]="kv.key + ':' + kv.value"></nz-badge>
          </div>
        </div>
      </div>
      <ng-template #noStatsTpl><div>暂无统计数据</div></ng-template>
    </ng-template>
    <h3>最近运行记录</h3>
    <div *ngIf="runsLoading(); else runsTpl">运行记录加载中...</div>
    <ng-template #runsTpl>
      <nz-table [nzData]="pagedRuns()" nzBordered *ngIf="runs().length; else emptyRunsTpl">
        <thead><tr><th>ID</th><th>Scheduled</th><th>Status</th><th>Start</th><th>End</th><th>Attempt</th></tr></thead>
        <tbody>
          <tr *ngFor="let r of pagedRuns()">
            <td><a [routerLink]="['runs', r.id]">{{r.id}}</a></td>
            <td>{{r.scheduled_time}}</td>
            <td>
              <nz-badge [nzStatus]="RUN_STATUS_BADGE[r.status].status || 'default'" [nzText]="RUN_STATUS_BADGE[r.status].text || r.status"></nz-badge>
            </td>
            <td>{{r.start_time || '-'}}</td>
            <td>{{r.end_time || '-'}}</td>
            <td>{{r.attempt}}</td>
          </tr>
        </tbody>
      </nz-table>
      <div class="runs-pager" *ngIf="runs().length">
        <nz-pagination [nzTotal]="runs().length" [nzPageIndex]="runPage()" [nzPageSize]="runPageSize()"
          (nzPageIndexChange)="onRunPage($event)" (nzPageSizeChange)="onRunPageSize($event)" [nzShowSizeChanger]="true"></nz-pagination>
      </div>
      <ng-template #emptyRunsTpl><div>暂无运行记录</div></ng-template>
    </ng-template>
  </div>
  <ng-template #loadingOrChild>
    <ng-container *ngIf="showingRunDetail; else loadingTpl">
      <router-outlet></router-outlet>
    </ng-container>
  </ng-template>
  <ng-template #loadingTpl><div>详情加载中...</div></ng-template>
  `,
  styles: [`
    .task-detail { padding: 24px; background: #fff; border-radius: 8px; }
    .meta { margin-bottom: 16px; }
    .actions { margin-bottom: 24px; }
    .runs-table { width: 100%; margin-top: 16px; }
    .runs-pager { margin-top: 12px; display:flex; justify-content:center; }
    .stats { margin: 12px 0 24px; }
    .dist { display:flex; flex-wrap:wrap; gap:4px; }
  `]
})
export class TaskDetailPageComponent implements OnInit {
  taskId = signal<number | null>(null);
  task = computed(()=> this.store.tasks().find(t=> t.id === this.taskId()) || null);
  runs = computed(()=> this.store.runsFor(this.taskId()||0)());
  pagedRuns = computed(()=> this.store.pagedRuns(this.taskId()||0)());
  runPage = computed(()=> this.store.runPage(this.taskId()||0)());
  runPageSize = computed(()=> this.store.runPageSize(this.taskId()||0)());
  runsLoading = computed(()=> this.store.loadingRunsFor(this.taskId()||0)());
  RUN_STATUS_BADGE = RUN_STATUS_BADGE;
  private _stats = signal<any | null>(null);
  private _statsLoading = signal(false);
  stats = computed(()=> this._stats());
  statsLoading = computed(()=> this._statsLoading());
  constructor(private route: ActivatedRoute, public store: CronjobsStore, private msg: NzMessageService, private api: CronjobsApiService, private router: Router) {}
  get showingRunDetail(): boolean { return !!this.route.firstChild && this.route.firstChild.routeConfig?.path === 'runs'; }
  ngOnInit(){
    const id = Number(this.route.snapshot.paramMap.get('id')); this.taskId.set(id);
    this.store.loadTasks();
    this.store.loadRuns(id);
    this.loadStats();
  }
  loadStats(){ if(!this.taskId()) return; this._statsLoading.set(true); this.api.taskRunStats(this.taskId()!).subscribe({ next: s=> this._stats.set(s), error: ()=> this._statsLoading.set(false), complete: ()=> this._statsLoading.set(false) }); }
  distEntries(){ const st = this.stats(); if(!st) return []; return Object.entries(st.status_distribution || {}).map(([key,value])=> ({ key, value })); }
  reloadRuns(){ if(this.taskId()) { this.store.loadRuns(this.taskId()!, true); this.loadStats(); } }
  manualTrigger(){
    if(this.taskId()) this.store.trigger(this.taskId()!).subscribe({
      next: ()=> {
        this.msg.success('触发成功');
        this.reloadRuns();
        // 取消自动跳转：让用户在当前页面手动选择是否去“运行进度”页
      },
      error: ()=> this.msg.error('触发失败'),
    });
  }
  goToRunProgress(){
    this.router.navigate(['/cronjobs/runs/progress']);
  }
  toggleStatus(){ const t = this.task(); if(!t) return; const obs = t.status==='ENABLED'? this.store.disable(t.id): this.store.enable(t.id); obs.subscribe(()=> this.store.loadTasks(true)); }
  onRunPage(i: number){ if(this.taskId()) this.store.setRunPage(this.taskId()!, i); }
  onRunPageSize(size: number){ if(this.taskId()) this.store.setRunPageSize(this.taskId()!, size); }
}
