import {CommonModule} from '@angular/common';
import {Component, OnInit, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {AtlasApiService} from '../services/atlas-api.service';
import {ExtractionRun} from '../models/atlas.models';

@Component({
  selector: 'app-atlas-extractions', standalone: true, imports: [CommonModule, FormsModule],
  template: `
    <section class="page"><h1>Extraction Runs</h1>
      <form class="batch" (ngSubmit)="startBatch()">
        <h2>启动正式抽取批次</h2>
        <label>开始日期 <input type="date" name="publishedFrom" [(ngModel)]="publishedFrom"></label>
        <label>结束日期 <input type="date" name="publishedTo" [(ngModel)]="publishedTo"></label>
        <label>Report Types
          <input name="reportTypes" [(ngModel)]="reportTypes"
            placeholder="留空；或 stock,industry">
        </label>
        <label>数量 <input type="number" name="limit" [(ngModel)]="limit" min="1" max="2000"></label>
        <label class="check"><input type="checkbox" name="force" [(ngModel)]="force"> 强制重新抽取</label>
        <button type="submit" [disabled]="starting || limit < 1 || limit > 2000">
          {{starting ? '运行中…' : '启动批次'}}
        </button>
        <small>Report Types 留空时只消费 Active Semantic Version 中启用的类型；显式类型也只能是其子集。</small>
      </form>
      <p class="success" *ngIf="batchMessage">{{batchMessage}}</p>
      <p class="error" *ngIf="error">{{error}}</p>

      <label>状态 <select [(ngModel)]="status" (change)="load()">
        <option value="">全部</option><option>SUCCEEDED</option><option>FAILED_RETRYABLE</option>
        <option>PROCESSING</option></select></label>
      <div class="table-wrap"><table><thead><tr>
        <th>文档 / 类型</th><th>模型 / 语义</th><th>PDF</th><th>请求与校验</th>
        <th>Claims</th><th>状态 / 错误</th><th>更新时间</th>
      </tr></thead>
      <tbody><tr *ngFor="let run of runs">
        <td><div>{{run.source_document_id}}</div><small>{{run.source_report_type}}</small></td>
        <td><div>{{run.payload?.model_id || '—'}}</div><small>{{run.payload?.semantic_version || '—'}}</small></td>
        <td><div>{{run.payload?.pdf_size_bytes || 0}} B / {{run.payload?.pdf_page_count || 0}} 页</div>
          <small>{{run.payload?.pdf_unlock_status || '—'}}</small></td>
        <td><div>attempts: {{run.payload?.request_attempt_count || 0}}</div>
          <small>{{(run.payload?.validation_error_codes || []).join(', ') || '无格式错误'}}</small>
          <strong *ngIf="run.payload?.possible_truncation">可能截断</strong></td>
        <td>R {{run.payload?.relation_claim_count || 0}} /
          Q {{run.payload?.quantified_claim_count || 0}} /
          V {{run.payload?.analyst_view_count || 0}}</td>
        <td><code>{{run.status}}</code><small>{{run.payload?.error_code || ''}}</small>
          <span>{{run.payload?.error_summary || ''}}</span></td>
        <td>{{run.updated_at | date:'medium'}}</td>
      </tr></tbody></table></div>
    </section>`,
  styles: [`.page{padding:24px}.batch{display:flex;flex-wrap:wrap;gap:12px;align-items:end;
      padding:16px;margin-bottom:16px;background:#f7f9fc;border:1px solid #e5e8ef;border-radius:8px}
    .batch h2{width:100%;margin:0}.batch label{display:flex;flex-direction:column;gap:5px}
    .batch .check{flex-direction:row}.batch small{width:100%;color:#666}.batch input{padding:7px}
    button{padding:8px 14px}.table-wrap{overflow:auto}table{width:100%;min-width:1180px;margin-top:18px;border-collapse:collapse}
    th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #eee}
    code{display:block;color:#1677ff}td small,td span{display:block;max-width:260px;color:#666;overflow-wrap:anywhere}
    td strong{display:block;color:#d46b08}.success{color:#237804}.error{color:#cf1322}`]
})
export class ExtractionRunsComponent implements OnInit {
  private api = inject(AtlasApiService); runs: ExtractionRun[] = []; status = '';
  publishedFrom = ''; publishedTo = ''; reportTypes = ''; limit = 100; force = false;
  starting = false; batchMessage = ''; error = '';
  ngOnInit(){ this.load(); }
  load(){
    this.api.extractionRuns(this.status).subscribe({
      next: v => this.runs = v.data,
      error: err => this.error = err?.error?.detail ?? err?.message ?? '加载运行记录失败'
    });
  }
  startBatch(){
    const selectedTypes = this.reportTypes.split(',').map(value => value.trim()).filter(Boolean);
    this.starting = true; this.error = ''; this.batchMessage = '';
    this.api.startExtractionBatch({
      published_from: this.publishedFrom || null,
      published_to: this.publishedTo || null,
      report_types: selectedTypes.length ? selectedTypes : null,
      limit: this.limit,
      force: this.force,
    }).subscribe({
      next: result => {
        this.starting = false;
        this.batchMessage = `批次完成，共返回 ${result.count} 个运行记录。`;
        this.load();
      },
      error: err => {
        this.starting = false;
        this.error = err?.error?.detail ?? err?.message ?? '启动抽取批次失败';
      }
    });
  }
}
