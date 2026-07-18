import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTimelineModule } from 'ng-zorro-antd/timeline';
import { FeatureNumericValue, FeatureRun, FeatureRunDetail, FeatureRunItem } from '../models/feature-platform.models';
import { featurePlatformError, isDirtyRevision } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-run-detail-page',
  standalone: true,
  imports: [CommonModule, RouterLink, NzButtonModule, NzEmptyModule, NzProgressModule, NzSpinModule, NzTableModule, NzTimelineModule, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page">
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      <nz-spin [nzSpinning]="loading">
        @if (detail; as data) {
          <section class="fp-panel">
            <div class="fp-panel-title">
              <div><div class="fp-eyebrow">Persisted execution</div><h2>Run Detail</h2><div class="fp-code">{{ data.run.run_id }}</div></div>
              <div class="fp-actions"><app-feature-status-badge [status]="data.run.status"></app-feature-status-badge><a nz-button [routerLink]="['../../values']" [queryParams]="{ run_id: data.run.run_id }">Inspect values</a></div>
            </div>
            @if (isPartial(data.items)) { <div class="fp-alert"><strong>Partial execution evidence.</strong> Successful and failed/skipped items coexist; this Run must not be presented as fully successful.</div> }
            @if (dirty(data.run)) { <div class="fp-alert"><strong>Non-reproducible build.</strong> Code revision <span class="fp-code">{{ data.run.code_revision }}</span> is dirty.</div> }
            @if (data.run.error_code) { <div class="fp-alert danger"><strong>{{ data.run.error_code }}</strong> {{ data.run.error_message }}</div> }
            <div class="fp-meta-grid" style="margin-top:12px">
              <div class="fp-meta"><label>Source / Market</label><span class="fp-code">{{ data.run.source_profile }}</span> · {{ data.run.market }}</div>
              <div class="fp-meta"><label>Producer</label>{{ data.run.producer_service }} · {{ data.run.worker_id || 'unassigned' }}</div>
              <div class="fp-meta"><label>As-of</label>{{ data.run.as_of_time | date:'medium' }}</div>
              <div class="fp-meta"><label>Data cutoff</label>{{ data.run.data_cutoff_time | date:'medium' }}</div>
              <div class="fp-meta"><label>Subject count</label>{{ data.subjects?.length ?? 'not loaded' }}</div>
              <div class="fp-meta"><label>Revision</label><span class="fp-code">{{ data.run.code_revision }}</span></div>
              <div class="fp-meta"><label>Retry of</label>@if (data.run.retry_of_run_id) { <a class="fp-link fp-code" [routerLink]="['../../runs', data.run.retry_of_run_id]">{{ data.run.retry_of_run_id }}</a> } @else { Original run }</div>
              <div class="fp-meta"><label>Backfill</label>{{ data.run.backfill_id || 'none' }} @if (data.run.backfill_attempt != null) { · attempt {{ data.run.backfill_attempt }} }</div>
            </div>
          </section>

          <section class="timeline-layout">
            <div class="fp-panel">
              <div class="fp-panel-title"><h3>Status timeline</h3><span class="fp-muted">heartbeat {{ data.run.heartbeat_at ? (data.run.heartbeat_at | date:'mediumTime') : 'n/a' }}</span></div>
              <nz-timeline>
                <nz-timeline-item nzColor="blue"><strong>Created</strong><div>{{ data.run.created_at | date:'medium' }}</div></nz-timeline-item>
                @if (data.run.started_at) { <nz-timeline-item nzColor="blue"><strong>Started</strong><div>{{ data.run.started_at | date:'medium' }}</div></nz-timeline-item> }
                @if (data.run.heartbeat_at && !data.run.finished_at) { <nz-timeline-item nzColor="green"><strong>Last heartbeat</strong><div>{{ data.run.heartbeat_at | date:'medium' }}</div></nz-timeline-item> }
                @if (data.run.finished_at) { <nz-timeline-item [nzColor]="data.run.status === 'succeeded' ? 'green' : 'red'"><strong>{{ data.run.status }}</strong><div>{{ data.run.finished_at | date:'medium' }}</div></nz-timeline-item> }
              </nz-timeline>
            </div>
            <div class="fp-panel">
              <div class="fp-panel-title"><h3>Request contract</h3></div>
              <div class="fp-meta"><label>Fingerprint</label><span class="fp-code">{{ data.run.request_fingerprint }}</span></div>
              <div class="fp-meta"><label>Universe hash</label><span class="fp-code">{{ data.run.universe_hash }}</span></div>
              <pre class="fp-json">{{ data.run.request_payload | json }}</pre>
            </div>
          </section>

          <section class="fp-panel">
            <div class="fp-panel-title"><div><div class="fp-eyebrow">Dependency-closed work units</div><h3>Run Items</h3></div><span class="fp-muted">{{ data.items.length }} items</span></div>
            <nz-table #itemsTable [nzData]="data.items" nzSize="small" [nzShowPagination]="false">
              <thead><tr><th>Version ID</th><th>Status</th><th>Input</th><th>Output</th><th>Valid</th><th>Missing</th><th>Invalid</th><th>Coverage</th><th>Duration</th><th>Quality / error</th></tr></thead>
              <tbody>@for (item of itemsTable.data; track item.feature_version_id) {<tr>
                <td class="fp-code">{{ item.feature_version_id }}</td><td><app-feature-status-badge [status]="item.status"></app-feature-status-badge></td>
                <td>{{ item.input_count }}</td><td>{{ item.output_count }}</td><td>{{ item.valid_count }}</td><td>{{ item.missing_count }}</td><td>{{ item.invalid_count }}</td>
                <td><nz-progress [nzPercent]="coverage(item)" nzSize="small" [nzStatus]="item.status === 'failed' ? 'exception' : 'normal'"></nz-progress></td>
                <td>{{ item.duration_ms }} ms</td>
                <td>@if (item.error_code) { <div class="fp-alert danger" style="padding:6px"><span class="fp-code">{{ item.error_code }}</span> {{ item.error_message }}</div> }<pre class="fp-json">{{ item.quality_summary | json }}</pre></td>
              </tr>}</tbody>
            </nz-table>
          </section>

          <section class="fp-panel">
            <div class="fp-panel-title"><h3>Subject Snapshot</h3><span class="fp-muted">Showing first {{ visibleSubjects(data).length }} of {{ data.subjects?.length || 0 }}</span></div>
            @if (!data.subjects?.length) { <nz-empty nzNotFoundContent="No subjects were returned."></nz-empty> }
            <div class="fp-chip-list">@for (subject of visibleSubjects(data); track subject.security_id) { <span class="fp-chip">#{{ subject.security_id }} · {{ subject.symbol_snapshot || 'symbol n/a' }} · {{ subject.exchange_snapshot }}</span> }</div>
          </section>

          <section class="fp-panel">
            <div class="fp-panel-title"><h3>Numeric Value Sample</h3><a class="fp-link" [routerLink]="['../../values']" [queryParams]="{ run_id: data.run.run_id }">Open full preview</a></div>
            @if (!values.length) { <nz-empty nzNotFoundContent="No numeric values are visible for this Run."></nz-empty> }
            <nz-table #valueTable [nzData]="values" nzSize="small" [nzShowPagination]="false">
              <thead><tr><th>Version</th><th>Security</th><th>Observed</th><th>Value</th><th>Status</th><th>Source available</th></tr></thead>
              <tbody>@for (value of valueTable.data; track value.feature_version_id + '-' + value.security_id + '-' + value.observed_at) {<tr>
                <td>{{ value.feature_version_id }}</td><td>{{ value.security_id }}</td><td>{{ value.observed_at | date:'medium' }}</td><td>{{ value.value ?? '-' }}</td><td><app-feature-status-badge [status]="value.value_status"></app-feature-status-badge></td><td>{{ value.source_max_available_at ? (value.source_max_available_at | date:'medium') : '-' }}</td>
              </tr>}</tbody>
            </nz-table>
          </section>
        }
      </nz-spin>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .timeline-layout { display:grid; grid-template-columns:minmax(260px,.8fr) minmax(320px,1.2fr); gap:16px; }
    @media(max-width:850px){.timeline-layout{grid-template-columns:1fr}}
  `],
})
export class RunDetailPageComponent implements OnInit, OnDestroy {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly route = inject(ActivatedRoute);
  detail: FeatureRunDetail | null = null;
  values: FeatureNumericValue[] = [];
  loading = true;
  error: ReturnType<typeof featurePlatformError> | null = null;
  private runId = '';
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.runId = this.route.snapshot.paramMap.get('runId') || '';
    this.load();
    this.timer = setInterval(() => { if (this.detail && this.isActive(this.detail.run.status)) this.load(false); }, 5_000);
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading = true;
    forkJoin({
      detail: this.api.getRun(this.runId, true),
      values: this.api.queryValues({ run_id: this.runId, limit: 20 }).pipe(catchError(() => of({ items: [], total: 0, limit: 20, offset: 0 }))),
    }).subscribe({
      next: ({ detail, values }) => { this.detail = detail; this.values = values.items; this.loading = false; },
      error: (error) => { this.error = featurePlatformError(error); this.loading = false; },
    });
  }

  coverage(item: FeatureRunItem): number { return item.input_count > 0 ? Math.round(item.valid_count / item.input_count * 1000) / 10 : 0; }
  visibleSubjects(data: FeatureRunDetail) { return (data.subjects || []).slice(0, 40); }
  isPartial(items: FeatureRunItem[]): boolean { return items.some((item) => item.status === 'succeeded') && items.some((item) => item.status !== 'succeeded'); }
  dirty(run: FeatureRun): boolean { return isDirtyRevision(run.code_revision); }
  isActive(status: string): boolean { return ['queued', 'planning', 'running', 'validating'].includes(status); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }
}
