import {CommonModule} from '@angular/common';
import {Component, OnInit, inject} from '@angular/core';
import {RouterLink} from '@angular/router';
import {forkJoin} from 'rxjs';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-overview', standalone: true, imports: [CommonModule, RouterLink],
  template: `
    <section class="page">
      <header><h1>Atlas Knowledge Engine</h1><p>研报知识生产、语义治理与受控图查询</p></header>
      <div class="cards">
        <a routerLink="../extractions"><strong>{{runCount}}</strong><span>最近抽取运行</span></a>
        <a routerLink="../semantics"><strong>{{semanticCount}}</strong><span>语义版本 / Proposal</span></a>
        <a routerLink="../graph"><strong>{{stats?.entities ?? 0}}</strong><span>图谱实体</span></a>
        <a routerLink="../graph"><strong>{{stats?.claims ?? 0}}</strong><span>图谱 Claims</span></a>
      </div>
      <div class="flow">
        <span>Sample PDF</span><b>→</b><span>人工审核语义</span><b>→</b>
        <span>发布 YAML</span><b>→</b><span>全量抽取</span><b>→</b><span>图投影 / 查询</span>
      </div>
      <p class="error" *ngIf="error">{{error}}</p>
    </section>`,
  styles: [`
    .page{padding:24px}.cards{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:16px}
    .cards a{padding:22px;border:1px solid #d9d9d9;border-radius:8px;background:#fff;color:#222}
    strong{display:block;font-size:30px;color:#1677ff}span{display:block;margin-top:6px;color:#666}
    .flow{display:flex;align-items:center;gap:14px;margin-top:28px;padding:20px;background:#f5f8ff;border-radius:8px}
    .flow span{color:#222}.error{color:#cf1322}@media(max-width:900px){.cards{grid-template-columns:1fr 1fr}}
  `]
})
export class AtlasOverviewComponent implements OnInit {
  private api = inject(AtlasApiService);
  runCount = 0; semanticCount = 0; stats: any; error = '';
  ngOnInit(): void {
    forkJoin({
      runs: this.api.extractionRuns(),
      semantics: this.api.governance('semantic-version'),
      stats: this.api.graphStats()
    }).subscribe({
      next: value => {
        this.runCount = value.runs.data.length;
        this.semanticCount = value.semantics.data.length;
        this.stats = value.stats;
      },
      error: err => this.error = err?.message ?? 'Atlas 服务不可用'
    });
  }
}
