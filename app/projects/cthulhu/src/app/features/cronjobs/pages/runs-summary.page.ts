// Runs summary page
import {Component, computed, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {RUN_STATUS_BADGE} from '../cronjobs.constants';
import {RunsSummaryAggregate, RunsSummaryResponse} from '../models/cronjob.model';

@Component({
  selector: 'cron-runs-summary-page',
  standalone: true,
  imports: [CommonModule, NzTableModule, NzBadgeModule, NzButtonModule],
  template: `
    <div class="runs-summary-page">
      <h2>运行汇总</h2>
      <div class="actions"><button nz-button nzType="default" (click)="reload()">刷新</button></div>
      <div *ngIf="loading()">加载中...</div>
      <ng-container *ngIf="!loading()">
        <nz-table nzBordered [nzData]="rows()" *ngIf="rows().length; else emptyTpl">
          <thead><tr><th>Task ID</th><th>总运行</th><th>状态分布</th><th>终态估比</th></tr></thead>
          <tbody>
            <tr *ngFor="let r of rows()">
              <td>{{r.taskId}}</td>
              <td>{{r.aggregate.total_runs || '-'}}</td>
              <td>
                <div class="status-dist">
                  <div *ngFor="let kv of distEntries(r.aggregate.status_distribution)">
                    <nz-badge [nzStatus]="RUN_STATUS_BADGE[kv.key].status || 'default'" [nzText]="kv.key + ':' + kv.value"></nz-badge>
                  </div>
                </div>
              </td>
              <td>{{(r.aggregate.terminal_ratio_estimate||0) * 100 | number:'1.0-2'}}%</td>
            </tr>
          </tbody>
        </nz-table>
        <ng-template #emptyTpl><div>暂无汇总数据</div></ng-template>
      </ng-container>
    </div>
  `,
  styles: [`
    .runs-summary-page { padding:24px; background:#fff; border-radius:8px; }
    .status-dist { display:flex; flex-wrap:wrap; gap:4px; }
  `]
})
export class RunsSummaryPageComponent implements OnInit {
  private _resp = signal<RunsSummaryResponse | null>(null);
  private _loading = signal(false);
  loading = computed(()=> this._loading());
  rows = computed(()=> {
    const resp = this._resp(); if(!resp) return [];
    return Object.entries(resp.aggregates || {}).map(([taskId, aggregate])=> ({ taskId, aggregate: aggregate as RunsSummaryAggregate }));
  });
  RUN_STATUS_BADGE = RUN_STATUS_BADGE;
  constructor(private api: CronjobsApiService) {}
  ngOnInit(){ this.reload(); }
  reload(){ this._loading.set(true); this.api.runsSummary().subscribe({ next: r=> this._resp.set(r), error: ()=> this._loading.set(false), complete: ()=> this._loading.set(false) }); }
  distEntries(dist: Record<string, number> | undefined){ if(!dist) return []; return Object.entries(dist).map(([key,value])=> ({ key, value })); }
}
