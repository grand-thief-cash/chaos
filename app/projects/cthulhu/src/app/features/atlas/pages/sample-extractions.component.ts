import {CommonModule} from '@angular/common';
import {Component, OnInit, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ActivatedRoute, Router} from '@angular/router';
import {AtlasApiService} from '../services/atlas-api.service';
import {SampleCategoryResult, SampleRun} from '../models/atlas.models';

@Component({
  selector: 'app-atlas-sample-extractions',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <h1>Sample extractions (per-document)</h1>
      <p class="hint">
        选择一次采样运行,按报告类型展示模型对每篇研报抽取的原始 JSON。
        新的采样流程先让模型自由抽取每篇 PDF 的重要内容(free_extraction_result),
        再由模型跨篇归纳出可复用的 predicate / concept;旧的严格 schema 结果(extraction_result)也会保留展示。
      </p>

      <div class="bar">
        <label>Run:
          <select [ngModel]="selectedRunId" (change)="onSelectRun($event)">
            <option value="">- 选择采样运行 -</option>
            <option *ngFor="let r of runs" [value]="r.id">
              {{r.id.slice(0,8)}} · {{r.status}} · {{r.current}}/{{r.total}}
            </option>
          </select>
        </label>
        <input [ngModel]="manualRunId" (ngModelChange)="manualRunId=$event"
          placeholder="或粘贴 run id">
        <button (click)="loadManual()" [disabled]="!manualRunId">加载</button>
      </div>
      <p class="error" *ngIf="error">{{error}}</p>
      <p class="hint" *ngIf="loading">加载中…</p>

      <ng-container *ngIf="selectedRunId && !loading">
        <p class="hint" *ngIf="!categories.length">该运行暂无分类抽取结果。</p>
        <details *ngFor="let c of categories" class="cat" open>
          <summary>
            <b>{{c.report_type}}</b> · {{c.document_count}} docs
            <span class="fs-tag" *ngIf="c.field_summary?.recommended_fields?.length">
              {{c.field_summary?.recommended_fields?.length}} recommended fields
            </span>
            <span class="fs-tag warn" *ngIf="c.field_summary?.notes">{{c.field_summary?.notes}}</span>
          </summary>

          <section class="fs" *ngIf="c.field_summary">
            <h3>Field summary — 模型总结(全量抽取应抽取的字段)</h3>
            <pre>{{json(c.field_summary)}}</pre>
          </section>

          <section class="docs">
            <h3>Documents ({{c.raw_results.length}}) — 每篇研报的抽取 JSON</h3>
            <details *ngFor="let r of c.raw_results; let i = index" class="doc">
              <summary>
                <span class="idx">{{i + 1}}</span>
                {{r.title || r.document_id}}
                <small>{{r.s3_path}}</small>
                <span class="tag" *ngIf="r.free_extraction_result">自由抽取</span>
                <span class="tag strict" *ngIf="!r.free_extraction_result">严格 schema</span>
              </summary>
              <ng-container *ngIf="r.free_extraction_result; else strictBlock">
                <h4 class="sub">自由抽取结果 (free_extraction_result)</h4>
                <pre>{{json(r.free_extraction_result)}}</pre>
              </ng-container>
              <ng-template #strictBlock>
                <h4 class="sub" *ngIf="r.extraction_result">严格 schema 结果 (extraction_result)</h4>
                <pre>{{json(r.extraction_result)}}</pre>
              </ng-template>
            </details>
          </section>
        </details>
      </ng-container>
    </section>
  `,
  styles: [`
    .page{padding:24px;font-family:system-ui,sans-serif;max-width:1100px}
    .hint{color:#666;max-width:900px}
    .bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px;margin:12px 0;
      background:#f7f9fc;border:1px solid #e5e8ef;border-radius:8px}
    .bar select,.bar input{padding:6px;font-family:monospace}
    button{padding:6px 12px;cursor:pointer}
    .error{color:#cf1322}
    .cat{margin-bottom:14px;border:1px solid #ddd;border-radius:6px;padding:8px}
    .cat summary{cursor:pointer;font-size:15px}
    .fs-tag{color:#1677ff;font-size:12px;margin-left:8px}
    .fs-tag.warn{color:#d46b08}
    .fs,.docs{margin:10px 0}
    .fs h3,.docs h3{margin:0 0 6px;font-size:13px;color:#555}
    .doc{margin:4px 0}.doc summary{cursor:pointer;font-size:13px}
    .doc .idx{display:inline-block;min-width:22px;color:#888;font-variant-numeric:tabular-nums}
    .doc small{color:#999;margin-left:6px}
    .tag{display:inline-block;margin-left:8px;padding:1px 6px;border-radius:3px;background:#e6f4ff;color:#1677ff;font-size:11px}
    .tag.strict{background:#fff7e6;color:#d46b08}
    .sub{margin:6px 0 4px;font-size:12px;color:#888;font-weight:600}
    pre{background:#1e1e1e;color:#d4d4d4;padding:10px;border-radius:4px;overflow:auto;
      max-height:520px;font-size:11px;max-width:1040px}
  `],
})
export class SampleExtractionsComponent implements OnInit {
  private api = inject(AtlasApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  runs: SampleRun[] = [];
  selectedRunId = '';
  manualRunId = '';
  categories: SampleCategoryResult[] = [];
  loading = false;
  error = '';

  ngOnInit(): void {
    this.api.listSampleRuns('').subscribe({
      next: r => (this.runs = r.data ?? []),
      error: e => (this.error = e?.message ?? '加载运行列表失败'),
    });
    const qid = this.route.snapshot.queryParamMap.get('run_id');
    if (qid) {
      this.selectedRunId = qid;
      this.manualRunId = qid;
      this.loadCategories(qid);
    }
  }

  onSelectRun(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    if (!value) {
      return;
    }
    this.selectedRunId = value;
    this.manualRunId = value;
    this.router.navigate([], {queryParams: {run_id: value}, queryParamsHandling: 'merge'});
    this.loadCategories(value);
  }

  loadManual(): void {
    if (!this.manualRunId) {
      return;
    }
    this.selectedRunId = this.manualRunId;
    this.router.navigate([], {queryParams: {run_id: this.manualRunId}, queryParamsHandling: 'merge'});
    this.loadCategories(this.manualRunId);
  }

  private loadCategories(runId: string): void {
    this.loading = true;
    this.error = '';
    this.api.listSampleCategoryResults(runId).subscribe({
      next: r => {
        this.categories = r.data ?? [];
        this.loading = false;
      },
      error: e => {
        this.error = e?.message ?? '加载分类结果失败';
        this.loading = false;
      },
    });
  }

  json(value: unknown): string {
    return value == null ? '(无)' : JSON.stringify(value, null, 2);
  }
}
