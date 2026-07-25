import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
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
  FeatureDataPurgeJob,
  FeaturePurgeDetail,
  FeaturePurgePreviewRequest,
  FeaturePurgePreviewResponse,
  FeaturePurgeScope,
} from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-purges-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzButtonModule, NzEmptyModule, NzInputModule,
    NzProgressModule, NzSelectModule, NzSpinModule, NzStatisticModule, NzTableModule,
    FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page">
      <section class="purge-layout">
        <div class="fp-panel">
          <div class="fp-panel-title">
            <div><div class="fp-eyebrow">Destructive data operation</div><h2>Preview Value Purge</h2></div>
            <app-feature-status-badge [status]="preview ? 'previewed' : 'needs_preview'"></app-feature-status-badge>
          </div>
          <div class="fp-alert">
            Purge removes only materialized values. Run, RunItem, Feature Version, Backfill and lifecycle evidence remain available for inspection.
          </div>
          <div class="form-grid">
            <div class="fp-field">
              <label>Scope</label>
              <nz-select [(ngModel)]="scopeType" (ngModelChange)="scopeChanged()">
                <nz-option nzValue="run" nzLabel="One Run"></nz-option>
                <nz-option nzValue="feature_version" nzLabel="One Feature Version"></nz-option>
                <nz-option nzValue="feature_all_versions" nzLabel="Feature, all versions"></nz-option>
              </nz-select>
            </div>
            @if (scopeType === 'run') {
              <div class="fp-field"><label>Run ID</label><input nz-input [(ngModel)]="runId" (ngModelChange)="scopeChanged()" placeholder="UUID" /></div>
            }
            @if (scopeType === 'feature_version') {
              <div class="fp-field"><label>Feature Version ID</label><input nz-input type="number" min="1" [(ngModel)]="featureVersionId" (ngModelChange)="scopeChanged()" /></div>
            }
            @if (scopeType === 'feature_all_versions') {
              <div class="fp-field"><label>Feature code</label><input nz-input [(ngModel)]="featureCode" (ngModelChange)="scopeChanged()" placeholder="financial.pe_ratio" /></div>
              <label class="all-versions"><input type="checkbox" [(ngModel)]="allVersions" (ngModelChange)="scopeChanged()" /> I explicitly include every version</label>
            }
          </div>
          <div class="fp-actions" style="margin-top:14px">
            <button nz-button nzType="primary" (click)="previewImpact()" [nzLoading]="previewing">Preview impact</button>
            <button nz-button (click)="clearPreview()" [disabled]="!preview">Reset confirmation</button>
          </div>
          @if (error) { <div class="fp-alert danger" style="margin-top:12px"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
        </div>

        <aside class="fp-panel impact-card">
          <div class="fp-panel-title"><h3>Frozen Impact</h3></div>
          @if (preview; as data) {
            <div class="impact-grid">
              <nz-statistic nzTitle="Rows" [nzValue]="data.job.estimated_rows"></nz-statistic>
              <nz-statistic nzTitle="Runs" [nzValue]="data.job.affected_run_count"></nz-statistic>
              <nz-statistic nzTitle="Versions" [nzValue]="data.job.affected_version_count"></nz-statistic>
              <nz-statistic nzTitle="Targets" [nzValue]="data.targets.length"></nz-statistic>
            </div>
            @if (data.job.affects_latest) { <div class="fp-alert danger"><strong>Latest affected.</strong> Latest-value reads may fall back to an older available Run.</div> }
            @for (warning of data.warnings; track warning) { <div class="fp-alert">{{ warning }}</div> }
            <div class="fp-meta"><label>Confirmation expires</label>{{ data.job.confirmation_expires_at | date:'medium' }}</div>
            <div class="fp-field confirmation">
              <label>Type exactly: <span class="fp-code">{{ data.job.confirmation_text }}</span></label>
              <input nz-input [(ngModel)]="confirmationText" placeholder="Exact confirmation text" />
            </div>
            <button nz-button nzType="primary" nzDanger class="submit-purge" (click)="submit()" [disabled]="!canSubmit()" [nzLoading]="submitting">Queue permanent purge</button>
          } @else {
            <nz-empty nzNotFoundContent="Preview is required before a purge can be confirmed."></nz-empty>
          }
        </aside>
      </section>

      <section class="fp-panel">
        <div class="fp-panel-title">
          <div><div class="fp-eyebrow">Retention history</div><h2>Purge Jobs</h2></div>
          <div class="fp-actions">
            <nz-select [(ngModel)]="scopeFilter" (ngModelChange)="loadJobs()" nzAllowClear nzPlaceHolder="All scopes" style="width:190px">
              <nz-option nzValue="run" nzLabel="Run"></nz-option>
              <nz-option nzValue="feature_version" nzLabel="Feature Version"></nz-option>
              <nz-option nzValue="feature_all_versions" nzLabel="All Versions"></nz-option>
            </nz-select>
            <nz-select [(ngModel)]="statusFilter" (ngModelChange)="loadJobs()" nzAllowClear nzPlaceHolder="All statuses" style="width:160px">
              @for (status of statuses; track status) { <nz-option [nzValue]="status" [nzLabel]="status"></nz-option> }
            </nz-select>
            <button nz-button (click)="loadJobs()" [nzLoading]="loadingJobs">Refresh</button>
          </div>
        </div>
        <nz-table #jobTable [nzData]="jobs" nzSize="small" [nzPageSize]="20">
          <thead><tr><th>Created</th><th>Purge</th><th>Scope</th><th>Status</th><th>Rows</th><th></th></tr></thead>
          <tbody>@for (job of jobTable.data; track job.purge_id) {<tr [class.selected-row]="detail?.job?.purge_id === job.purge_id">
            <td>{{ job.created_at | date:'short' }}</td>
            <td class="fp-code">{{ job.purge_id }}</td><td>{{ job.scope_type }}</td>
            <td><app-feature-status-badge [status]="job.status"></app-feature-status-badge></td>
            <td>{{ job.deleted_rows }} / {{ job.estimated_rows }}</td>
            <td><button nz-button nzSize="small" (click)="selectJob(job)">Inspect</button></td>
          </tr>}</tbody>
        </nz-table>
      </section>

      @if (detail; as data) {
        <section class="fp-panel">
          <div class="fp-panel-title">
            <div><div class="fp-eyebrow">Per-RunItem deletion</div><h2>{{ data.job.purge_id }}</h2></div>
            <div class="fp-actions">
              <app-feature-status-badge [status]="data.job.status"></app-feature-status-badge>
              <button nz-button nzDanger (click)="cancel()" [disabled]="!canCancel(data.job)" [nzLoading]="acting">Cancel before start</button>
            </div>
          </div>
          <nz-progress [nzPercent]="progress(data)" [nzStatus]="data.job.status === 'failed' ? 'exception' : 'normal'"></nz-progress>
          <div class="detail-grid">
            <div><span>Deleted rows</span><strong>{{ data.job.deleted_rows }}</strong></div>
            <div><span>Estimated rows</span><strong>{{ data.job.estimated_rows }}</strong></div>
            <div><span>Latest affected</span><strong>{{ data.job.affects_latest ? 'yes' : 'no' }}</strong></div>
            <div><span>Finished</span><strong>{{ data.job.finished_at ? (data.job.finished_at | date:'short') : 'pending' }}</strong></div>
          </div>
          @if (hasError(data.job)) { <pre class="fp-alert danger">{{ data.job.error_summary | json }}</pre> }
          <nz-table #targetTable [nzData]="data.targets" nzSize="small" [nzPageSize]="25">
            <thead><tr><th>Run</th><th>Version</th><th>Status</th><th>Rows</th><th>Error</th><th></th></tr></thead>
            <tbody>@for (target of targetTable.data; track target.run_id + '-' + target.feature_version_id) {<tr>
              <td class="fp-code">{{ target.run_id }}</td><td>{{ target.feature_version_id }}</td>
              <td><app-feature-status-badge [status]="target.status"></app-feature-status-badge></td>
              <td>{{ target.deleted_rows }} / {{ target.estimated_rows }}</td><td>{{ target.error_message }}</td>
              <td><button nz-button nzSize="small" (click)="openRun(target.run_id)">Run detail</button></td>
            </tr>}</tbody>
          </nz-table>
        </section>
      }
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .purge-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(310px,.65fr);gap:16px;align-items:start}
    .impact-card{position:sticky;top:12px;border-top:4px solid #b44137}.impact-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
    .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}.all-versions{align-self:end;padding:8px 0;font-weight:700}
    .confirmation{margin:14px 0}.submit-purge{width:100%;margin-top:14px}
    .detail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0}
    .detail-grid div{padding:12px;border:1px solid #d8d3c9;background:#faf8f3}.detail-grid span{display:block;color:#777;font-size:11px;text-transform:uppercase}.detail-grid strong{font-size:18px}
    .selected-row{background:#fff1ea}
    @media(max-width:980px){.purge-layout{grid-template-columns:1fr}.impact-card{position:static}}
    @media(max-width:650px){.form-grid,.impact-grid,.detail-grid{grid-template-columns:1fr}}
  `],
})
export class PurgesPageComponent implements OnInit, OnDestroy {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroy$ = new Subject<void>();
  private refreshTimer?: ReturnType<typeof setInterval>;

  scopeType: FeaturePurgeScope = 'run';
  runId = '';
  featureVersionId: number | null = null;
  featureCode = '';
  allVersions = false;
  confirmationText = '';
  preview: FeaturePurgePreviewResponse | null = null;
  jobs: FeatureDataPurgeJob[] = [];
  detail: FeaturePurgeDetail | null = null;
  statusFilter: string | null = null;
  scopeFilter: FeaturePurgeScope | null = null;
  readonly statuses = ['previewed', 'queued', 'running', 'succeeded', 'failed', 'cancelled'];
  previewing = false;
  submitting = false;
  loadingJobs = false;
  acting = false;
  error: ReturnType<typeof featurePlatformError> | null = null;

  ngOnInit(): void {
    const featureCode = this.route.snapshot.queryParamMap.get('feature_code');
    const runId = this.route.snapshot.queryParamMap.get('run_id');
    const versionID = Number(this.route.snapshot.queryParamMap.get('feature_version_id'));
    if (runId) {
      this.scopeType = 'run';
      this.runId = runId;
    } else if (versionID > 0) {
      this.scopeType = 'feature_version';
      this.featureVersionId = versionID;
    } else if (featureCode) {
      this.scopeType = 'feature_all_versions';
      this.featureCode = featureCode;
    }
    this.loadJobs();
    this.refreshTimer = setInterval(() => {
      this.loadJobs(false);
      if (this.detail && ['queued', 'running'].includes(this.detail.job.status)) {
        this.loadDetail(this.detail.job.purge_id, false);
      }
    }, 5_000);
  }

  scopeChanged(): void { this.clearPreview(); }

  clearPreview(): void {
    this.preview = null;
    this.confirmationText = '';
  }

  previewImpact(): void {
    const request = this.request();
    if (!request) return;
    this.previewing = true;
    this.error = null;
    this.api.previewPurge(request).pipe(takeUntil(this.destroy$)).subscribe({
      next: (preview) => { this.preview = preview; this.previewing = false; },
      error: (error) => { this.error = featurePlatformError(error); this.previewing = false; },
    });
  }

  submit(): void {
    if (!this.preview || !this.canSubmit()) return;
    this.submitting = true;
    this.error = null;
    this.api.submitPurge({
      purge_id: this.preview.job.purge_id,
      confirmation_token: this.preview.confirmation_token,
      confirmation_text: this.confirmationText,
    }).pipe(takeUntil(this.destroy$)).subscribe({
      next: (detail) => {
        this.detail = detail;
        this.submitting = false;
        this.clearPreview();
        this.loadJobs(false);
      },
      error: (error) => { this.error = featurePlatformError(error); this.submitting = false; },
    });
  }

  canSubmit(): boolean {
    return Boolean(
      this.preview &&
      this.confirmationText === this.preview.job.confirmation_text &&
      new Date(this.preview.job.confirmation_expires_at).getTime() > Date.now(),
    );
  }

  loadJobs(showSpinner = true): void {
    if (showSpinner) this.loadingJobs = true;
    this.api.listPurges({
      status: this.statusFilter || undefined,
      scope_type: this.scopeFilter || undefined,
      limit: 200,
    }).pipe(takeUntil(this.destroy$)).subscribe({
      next: (response) => { this.jobs = response.items; this.loadingJobs = false; },
      error: (error) => { this.error = featurePlatformError(error); this.loadingJobs = false; },
    });
  }

  selectJob(job: FeatureDataPurgeJob): void { this.loadDetail(job.purge_id); }

  loadDetail(purgeId: string, showSpinner = true): void {
    if (showSpinner) this.acting = true;
    this.api.getPurge(purgeId).pipe(takeUntil(this.destroy$)).subscribe({
      next: (detail) => { this.detail = detail; this.acting = false; },
      error: (error) => { this.error = featurePlatformError(error); this.acting = false; },
    });
  }

  cancel(): void {
    if (!this.detail || !this.canCancel(this.detail.job)) return;
    this.acting = true;
    this.api.cancelPurge(this.detail.job.purge_id).pipe(takeUntil(this.destroy$)).subscribe({
      next: () => { this.loadDetail(this.detail!.job.purge_id, false); this.loadJobs(false); },
      error: (error) => { this.error = featurePlatformError(error); this.acting = false; },
    });
  }

  canCancel(job: FeatureDataPurgeJob): boolean { return ['previewed', 'queued'].includes(job.status); }

  progress(detail: FeaturePurgeDetail): number {
    if (!detail.targets.length) return detail.job.status === 'succeeded' ? 100 : 0;
    const finished = detail.targets.filter((target) => ['succeeded', 'failed', 'cancelled'].includes(target.status)).length;
    return Math.round(finished / detail.targets.length * 1000) / 10;
  }

  hasError(job: FeatureDataPurgeJob): boolean { return Object.keys(job.error_summary || {}).length > 0; }
  openRun(runId: string): void { this.router.navigate(['/workbench/features/runs', runId]); }

  private request(): FeaturePurgePreviewRequest | null {
    const request: FeaturePurgePreviewRequest = { scope_type: this.scopeType };
    if (this.scopeType === 'run') {
      if (!this.runId.trim()) return this.fail('RUN_REQUIRED', 'Run ID is required.');
      request.run_id = this.runId.trim();
    } else if (this.scopeType === 'feature_version') {
      if (!this.featureVersionId || this.featureVersionId <= 0) return this.fail('VERSION_REQUIRED', 'A positive Feature Version ID is required.');
      request.feature_version_id = this.featureVersionId;
    } else {
      if (!this.featureCode.trim()) return this.fail('FEATURE_REQUIRED', 'Feature code is required.');
      if (!this.allVersions) return this.fail('ALL_VERSIONS_REQUIRED', 'Explicitly include all versions before previewing.');
      request.feature_code = this.featureCode.trim();
      request.all_versions = true;
    }
    return request;
  }

  private fail(code: string, message: string): null {
    this.error = { code, message };
    return null;
  }

  ngOnDestroy(): void {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.destroy$.next();
    this.destroy$.complete();
  }
}
