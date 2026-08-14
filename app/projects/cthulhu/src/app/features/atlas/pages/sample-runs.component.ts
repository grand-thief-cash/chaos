import {CommonModule} from '@angular/common';
import {Component, OnDestroy, OnInit, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {Subscription, timer} from 'rxjs';
import {AtlasApiService} from '../services/atlas-api.service';
import {
  ActiveSampleRun, HarnessEvent, SampleCategoryResult, SampleRun, SampleRunRequest,
} from '../models/atlas.models';

const REPORT_TYPES = ['stock', 'industry', 'macro', 'new_stock', 'strategy', 'morning_report'];

@Component({
  selector: 'app-atlas-sample-runs',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="page">
      <h1>Sample Runs</h1>
      <p class="hint">
        触发一次异步采样:并发抽取每类研报,产出每类聚合 JSON 与字段建议(field_summary),
        可人工编辑 field_summary 后用于全量抽取。进度由 atlas 持久化并推给 cronjob。
      </p>

      <form class="form" (ngSubmit)="start()">
        <label class="num">Sample size
          <input type="number" name="sampleSize" [(ngModel)]="sampleSize"
                 [min]="1" [max]="5000" [disabled]="sampleAll">
        </label>
        <label class="check"><input type="checkbox" name="sampleAll" [(ngModel)]="sampleAll"> 全量 (0=所有可用文档)</label>
        <div class="types">
          <span class="types-label">Report types</span>
          <label *ngFor="let t of reportTypes" class="check">
            <input type="checkbox" [checked]="selected[t]" (change)="toggle(t)"> {{t}}
          </label>
        </div>
        <label class="check"><input type="checkbox" name="force" [(ngModel)]="force"> force (跳过去重)</label>
        <button type="submit" [disabled]="starting || !canStart">
          {{starting ? '启动中…' : '运行采样'}}
        </button>
      </form>
      <p class="error" *ngIf="error">{{error}}</p>

      <section class="active-runs" *ngIf="activeRuns.length">
        <b>当前进程正在运行的 Sampling</b>
        <button type="button" *ngFor="let active of activeRuns"
          (click)="attach(active.run_id)" [disabled]="run?.id === active.run_id">
          {{active.run_id}} · {{active.identity_key}}
        </button>
      </section>

      <article class="run" *ngIf="run">
        <header>
          <b>Run {{run.id}}</b>
          <code class="status" [class.ok]="run.status==='SUCCESS'" [class.fail]="run.status==='FAILED'"
            [class.run]="run.status==='RUNNING'">{{run.status}}</code>
          <span class="prog">{{run.current}}/{{run.total}}</span>
          <span class="msg">{{run.progress_message || ''}}</span>
          <span class="elapsed" *ngIf="elapsed">{{elapsed}}</span>
        </header>
        <p class="error" *ngIf="run.error_message">{{run.error_message}}</p>
        <p class="meta">
          started: {{run.started_at | date:'medium'}} ·
          cronjob_run_id: {{run.cronjob_run_id ?? '—'}}
        </p>

        <section class="harness" *ngIf="run">
          <div class="harness-head">
            <div>
              <h2>Harness 实时进展</h2>
              <p>仅保存在当前 Atlas 进程内；服务重启后清空，不影响持久化 Sampling 结果。</p>
            </div>
            <label class="check">
              <input type="checkbox" [(ngModel)]="autoScroll" name="autoScroll">
              自动滚动
            </label>
          </div>
          <p class="event-warn" *ngIf="eventsTruncated">
            更早事件已从有界缓冲区滚出；当前显示最近 {{harnessEvents.length}} 条。
          </p>
          <div class="timeline" #timeline>
            <div class="event" *ngFor="let event of harnessEvents"
              [class.error-event]="event.level === 'ERROR'"
              [class.warn-event]="event.level === 'WARNING'">
              <time>{{event.timestamp | date:'HH:mm:ss'}}</time>
              <code class="stage">{{event.stage}}</code>
              <span class="event-msg">{{event.message}}</span>
              <span class="tag" *ngIf="event.report_type">{{event.report_type}}</span>
              <span class="tag" *ngIf="event.parser">parser: {{event.parser}}</span>
              <span class="tag" *ngIf="event.provider">model: {{event.provider}}</span>
              <small *ngIf="event.document_id">{{event.document_id}}</small>
              <details *ngIf="hasDetails(event)">
                <summary>details</summary>
                <pre>{{json(event.details)}}</pre>
              </details>
            </div>
            <p class="empty" *ngIf="!harnessEvents.length">等待 Harness 事件…</p>
          </div>
        </section>

        <div class="cats" *ngIf="run.status === 'SUCCESS'">
          <div class="cats-head">
            <h2>Category results ({{categories.length}})</h2>
            <a class="link-btn" [routerLink]="['/atlas/sample-extractions']" [queryParams]="{run_id: run.id}">
              在新页面查看每篇文档抽取 JSON ->
            </a>
          </div>
          <details *ngFor="let c of categories" class="cat" open>
            <summary>
              <b>{{c.report_type}}</b> · {{c.document_count}} docs
              <span class="fs-tag" *ngIf="c.field_summary?.recommended_fields?.length">
                {{c.field_summary?.recommended_fields?.length}} recommended fields
              </span>
            </summary>

            <section class="fs-edit">
              <h3>Field summary (agent 建议,可编辑)</h3>
              <textarea [(ngModel)]="fieldSummaryDraft[c.report_type]" rows="10"
                (ngModelChange)="markDirty(c.report_type)"></textarea>
              <button (click)="saveFieldSummary(c.report_type)"
                [disabled]="!dirty[c.report_type] || saving[c.report_type]">
                {{saving[c.report_type] ? '保存中…' : '保存 field_summary'}}
              </button>
              <span class="ok" *ngIf="saved[c.report_type]">已保存</span>
            </section>

            <section class="raw">
              <h3>Raw results ({{c.raw_results.length}} documents)</h3>
              <details *ngFor="let r of c.raw_results" class="doc">
                <summary>{{r.title || r.document_id}} <small>{{r.s3_path}}</small></summary>
                <pre>{{ json(r) }}</pre>
              </details>
            </section>
          </details>
        </div>
      </article>
    </section>
  `,
  styles: [`.page{padding:24px;font-family:system-ui,sans-serif}
    .hint{color:#666;max-width:900px}
    .form{display:flex;flex-wrap:wrap;gap:14px;align-items:end;padding:16px;margin:16px 0;
      background:#f7f9fc;border:1px solid #e5e8ef;border-radius:8px}
    .form .num{display:flex;flex-direction:column;gap:5px}.form input{padding:6px}
    .types{display:flex;flex-direction:column;gap:4px}.types-label{font-size:12px;color:#666}
    .check{display:flex;flex-direction:row;gap:6px;align-items:center}
    button{padding:8px 14px;cursor:pointer}
    .error{color:#cf1322}.ok{color:#237804}
    .active-runs{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0;
      padding:10px;background:#fffbe6;border:1px solid #ffe58f;border-radius:6px}
    .active-runs button{font-family:monospace;font-size:11px;max-width:100%;overflow:hidden;text-overflow:ellipsis}
    .run{margin-top:18px;padding:16px;background:#fff;border:1px solid #e5e8ef;border-radius:8px}
    .run header{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
    .status{padding:2px 8px;border-radius:4px;background:#eee}
    .status.ok{background:#d9f7be;color:#237804}.status.fail{background:#ffd6e7;color:#cf1322}
    .status.run{background:#e6f4ff;color:#1677ff}
    .prog{font-weight:600}.msg{color:#555}.elapsed{color:#888;margin-left:auto}
    .meta{color:#888;font-size:12px;margin:4px 0}
    .harness{margin:16px 0;border:1px solid #d9e2f2;border-radius:8px;background:#f8fbff;padding:12px}
    .harness-head{display:flex;justify-content:space-between;align-items:start;gap:12px}
    .harness h2{font-size:16px;margin:0}.harness-head p{font-size:12px;color:#667;margin:4px 0 8px}
    .timeline{max-height:420px;overflow:auto;background:#111827;color:#d1d5db;border-radius:6px;padding:8px}
    .event{display:grid;grid-template-columns:68px 190px minmax(220px,1fr);gap:6px 10px;
      padding:7px 5px;border-bottom:1px solid #273244;font-size:12px;align-items:start}
    .event:last-child{border-bottom:0}.event time{color:#94a3b8}.stage{color:#7dd3fc}
    .event-msg{color:#f3f4f6}.tag{display:inline-block;color:#bae6fd;background:#1e3a5f;
      padding:1px 5px;border-radius:3px;width:max-content}.event small{grid-column:3;color:#94a3b8}
    .event details{grid-column:3}.event details pre{max-height:180px;margin:5px 0 0}
    .warn-event{border-left:3px solid #f59e0b}.error-event{border-left:3px solid #ef4444}
    .event-warn{color:#ad6800;font-size:12px}.empty{color:#94a3b8;text-align:center}
    .cats{margin-top:16px}.cats-head{display:flex;gap:12px;align-items:center;margin-bottom:8px}
    .link-btn{padding:6px 12px;background:#5f6b7a;color:#fff;border-radius:4px;text-decoration:none;font-size:13px}
    .cat{margin-bottom:14px;border:1px solid #eee;border-radius:6px;padding:8px}
    .cat summary{cursor:pointer;font-size:15px}.fs-tag{color:#1677ff;font-size:12px;margin-left:8px}
    .fs-edit{margin:10px 0;padding:10px;background:#fafafa;border-radius:4px}
    .fs-edit textarea{width:100%;min-width:500px;font-family:monospace;font-size:12px}
    .raw h3,.fs-edit h3{margin:0 0 6px;font-size:13px;color:#555}
    .doc{margin:4px 0}.doc summary{cursor:pointer;font-size:13px}.doc small{color:#888;margin-left:6px}
    pre{background:#1e1e1e;color:#d4d4d4;padding:10px;border-radius:4px;overflow:auto;
      max-height:400px;font-size:11px;max-width:900px}`],
})
export class SampleRunsComponent implements OnInit, OnDestroy {
  private api = inject(AtlasApiService);
  reportTypes = REPORT_TYPES;
  selected: Record<string, boolean> = {};
  sampleSize = 5;
  sampleAll = false;
  force = false;
  starting = false;
  error = '';
  run: SampleRun | null = null;
  categories: SampleCategoryResult[] = [];
  elapsed = '';
  fieldSummaryDraft: Record<string, string> = {};
  dirty: Record<string, boolean> = {};
  saving: Record<string, boolean> = {};
  saved: Record<string, boolean> = {};
  harnessEvents: HarnessEvent[] = [];
  eventsTruncated = false;
  autoScroll = true;
  activeRuns: ActiveSampleRun[] = [];
  private latestEventSequence = 0;
  private pollSub: Subscription | null = null;
  private activeRunsSub: Subscription | null = null;
  private startTs = 0;

  ngOnInit() {
    this.activeRunsSub = timer(0, 3000).subscribe(() => {
      this.api.getActiveSampleRuns().subscribe({
        next: page => {
          this.activeRuns = page.data;
          if (!this.run && page.data.length) {
            this.attach(page.data[0].run_id);
          }
        },
        error: () => { /* the ephemeral task list must not block Sampling */ },
      });
    });
  }

  get selectedTypes(): string[] {
    return REPORT_TYPES.filter(t => this.selected[t]);
  }
  get canStart(): boolean {
    return this.selectedTypes.length > 0 && (this.sampleAll || this.sampleSize >= 1);
  }
  toggle(t: string) {
    this.selected = {...this.selected, [t]: !this.selected[t]};
  }

  start() {
    const payload: SampleRunRequest = {
      sample_size: this.sampleAll ? 0 : this.sampleSize,
      report_types: this.selectedTypes,
      published_from: null,
      published_to: null,
      force: this.force,
    };
    this.starting = true;
    this.error = '';
    this.run = null;
    this.categories = [];
    this.harnessEvents = [];
    this.latestEventSequence = 0;
    this.eventsTruncated = false;
    this.api.createSampleRun(payload).subscribe({
      next: resp => {
        this.starting = false;
        if (resp.sample_run_id) {
          this.attach(resp.sample_run_id, Date.now());
        }
      },
      error: err => {
        this.starting = false;
        this.error = err?.error?.error ?? err?.error?.detail ?? err?.message ?? '启动采样失败';
      },
    });
  }

  attach(runId: string, observedAt = 0) {
    if (this.run?.id === runId && this.pollSub) { return; }
    this.run = null;
    this.categories = [];
    this.harnessEvents = [];
    this.latestEventSequence = 0;
    this.eventsTruncated = false;
    this.startTs = observedAt;
    this.poll(runId);
  }

  private poll(runId: string) {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
    }
    this.pollSub = timer(0, 3000).subscribe(() => {
      this.loadHarnessEvents(runId);
      this.api.getSampleRun(runId).subscribe({
        next: r => {
          this.run = r;
          if (!this.startTs && r.started_at) {
            this.startTs = Date.parse(r.started_at);
          }
          if (this.startTs) {
            const sec = Math.floor((Date.now() - this.startTs) / 1000);
            this.elapsed = `elapsed ${Math.floor(sec / 60)}m${sec % 60}s`;
          }
          if (r.status === 'SUCCESS') {
            this.loadHarnessEvents(runId);
            this.stopPoll();
            this.loadCategories(runId);
          } else if (r.status === 'FAILED') {
            this.loadHarnessEvents(runId);
            this.stopPoll();
          }
        },
        error: err => {
          this.error = err?.message ?? '轮询进度失败';
          this.stopPoll();
        },
      });
    });
  }

  private loadHarnessEvents(runId: string) {
    this.api.getSampleHarnessEvents(runId, this.latestEventSequence).subscribe({
      next: page => {
        if (page.events.length) {
          const bySequence = new Map<number, HarnessEvent>();
          for (const event of [...this.harnessEvents, ...page.events]) {
            bySequence.set(event.sequence, event);
          }
          this.harnessEvents = [...bySequence.values()]
            .sort((left, right) => left.sequence - right.sequence)
            .slice(-page.buffer_limit);
          this.latestEventSequence = Math.max(
            this.latestEventSequence, page.latest_sequence,
          );
          this.eventsTruncated = this.eventsTruncated || page.truncated;
          if (this.autoScroll) {
            setTimeout(() => {
              const node = document.querySelector('.timeline');
              if (node) { node.scrollTop = node.scrollHeight; }
            });
          }
        }
      },
      error: () => { /* ephemeral observability must not fail the run UI */ },
    });
  }

  hasDetails(event: HarnessEvent): boolean {
    return Object.keys(event.details || {}).length > 0;
  }

  private loadCategories(runId: string) {
    this.api.listSampleCategoryResults(runId).subscribe({
      next: res => {
        this.categories = res.data;
        for (const c of this.categories) {
          this.fieldSummaryDraft[c.report_type] = c.field_summary
            ? JSON.stringify(c.field_summary, null, 2)
            : '{}';
        }
      },
      error: err => (this.error = err?.message ?? '加载分类结果失败'),
    });
  }

  markDirty(reportType: string) {
    this.dirty = {...this.dirty, [reportType]: true};
    this.saved = {...this.saved, [reportType]: false};
  }

  saveFieldSummary(reportType: string) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(this.fieldSummaryDraft[reportType] || '{}');
    } catch (e) {
      this.error = `${reportType}: field_summary 不是合法 JSON`;
      return;
    }
    if (!this.run) {
      return;
    }
    this.saving = {...this.saving, [reportType]: true};
    this.api.updateSampleFieldSummary(this.run.id, reportType, parsed).subscribe({
      next: () => {
        this.saving = {...this.saving, [reportType]: false};
        this.dirty = {...this.dirty, [reportType]: false};
        this.saved = {...this.saved, [reportType]: true};
      },
      error: err => {
        this.saving = {...this.saving, [reportType]: false};
        this.error = `${reportType}: 保存失败 ${err?.message ?? ''}`;
      },
    });
  }

  json(r: unknown): string {
    return JSON.stringify(r, null, 2);
  }

  private stopPoll() {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
      this.pollSub = null;
    }
  }

  ngOnDestroy() {
    this.stopPoll();
    this.activeRunsSub?.unsubscribe();
  }
}
