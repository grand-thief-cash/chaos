import {CommonModule} from '@angular/common';
import {Component, OnInit, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {GovernanceRecord} from '../models/atlas.models';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-crosswalk',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <h1>Industry crosswalk</h1>
      <p>
        SW2021 seeds Atlas Canonical Industry deterministically. Other schemes
        are mapped by the model in bounded batches and rejected unless every
        source concept has an explicit mapping or NO_CANONICAL_MAPPING result.
      </p>
      <div class="toolbar">
        <label>Source <input [(ngModel)]="source"></label>
        <label>Target <input [(ngModel)]="target"></label>
        <button (click)="run()">Generate and validate</button>
        <button (click)="runRequired()">Run all required schemes</button>
      </div>
      <article *ngFor="let record of records">
        <header><b>{{record.id}}</b><code>{{record.status}}</code></header>
        <p>
          {{record.payload.source_scheme}} → {{record.payload.target_scheme}} ·
          coverage {{record.payload.validation?.coverage_ratio | percent:'1.0-2'}} ·
          warnings {{record.payload.validation?.warnings?.length || 0}}
        </p>
        <details>
          <summary>Mappings and validation</summary>
          <pre>{{record.payload | json}}</pre>
        </details>
        <div class="toolbar">
          <button
            (click)="review(record)"
            [disabled]="!record.payload.validation?.valid">
            Confirm final review
          </button>
          <input [(ngModel)]="versions[record.id]" placeholder="atlas-semantic-v0003">
          <button
            (click)="publish(record)"
            [disabled]="record.status !== 'REVIEWED'">
            Create semantic YAML
          </button>
        </div>
      </article>
      <p>{{message}}</p>
    </section>
  `,
  styles: [`
    .page{padding:24px}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
    input,button{padding:7px}article{border:1px solid #ddd;border-radius:6px;padding:14px;margin-top:16px}
    header{display:flex;justify-content:space-between}pre{background:#fafafa;padding:12px;max-height:360px;overflow:auto}
  `],
})
export class CrosswalkComponent implements OnInit {
  private api = inject(AtlasApiService);
  source = 'EastMoneyIndustry';
  target = 'ATLAS_CANONICAL';
  records: GovernanceRecord[] = [];
  versions: Record<string, string> = {};
  message = '';

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.governance('crosswalk').subscribe(result => {
      this.records = result.data;
      for (const record of this.records) {
        this.versions[record.id] ||= 'atlas-semantic-v0003';
      }
    });
  }

  run(): void {
    this.api.runCrosswalk(this.source, this.target).subscribe({
      next: () => {
        this.message = 'Crosswalk run completed.';
        this.load();
      },
      error: error => this.message = error.message,
    });
  }

  runRequired(): void {
    this.api.runRequiredCrosswalks().subscribe({
      next: result => {
        this.message = `${result.count} required crosswalk runs completed.`;
        this.load();
      },
      error: error => this.message = error.message,
    });
  }

  review(record: GovernanceRecord): void {
    this.api.reviewCrosswalk(record.id, record.payload).subscribe({
      next: () => {
        this.message = 'Crosswalk review confirmed.';
        this.load();
      },
      error: error => this.message = error.message,
    });
  }

  publish(record: GovernanceRecord): void {
    this.api.publishCrosswalk(record.id, this.versions[record.id]).subscribe({
      next: () => this.message = 'Semantic YAML containing the crosswalk was created.',
      error: error => this.message = error.message,
    });
  }
}
