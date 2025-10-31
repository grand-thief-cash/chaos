// Run detail page
import {Component, OnInit, signal, computed} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ActivatedRoute} from '@angular/router';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';
import {RUN_STATUS_BADGE} from '../cronjobs.constants';

@Component({
  selector: 'cron-run-detail-page',
  standalone: true,
  imports: [CommonModule, NzBadgeModule, NzButtonModule, NzMessageModule],
  template: `
    <div class="run-detail-page" *ngIf="run(); else loadingTpl">
      <h2>运行详情 #{{run()?.id}}</h2>
      <div class="status">
        <nz-badge [nzStatus]="RUN_STATUS_BADGE[run()?.status].status || 'default'" [nzText]="RUN_STATUS_BADGE[run()?.status].text || run()?.status"></nz-badge>
      </div>
      <div class="meta">
        <div><strong>Task ID:</strong> {{run()?.task_id}}</div>
        <div><strong>Scheduled:</strong> {{run()?.scheduled_time}}</div>
        <div><strong>Start:</strong> {{run()?.start_time || '-'}} </div>
        <div><strong>End:</strong> {{run()?.end_time || '-'}} </div>
        <div><strong>Attempt:</strong> {{run()?.attempt}}</div>
        <div><strong>Trace:</strong> {{run()?.trace_id}}</div>
      </div>
      <div class="progress" *ngIf="progress()">
        <h3>进度: {{progress()?.percent}}%</h3>
        <div>{{progress()?.message}}</div>
      </div>
      <div class="req">
        <h3>请求</h3>
        <pre>{{run()?.request_headers}}</pre>
        <pre>{{run()?.request_body}}</pre>
      </div>
      <div class="resp">
        <h3>响应</h3>
        <div><strong>Code:</strong> {{run()?.response_code || '-'}} </div>
        <pre>{{run()?.response_body}}</pre>
        <div><strong>Error:</strong> {{run()?.error_message}}</div>
      </div>
      <div class="actions">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
        <button nz-button nzType="default" *ngIf="canCancel()" (click)="cancel()">取消运行</button>
      </div>
    </div>
    <ng-template #loadingTpl><div>加载中...</div></ng-template>
  `,
  styles: [`
    .run-detail-page { padding:24px; background:#fff; border-radius:8px; }
    pre { background:#f7f7f7; padding:8px; border-radius:4px; }
    .actions { margin-top:12px; }
  `]
})
export class RunDetailPageComponent implements OnInit {
  private _run = signal<any | null>(null);
  private _progress = signal<any | null>(null);
  run = computed(()=> this._run());
  progress = computed(()=> this._progress());
  RUN_STATUS_BADGE = RUN_STATUS_BADGE;
  constructor(private route: ActivatedRoute, private api: CronjobsApiService, private msg: NzMessageService) {}
  ngOnInit(){ this.reload(); }
  reload(){ const id = Number(this.route.snapshot.paramMap.get('runId')); if(!id) return; this.api.getRun(id).subscribe(r=> this._run.set(r)); this.api.runProgress(id).subscribe(p=> this._progress.set(p)); }
  canCancel(){ const st = this.run()?.status; return ['SCHEDULED','RUNNING','CALLBACK_PENDING'].includes(st || ''); }
  cancel(){ const id = this.run()?.id; if(!id) return; this.api.cancelRun(id).subscribe({ next: ()=> { this.msg.success('取消成功'); this.reload(); }, error: ()=> this.msg.error('取消失败') }); }
}

