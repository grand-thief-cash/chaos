import {Component, computed, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzProgressModule} from 'ng-zorro-antd/progress';
import {RouterLink} from '@angular/router';

@Component({
  selector: 'cron-runs-progress-page',
  standalone: true,
  imports: [CommonModule, NzTableModule, NzButtonModule, NzBadgeModule, NzTagModule, NzProgressModule, RouterLink],
  template: `
    <div class="runs-progress-page">
      <h2>运行进度总览</h2>
      <div class="actions">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
        <button nz-button nzType="dashed" (click)="autoToggle()">{{autoRefresh() ? '停止自动刷新' : '自动刷新'}}</button>
      </div>
      <nz-table nzBordered [nzData]="progresses()" *ngIf="progresses().length; else emptyTpl">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Current</th>
            <th>Total</th>
            <th>Percent</th>
            <th>Message</th>
            <th>Updated At</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of progresses()">
            <td><a [routerLink]="['/cronjobs/run', p.run_id]">{{p.run_id}}</a></td>
            <td>{{p.current}}</td>
            <td>{{p.total}}</td>
            <td><nz-progress [nzPercent]="p.percent" [nzStatus]="p.percent===100 ? 'success':'active'" [nzStrokeWidth]="8" [nzShowInfo]="true"></nz-progress></td>
            <td>{{p.message || '-'}}</td>
            <td>{{p.updated_at | date:'yyyy-MM-dd HH:mm:ss'}}</td>
          </tr>
        </tbody>
      </nz-table>
      <ng-template #emptyTpl><div>暂无进度数据</div></ng-template>
    </div>
  `,
  styles: [`
    .runs-progress-page { padding:24px; background:#fff; border-radius:8px; }
    .actions { margin-bottom:12px; display:flex; gap:8px; }
    nz-progress { width:140px; }
  `]
})
export class RunsProgressPageComponent implements OnInit {
  private _progresses = signal<any[]>([]);
  private _autoRefresh = signal(false);
  progresses = computed(()=> this._progresses());
  autoRefresh = computed(()=> this._autoRefresh());
  private intervalHandle: any;
  constructor(private api: CronjobsApiService) {}
  ngOnInit(){ this.reload(); }
  reload(){ this.api.listAllRunProgress().subscribe(items => { this._progresses.set(items); }); }
  autoToggle(){
    this._autoRefresh.set(!this._autoRefresh());
    if(this._autoRefresh()){
      this.intervalHandle = setInterval(()=> this.reload(), 2000);
    } else if(this.intervalHandle){
      clearInterval(this.intervalHandle);
    }
  }
  ngOnDestroy(){ if(this.intervalHandle){ clearInterval(this.intervalHandle); } }
}

