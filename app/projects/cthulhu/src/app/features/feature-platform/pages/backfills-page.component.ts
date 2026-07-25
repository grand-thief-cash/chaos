import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import type { EChartsOption } from 'echarts';
import { NgxEchartsModule } from 'ngx-echarts';
import { Subject, takeUntil } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzTableModule } from 'ng-zorro-antd/table';
import {
  FeatureBackfillDetail,
  FeatureBackfillJob,
  FeatureBackfillPreview,
  FeatureBackfillRequest,
  FeatureRun,
  FeatureScopeDraft,
  FeatureScopeRequest,
} from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureScopeEditorComponent } from '../ui/feature-scope-editor.component';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-backfills-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NgxEchartsModule, NzButtonModule, NzEmptyModule,
    NzInputModule, NzProgressModule, NzSelectModule, NzSpinModule, NzStatisticModule,
    NzTableModule, FeatureScopeEditorComponent, FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page">
      <section class="backfill-layout">
        <div class="fp-panel">
          <div class="fp-panel-title">
            <div><div class="fp-eyebrow">Persisted range execution</div><h2>Create Backfill</h2></div>
            <app-feature-status-badge [status]="impact ? 'previewed' : 'needs_preview'"></app-feature-status-badge>
          </div>
          <app-feature-scope-editor [draft]="draft" (draftChange)="updateDraft($event)"></app-feature-scope-editor>
          <div class="form-grid">
            <div class="fp-field"><label>Max concurrency</label><input nz-input type="number" min="1" max="32" [(ngModel)]="maxConcurrency" (ngModelChange)="scopeChanged()" /></div>
          </div>
          <div class="fp-actions" style="margin-top:14px">
            <button nz-button nzType="primary" (click)="previewImpact()" [nzLoading]="previewing">Preview impact</button>
            <button nz-button nzType="primary" nzDanger (click)="create()" [disabled]="!canCreate()" [nzLoading]="creating">Create {{ impact?.run_count || 0 }} Runs</button>
          </div>
          @if (error) { <div class="fp-alert danger" style="margin-top:12px"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
        </div>

        <aside class="fp-panel impact-card">
          <div class="fp-panel-title"><h3>Confirmed Impact</h3></div>
          @if (impact; as preview) {
            <div class="impact-grid">
              <nz-statistic nzTitle="Runs" [nzValue]="preview.run_count"></nz-statistic>
              <nz-statistic nzTitle="Subjects / Run" [nzValue]="preview.subject_count"></nz-statistic>
              <nz-statistic nzTitle="Execution cells" [nzValue]="preview.estimated_execution_cells"></nz-statistic>
              <nz-statistic nzTitle="Concurrency" [nzValue]="preview.max_concurrency"></nz-statistic>
            </div>
            <div class="fp-meta"><label>Token expires</label>{{ preview.confirmation_expires_at | date:'medium' }}</div>
            <div class="fp-meta"><label>Universe hash</label><span class="fp-code">{{ preview.scope.universe_hash }}</span></div>
            <div class="fp-meta"><label>Plan checksum</label><span class="fp-code">{{ preview.plan.plan_checksum }}</span></div>
            @for (warning of preview.warnings; track warning) { <div class="fp-alert">{{ warning }}</div> }
          } @else {
            <nz-empty nzNotFoundContent="Preview freezes scope, plan and cost before creation."></nz-empty>
          }
        </aside>
      </section>

      <section class="fp-panel">
        <div class="fp-panel-title">
          <div><div class="fp-eyebrow">Persistent orchestration</div><h2>Backfill Jobs</h2></div>
          <div class="fp-actions">
            <nz-select [(ngModel)]="statusFilter" (ngModelChange)="loadJobs()" nzAllowClear nzPlaceHolder="All statuses" style="width:170px">
              @for (status of statuses; track status) { <nz-option [nzValue]="status" [nzLabel]="status"></nz-option> }
            </nz-select>
            <button nz-button (click)="loadJobs()" [nzLoading]="loadingJobs">Refresh</button>
          </div>
        </div>
        <nz-table #jobTable [nzData]="jobs" nzSize="small" [nzPageSize]="20">
          <thead><tr><th>Created</th><th>Job</th><th>Status</th><th>Range</th><th>Progress</th><th></th></tr></thead>
          <tbody>@for (job of jobTable.data; track job.backfill_id) {<tr [class.selected-row]="detail?.job?.backfill_id === job.backfill_id">
            <td>{{ job.created_at | date:'short' }}</td><td class="fp-code">{{ job.backfill_id }}</td>
            <td><app-feature-status-badge [status]="job.status"></app-feature-status-badge></td>
            <td>{{ job.start_as_of | date:'shortDate' }} - {{ job.end_as_of | date:'shortDate' }}</td>
            <td style="min-width:180px"><nz-progress [nzPercent]="progress(job)" nzSize="small"></nz-progress><span class="fp-muted">{{ job.succeeded_count }} ok / {{ job.failed_count }} failed / {{ job.total_count }} total</span></td>
            <td><button nz-button nzSize="small" (click)="selectJob(job)">Inspect</button></td>
          </tr>}</tbody>
        </nz-table>
      </section>

      @if (detail; as data) {
        <section class="fp-panel">
          <div class="fp-panel-title">
            <div><div class="fp-eyebrow">Date status matrix</div><h2>{{ data.job.backfill_id }}</h2></div>
            <div class="fp-actions">
              <app-feature-status-badge [status]="data.job.status"></app-feature-status-badge>
              <button nz-button nzDanger (click)="cancel()" [disabled]="!canCancel(data.job)" [nzLoading]="acting">Cancel remaining</button>
              <button nz-button (click)="retryFailed()" [disabled]="!data.job.failed_count" [nzLoading]="acting">Retry failed</button>
            </div>
          </div>
          <section class="job-summary">
            <div><span>Completion</span><strong>{{ progress(data.job) }}%</strong></div>
            <div><span>Failed</span><strong>{{ data.job.failed_count }}</strong></div>
            <div><span>Active / queued</span><strong>{{ activeCount(data.runs) }} / {{ queuedCount(data.runs) }}</strong></div>
            <div><span>Estimated remaining</span><strong>{{ eta(data.runs, data.job.max_concurrency) }}</strong></div>
          </section>
          <div echarts [options]="heatmapOptions" (chartClick)="openRunFromChart($event)" class="backfill-heatmap"></div>
          @if (errorGroups(data.runs).length) {
            <div class="error-grid">
              @for (group of errorGroups(data.runs); track group.code) {
                <div class="fp-alert danger"><strong>{{ group.code }}</strong><span>{{ group.count }} latest attempts</span><small>{{ group.message }}</small></div>
              }
            </div>
          }
          <nz-table #runTable [nzData]="latestRuns(data.runs)" nzSize="small" [nzPageSize]="25">
            <thead><tr><th>As-of</th><th>Attempt</th><th>Status</th><th>Run ID</th><th>Error</th><th></th></tr></thead>
            <tbody>@for (run of runTable.data; track run.run_id) {<tr>
              <td>{{ run.as_of_time | date:'medium' }}</td><td>{{ run.backfill_attempt }}</td>
              <td><app-feature-status-badge [status]="run.status"></app-feature-status-badge></td>
              <td class="fp-code">{{ run.run_id }}</td><td><span class="fp-code">{{ run.error_code }}</span> {{ run.error_message }}</td>
              <td><button nz-button nzSize="small" (click)="openRun(run.run_id)">Run detail</button></td>
            </tr>}</tbody>
          </nz-table>
        </section>
      }
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .backfill-layout{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(290px,.55fr);gap:16px;align-items:start}
    .impact-card{position:sticky;top:12px}.impact-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
    .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
    .job-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
    .job-summary div{padding:12px;border:1px solid #d8d3c9;background:#faf8f3}.job-summary span{display:block;color:#777;font-size:11px;text-transform:uppercase}.job-summary strong{font-size:20px}
    .backfill-heatmap{height:320px;width:100%;background:linear-gradient(145deg,#fffdf8,#eef3f0)}
    .error-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}.error-grid .fp-alert{display:grid}
    .selected-row{background:#fff7e8}
    @media(max-width:980px){.backfill-layout{grid-template-columns:1fr}.impact-card{position:static}.job-summary{grid-template-columns:1fr 1fr}}
    @media(max-width:600px){.form-grid,.impact-grid,.job-summary,.error-grid{grid-template-columns:1fr}}
  `],
})
export class BackfillsPageComponent implements OnInit, OnDestroy {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly router = inject(Router);
  private readonly destroy$ = new Subject<void>();
  private refreshTimer?: ReturnType<typeof setInterval>;

  draft = this.defaultDraft();
  maxConcurrency = 2;
  impact: FeatureBackfillPreview | null = null;
  jobs: FeatureBackfillJob[] = [];
  detail: FeatureBackfillDetail | null = null;
  statusFilter: string | null = null;
  readonly statuses = ['queued', 'running', 'succeeded', 'partially_succeeded', 'failed', 'cancelled'];
  previewing = false;
  creating = false;
  loadingJobs = false;
  acting = false;
  error: ReturnType<typeof featurePlatformError> | null = null;
  heatmapOptions: EChartsOption = {};

  ngOnInit(): void {
    this.loadJobs();
    this.refreshTimer = setInterval(() => {
      this.loadJobs(false);
      if (this.detail && ['queued', 'running'].includes(this.detail.job.status)) {
        this.loadDetail(this.detail.job.backfill_id, false);
      }
    }, 5_000);
  }

  updateDraft(draft: FeatureScopeDraft): void {
    this.draft = { ...draft, evaluationMode: 'range' };
    this.scopeChanged();
  }

  scopeChanged(): void { this.impact = null; }

  previewImpact(): void {
    const request = this.request();
    if (!request) return;
    this.previewing = true;
    this.error = null;
    this.api.previewBackfill(request).pipe(takeUntil(this.destroy$)).subscribe({
      next: (impact) => { this.impact = impact; this.previewing = false; },
      error: (error) => { this.error = featurePlatformError(error); this.previewing = false; },
    });
  }

  create(): void {
    const request = this.request();
    if (!request || !this.impact || !this.canCreate()) return;
    this.creating = true;
    this.error = null;
    this.api.createBackfill({ ...request, confirmation_token: this.impact.confirmation_token }).pipe(takeUntil(this.destroy$)).subscribe({
      next: (detail) => {
        this.creating = false;
        this.impact = null;
        this.detail = detail;
        this.buildHeatmap();
        this.loadJobs(false);
      },
      error: (error) => { this.error = featurePlatformError(error); this.creating = false; },
    });
  }

  canCreate(): boolean {
    return Boolean(this.impact && new Date(this.impact.confirmation_expires_at).getTime() > Date.now());
  }

  loadJobs(showSpinner = true): void {
    if (showSpinner) this.loadingJobs = true;
    this.api.listBackfills({
      status: this.statusFilter || undefined,
      source_profile: this.draft.sourceProfile,
      limit: 200,
    }).pipe(takeUntil(this.destroy$)).subscribe({
      next: (response) => { this.jobs = response.items; this.loadingJobs = false; },
      error: (error) => { this.error = featurePlatformError(error); this.loadingJobs = false; },
    });
  }

  selectJob(job: FeatureBackfillJob): void { this.loadDetail(job.backfill_id); }

  loadDetail(backfillId: string, showSpinner = true): void {
    if (showSpinner) this.acting = true;
    const profile = this.jobs.find((job) => job.backfill_id === backfillId)?.source_profile || this.draft.sourceProfile;
    this.api.getBackfill(backfillId, profile).pipe(takeUntil(this.destroy$)).subscribe({
      next: (detail) => { this.detail = detail; this.buildHeatmap(); this.acting = false; },
      error: (error) => { this.error = featurePlatformError(error); this.acting = false; },
    });
  }

  cancel(): void {
    if (!this.detail || !this.canCancel(this.detail.job)) return;
    this.acting = true;
    this.api.cancelBackfill(
      this.detail.job.backfill_id,
      this.detail.job.source_profile,
    ).pipe(takeUntil(this.destroy$)).subscribe({
      next: () => { this.loadDetail(this.detail!.job.backfill_id, false); this.loadJobs(false); },
      error: (error) => { this.error = featurePlatformError(error); this.acting = false; },
    });
  }

  retryFailed(): void {
    if (!this.detail) return;
    this.acting = true;
    this.api.retryFailedBackfill(
      this.detail.job.backfill_id,
      this.detail.job.source_profile,
    ).pipe(takeUntil(this.destroy$)).subscribe({
      next: () => { this.loadDetail(this.detail!.job.backfill_id, false); this.loadJobs(false); },
      error: (error) => { this.error = featurePlatformError(error); this.acting = false; },
    });
  }

  progress(job: FeatureBackfillJob): number {
    return job.total_count ? Math.round((job.succeeded_count + job.failed_count) / job.total_count * 1000) / 10 : 0;
  }

  canCancel(job: FeatureBackfillJob): boolean { return ['queued', 'running'].includes(job.status); }
  activeCount(runs: FeatureRun[]): number { return this.latestRuns(runs).filter((run) => ['planning', 'running', 'validating'].includes(run.status)).length; }
  queuedCount(runs: FeatureRun[]): number { return this.latestRuns(runs).filter((run) => run.status === 'queued').length; }

  latestRuns(runs: FeatureRun[]): FeatureRun[] {
    const latest = new Map<string, FeatureRun>();
    for (const run of runs) {
      const key = run.as_of_time;
      const old = latest.get(key);
      if (!old || (run.backfill_attempt || 0) > (old.backfill_attempt || 0)) latest.set(key, run);
    }
    return [...latest.values()].sort((a, b) => a.as_of_time.localeCompare(b.as_of_time));
  }

  errorGroups(runs: FeatureRun[]): Array<{ code: string; message: string; count: number }> {
    const groups = new Map<string, { code: string; message: string; count: number }>();
    for (const run of this.latestRuns(runs)) {
      if (!run.error_code) continue;
      const old = groups.get(run.error_code) || { code: run.error_code, message: run.error_message, count: 0 };
      old.count += 1;
      groups.set(run.error_code, old);
    }
    return [...groups.values()].sort((a, b) => b.count - a.count);
  }

  eta(runs: FeatureRun[], concurrency: number): string {
    const latest = this.latestRuns(runs);
    const durations = latest.filter((run) => run.started_at && run.finished_at)
      .map((run) => new Date(run.finished_at!).getTime() - new Date(run.started_at!).getTime())
      .filter((value) => value > 0);
    const remaining = latest.filter((run) => ['queued', 'planning', 'running', 'validating'].includes(run.status)).length;
    if (!durations.length || !remaining) return remaining ? 'estimating' : 'complete';
    const average = durations.reduce((sum, value) => sum + value, 0) / durations.length;
    const seconds = Math.ceil(average * remaining / Math.max(1, concurrency) / 1000);
    return seconds >= 3600 ? `${Math.ceil(seconds / 3600)}h` : seconds >= 60 ? `${Math.ceil(seconds / 60)}m` : `${seconds}s`;
  }

  openRun(runId: string): void { this.router.navigate(['/workbench/features/runs', runId]); }

  openRunFromChart(event: unknown): void {
    const params = event as { value?: [string, number, string] };
    if (params.value?.[2]) this.openRun(params.value[2]);
  }

  private buildHeatmap(): void {
    if (!this.detail) { this.heatmapOptions = {}; return; }
    const statusValue: Record<string, number> = { queued: 0, planning: 1, running: 2, validating: 2, succeeded: 3, partially_succeeded: 4, failed: 4, aborted: 4, cancelled: 5 };
    const runs = this.latestRuns(this.detail.runs);
    this.heatmapOptions = {
      tooltip: {
        formatter: (params: unknown) => {
          const value = (params as { value: [string, number, string, string] }).value;
          return `<strong>${value[0]}</strong><br>${value[3]}<br>${value[2]}`;
        },
      },
      visualMap: {
        type: 'piecewise', dimension: 1, orient: 'horizontal', top: 8, left: 'center',
        pieces: [
          { value: 0, label: 'queued', color: '#9aa5a7' }, { value: 1, label: 'planning', color: '#6f91a2' },
          { value: 2, label: 'running', color: '#d49b34' }, { value: 3, label: 'succeeded', color: '#4b8062' },
          { value: 4, label: 'failed', color: '#b44137' }, { value: 5, label: 'cancelled', color: '#756f68' },
        ],
      },
      calendar: {
        top: 78, left: 48, right: 25, cellSize: ['auto', 24],
        range: [this.detail.job.start_as_of.slice(0, 10), this.detail.job.end_as_of.slice(0, 10)],
        itemStyle: { borderWidth: 3, borderColor: '#fff' },
        yearLabel: { show: false },
      },
      series: [{
        type: 'heatmap', coordinateSystem: 'calendar',
        data: runs.map((run) => [run.as_of_time.slice(0, 10), statusValue[run.status] ?? 4, run.run_id, run.status]),
        label: { show: true, formatter: (params: unknown) => String((params as { value: unknown[] }).value[3]).slice(0, 1).toUpperCase(), color: '#fff' },
      }],
    };
  }

  private request(): FeatureBackfillRequest | null {
    if (!this.draft.featureCode || !this.draft.version) {
      this.error = { code: 'FEATURE_REQUIRED', message: 'Choose a published Feature version.' };
      return null;
    }
    if (this.draft.evaluationMode !== 'range' || !this.draft.startAsOf || !this.draft.endAsOf) {
      this.error = { code: 'BACKFILL_RANGE_REQUIRED', message: 'Backfill requires a bounded date range.' };
      return null;
    }
    const securityIds = this.draft.securityIdsText.split(/[\s,]+/).filter(Boolean).map(Number);
    if (this.draft.universeMode === 'explicit' && (!securityIds.length || securityIds.some((id) => !Number.isInteger(id) || id <= 0))) {
      this.error = { code: 'UNIVERSE_REQUIRED', message: 'Explicit universe requires positive Security IDs.' };
      return null;
    }
    const scope: FeatureScopeRequest = {
      feature_refs: [{ code: this.draft.featureCode, version: this.draft.version }],
      universe: { mode: this.draft.universeMode, security_ids: this.draft.universeMode === 'explicit' ? [...new Set(securityIds)] : [] },
      evaluation: {
        mode: 'range',
        start_as_of: new Date(this.draft.startAsOf).toISOString(),
        end_as_of: new Date(this.draft.endAsOf).toISOString(),
        step: this.draft.step,
      },
      data_cutoff_policy: this.draft.cutoffMode === 'lag_seconds'
        ? { mode: 'lag_seconds', seconds: this.draft.cutoffLagSeconds }
        : { mode: 'same_as_as_of' },
      market: this.draft.market,
      source_profile: this.draft.sourceProfile,
    };
    return { ...scope, max_concurrency: this.maxConcurrency };
  }

  private defaultDraft(): FeatureScopeDraft {
    const end = new Date();
    end.setMinutes(end.getMinutes() - end.getTimezoneOffset());
    const start = new Date(end);
    start.setMonth(start.getMonth() - 6);
    return {
      featureCode: '', version: null, universeMode: 'explicit', securityIdsText: '',
      evaluationMode: 'range', asOf: '', startAsOf: start.toISOString().slice(0, 16),
      endAsOf: end.toISOString().slice(0, 16), step: 'monthly',
      cutoffMode: 'same_as_as_of', cutoffLagSeconds: 0, market: 'CN', sourceProfile: 'default',
    };
  }

  ngOnDestroy(): void {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.destroy$.next();
    this.destroy$.complete();
  }
}
