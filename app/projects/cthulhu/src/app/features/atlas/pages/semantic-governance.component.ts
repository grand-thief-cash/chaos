import {CommonModule} from '@angular/common';
import {Component, OnInit, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {
  DiscoveryPayload,
  GovernanceRecord,
  ProposalStatus,
} from '../models/atlas.models';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-semantics',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <h1>Sample and semantic governance</h1>
      <div class="toolbar">
        <label>
          Sample size
          <input type="number" min="1" max="2000" [(ngModel)]="sampleSize">
        </label>
        <label *ngFor="let type of reportTypes">
          <input type="checkbox" [(ngModel)]="selected[type]"> {{type}}
        </label>
        <button (click)="start()">Run sample</button>
      </div>
      <p>
        The model proposes useful report types, predicates, and concepts.
        A reviewed proposal is required before an immutable YAML version can be created.
      </p>

      <article *ngFor="let record of records">
        <header>
          <b>{{record.id}}</b>
          <code>{{record.status}}</code>
        </header>
        <ng-container *ngIf="payload(record) as proposal">
          <h2>Report types</h2>
          <table>
            <thead>
              <tr>
                <th>Use</th><th>Type</th><th>Useful</th>
                <th>Prompt profile</th><th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let item of proposal.report_type_assessments">
                <td>
                  <input type="checkbox" [(ngModel)]="item.enabled_for_production">
                </td>
                <td>{{item.report_type}}</td>
                <td>{{item.useful_document_count}} / {{item.sampled_document_count}}</td>
                <td>
                  <input
                    [(ngModel)]="item.prompt_profile_key"
                    [required]="item.enabled_for_production"
                    placeholder="stock-v1">
                </td>
                <td>{{item.rationale}}</td>
              </tr>
            </tbody>
          </table>

          <div class="proposal-header">
            <h2>Predicates</h2>
            <button class="secondary" (click)="setAll(proposal.predicate_proposals, 'ACCEPTED')">
              Accept all
            </button>
            <button class="secondary" (click)="setAll(proposal.predicate_proposals, 'REJECTED')">
              Reject all
            </button>
          </div>
          <table>
            <thead>
              <tr><th>Status</th><th>Name</th><th>Types</th><th>Evidence count</th><th>Description</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let item of proposal.predicate_proposals">
                <td><select [(ngModel)]="item.status">
                  <option *ngFor="let status of statuses" [value]="status">{{status}}</option>
                </select></td>
                <td>{{item.canonical_name}}</td>
                <td>{{item.subject_types?.join(', ')}} → {{item.object_types?.join(', ')}}</td>
                <td>{{item.occurrence_count}}</td>
                <td>{{item.description}}</td>
              </tr>
            </tbody>
          </table>

          <div class="proposal-header">
            <h2>Concepts</h2>
            <button class="secondary" (click)="setAll(proposal.concept_proposals, 'ACCEPTED')">
              Accept all
            </button>
            <button class="secondary" (click)="setAll(proposal.concept_proposals, 'REJECTED')">
              Reject all
            </button>
          </div>
          <table>
            <thead>
              <tr><th>Status</th><th>Type</th><th>Name</th><th>Evidence count</th><th>Description</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let item of proposal.concept_proposals">
                <td><select [(ngModel)]="item.status">
                  <option *ngFor="let status of statuses" [value]="status">{{status}}</option>
                </select></td>
                <td>{{item.concept_type}}</td>
                <td>{{item.canonical_name}}</td>
                <td>{{item.occurrence_count}}</td>
                <td>{{item.description}}</td>
              </tr>
            </tbody>
          </table>

          <div class="actions">
            <button (click)="review(record, proposal)">Save reviewed proposal</button>
            <input [(ngModel)]="publishVersions[record.id]" placeholder="atlas-semantic-v0002">
            <button
              (click)="publish(record)"
              [disabled]="record.status !== 'REVIEWED'">
              Create immutable YAML
            </button>
          </div>
        </ng-container>
      </article>
      <p class="message">{{message}}</p>
    </section>
  `,
  styles: [`
    .page{padding:24px}.toolbar,.actions,.proposal-header{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
    button{padding:7px 14px;background:#1677ff;color:#fff;border:0;border-radius:4px;cursor:pointer}
    button.secondary{background:#5f6b7a}button:disabled{background:#aaa;cursor:not-allowed}
    article{border:1px solid #ddd;padding:16px;margin-top:16px;border-radius:6px}
    article header,.proposal-header{display:flex;justify-content:space-between}
    table{width:100%;border-collapse:collapse;margin-bottom:16px}
    th,td{border-bottom:1px solid #eee;text-align:left;padding:8px;vertical-align:top}
    input,select{padding:6px}.message{color:#1677ff}
  `],
})
export class SemanticGovernanceComponent implements OnInit {
  private api = inject(AtlasApiService);
  readonly reportTypes = ['stock', 'industry', 'macro', 'new_stock', 'strategy', 'morning_report'];
  readonly statuses: ProposalStatus[] = ['PROPOSED', 'ACCEPTED', 'REJECTED'];
  selected: Record<string, boolean> = Object.fromEntries(this.reportTypes.map(value => [value, true]));
  publishVersions: Record<string, string> = {};
  sampleSize = 120;
  records: GovernanceRecord[] = [];
  message = '';

  ngOnInit(): void {
    this.load();
  }

  payload(record: GovernanceRecord): DiscoveryPayload {
    return record.payload as DiscoveryPayload;
  }

  load(): void {
    this.api.governance('discovery').subscribe(result => {
      this.records = result.data;
      for (const record of this.records) {
        this.publishVersions[record.id] ||= 'atlas-semantic-v0002';
      }
    });
  }

  start(): void {
    this.api.startDiscovery(
      this.sampleSize,
      this.reportTypes.filter(value => this.selected[value]),
    ).subscribe({
      next: () => {
        this.message = 'Sample discovery completed.';
        this.load();
      },
      error: error => this.message = error.message,
    });
  }

  setAll(items: Array<{status: ProposalStatus}>, status: ProposalStatus): void {
    for (const item of items) {
      item.status = status;
    }
  }

  review(record: GovernanceRecord, proposal: DiscoveryPayload): void {
    this.api.reviewDiscovery(record.id, proposal).subscribe({
      next: () => {
        this.message = 'Reviewed proposal saved.';
        this.load();
      },
      error: error => this.message = error.message,
    });
  }

  publish(record: GovernanceRecord): void {
    this.api.publishSemantic(record.id, this.publishVersions[record.id]).subscribe({
      next: () => this.message = 'Immutable semantic YAML created. Activate it through deployment configuration.',
      error: error => this.message = error.message,
    });
  }
}
