import {Component, computed, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzPaginationModule} from 'ng-zorro-antd/pagination';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {RouterLink} from '@angular/router';
import {RUN_STATUS_BADGE} from '../cronjobs.constants';

@Component({
  selector: 'cron-runs-active-page',
  standalone: true,
  imports: [CommonModule, NzTableModule, NzBadgeModule, NzPaginationModule, NzButtonModule, RouterLink],
  template: `
    <div class="active-runs-page">
      <h2>活跃运行</h2>
      <div class="filters">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
      </div>
      <nz-table nzBordered [nzData]="paged()" *ngIf="runs().length; else emptyTpl">
        <thead><tr><th>ID</th><th>Task</th><th>Status</th><th>Scheduled</th><th>Start</th><th>Attempt</th></tr></thead>
        <tbody>
          <tr *ngFor="let r of paged()">
            <td><a [routerLink]="['/cronjobs/run', r.id]">{{r.id}}</a></td>
            <td>{{r.task_id}}</td>
            <td><nz-badge [nzStatus]="RUN_STATUS_BADGE[r.status].status || 'default'" [nzText]="RUN_STATUS_BADGE[r.status].text || r.status"></nz-badge></td>
            <td>{{r.scheduled_time}}</td>
            <td>{{r.start_time || '-'}}</td>
            <td>{{r.attempt}}</td>
          </tr>
        </tbody>
      </nz-table>
      <ng-template #emptyTpl><div>暂无活跃运行</div></ng-template>
      <nz-pagination [nzTotal]="runs().length" [nzPageIndex]="page()" [nzPageSize]="size()" (nzPageIndexChange)="onPage($event)" (nzPageSizeChange)="onSize($event)" [nzShowSizeChanger]="true"></nz-pagination>
    </div>
  `,
  styles: [`
    .active-runs-page { padding: 24px; background:#fff; border-radius:8px; }
    .filters { margin-bottom:12px; }
  `]
})
export class RunsActivePageComponent implements OnInit {
  private _runs = signal<any[]>([]);
  private _page = signal(1);
  private _size = signal(10);
  runs = computed(()=> this._runs());
  page = computed(()=> this._page());
  size = computed(()=> this._size());
  paged = computed(()=> { const start = (this.page()-1)* this.size(); return this.runs().slice(start, start+ this.size()); });
  RUN_STATUS_BADGE = RUN_STATUS_BADGE;
  constructor(private api: CronjobsApiService) {}
  ngOnInit(){ this.reload(); }
  reload(){ this.api.listActiveRuns().subscribe(resp=> { const items = Array.isArray(resp.items)? resp.items: resp.items || resp; this._runs.set(items); }); }
  onPage(i: number){ this._page.set(i); }
  onSize(s: number){ this._size.set(s); this._page.set(1); }
}
