// Run detail page
import {Component, computed, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ActivatedRoute, RouterLink} from '@angular/router';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';
import {RUN_STATUS_BADGE} from '../cronjobs.constants';

@Component({
  selector: 'cron-run-detail-page',
  standalone: true,
  imports: [CommonModule, NzBadgeModule, NzButtonModule, NzMessageModule, RouterLink],
  template: `
    <div class="run-detail-page" *ngIf="run(); else loadingTpl">
      <h2>运行详情 #{{run()?.id}} <small>(任务 <a [routerLink]="['/cronjobs/tasks', parentTaskId]">{{parentTaskId}}</a>)</small></h2>
      <div class="status">
        <nz-badge [nzStatus]="RUN_STATUS_BADGE[run()?.status].status || 'default'" [nzText]="RUN_STATUS_BADGE[run()?.status].text || run()?.status"></nz-badge>
      </div>
      <div class="meta">
        <div><strong>Task ID:</strong> {{parentTaskId}}</div>
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
        <div class="kv">
          <div class="label">Headers</div>
          <button nz-button nzSize="small" nzType="link" (click)="copy(run()?.request_headers)">复制</button>
        </div>
        <pre>{{ formatMaybeJson(run()?.request_headers) }}</pre>

        <div class="kv">
          <div class="label">Body</div>
          <button nz-button nzSize="small" nzType="link" (click)="copy(run()?.request_body)">复制</button>
        </div>
        <pre>{{ formatMaybeJson(run()?.request_body) }}</pre>
      </div>
      <div class="resp">
        <h3>响应</h3>
        <div><strong>Code:</strong> {{run()?.response_code || '-'}} </div>

        <div class="kv">
          <div class="label">Body</div>
          <button nz-button nzSize="small" nzType="link" (click)="copy(run()?.response_body)">复制</button>
        </div>
        <pre>{{ formatMaybeJson(run()?.response_body) }}</pre>

        <div class="kv">
          <div class="label">Error</div>
          <button nz-button nzSize="small" nzType="link" (click)="copy(run()?.error_message)">复制</button>
        </div>
        <pre class="error">{{ formatMaybeJson(run()?.error_message) }}</pre>
      </div>
      <div class="actions">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
        <button nz-button nzType="default" *ngIf="canCancel()" (click)="cancel()">取消运行</button>
        <button nz-button nzType="link" [routerLink]="['/cronjobs/tasks', parentTaskId]">返回任务</button>
      </div>
    </div>
    <ng-template #loadingTpl><div>加载中...</div></ng-template>
  `,
  styles: [`
    .run-detail-page { padding:24px; background:#fff; border-radius:8px; }
    pre { background:#f7f7f7; padding:8px; border-radius:4px; white-space: pre-wrap; word-break: break-word; }
    pre.error { background:#fff1f0; }
    .actions { margin-top:12px; }
    .kv { display:flex; align-items:center; justify-content: space-between; margin-top: 6px; }
    .kv .label { font-weight: 600; }
  `]
})
export class RunDetailPageComponent implements OnInit {
  private _run = signal<any | null>(null);
  private _progress = signal<any | null>(null);
  run = computed(()=> this._run());
  progress = computed(()=> this._progress());
  RUN_STATUS_BADGE = RUN_STATUS_BADGE;
  parentTaskId: number | null = null;
  constructor(private route: ActivatedRoute, private api: CronjobsApiService, private msg: NzMessageService) {}
  ngOnInit(){ this.parentTaskId = Number(this.route.snapshot.paramMap.get('id')); this.reload(); }
  reload(){ const id = Number(this.route.snapshot.paramMap.get('runId')); if(!id) return; this.api.getRun(id).subscribe(r=> this._run.set(r)); this.api.runProgress(id).subscribe(p=> this._progress.set(p)); }
  canCancel(){ const st = this.run()?.status; return ['SCHEDULED','RUNNING','CALLBACK_PENDING'].includes(st || ''); }
  cancel(){ const id = this.run()?.id; if(!id) return; this.api.cancelRun(id).subscribe({ next: ()=> { this.msg.success('取消成功'); this.reload(); }, error: ()=> this.msg.error('取消失败') }); }

  formatMaybeJson(v: any): string {
    if (v === null || v === undefined) return '';
    // If backend already returns an object (rare), pretty-print directly.
    if (typeof v === 'object') {
      try { return JSON.stringify(v, null, 2); } catch { return String(v); }
    }
    const s = String(v);
    const t = s.trim();
    if (!t) return '';

    // Try to parse JSON objects/arrays.
    if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))) {
      try {
        const obj = JSON.parse(t);
        return JSON.stringify(obj, null, 2);
      } catch {
        // fallthrough
      }
    }

    // Some errors are like: "400 Bad Request; body={...}". Pull out the JSON part if any.
    const idx = t.indexOf('{');
    if (idx >= 0) {
      const maybe = t.slice(idx);
      try {
        const obj = JSON.parse(maybe);
        return t.slice(0, idx) + JSON.stringify(obj, null, 2);
      } catch {
        // ignore
      }
    }

    return s;
  }

  copy(v: any) {
    const text = v === null || v === undefined ? '' : (typeof v === 'string' ? v : (() => {
      try { return JSON.stringify(v, null, 2); } catch { return String(v); }
    })());
    if (!text) {
      this.msg.warning('没有内容可复制');
      return;
    }
    const navAny: any = navigator as any;
    if (navAny?.clipboard?.writeText) {
      navAny.clipboard.writeText(text).then(
        () => this.msg.success('已复制'),
        () => this.msg.error('复制失败')
      );
      return;
    }
    // Fallback
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      this.msg.success('已复制');
    } catch {
      this.msg.error('复制失败');
    }
  }
}
