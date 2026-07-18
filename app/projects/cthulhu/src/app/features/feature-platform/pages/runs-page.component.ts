import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzTableModule } from 'ng-zorro-antd/table';
import { FeatureRun } from '../models/feature-platform.models';
import { featurePlatformError, isDirtyRevision } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-runs-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NzButtonModule, NzEmptyModule, NzIconModule, NzInputModule, NzSelectModule, NzSpinModule, NzSwitchModule, NzTableModule, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar">
        <div class="fp-toolbar-fields">
          <div class="fp-field"><label>Status</label><nz-select [(ngModel)]="status" nzAllowClear nzPlaceHolder="All" style="width:145px">
            @for (option of statuses; track option) { <nz-option [nzValue]="option" [nzLabel]="option"></nz-option> }
          </nz-select></div>
          <div class="fp-field"><label>Producer</label><input nz-input [(ngModel)]="producer" placeholder="artemis" style="width:130px" /></div>
          <div class="fp-field"><label>Feature version ID</label><input nz-input type="number" [(ngModel)]="featureVersionId" style="width:155px" /></div>
          <div class="fp-field"><label>Backfill ID</label><input nz-input [(ngModel)]="backfillId" style="width:210px" /></div>
          <div class="fp-field"><label>Auto refresh</label><nz-switch [(ngModel)]="autoRefresh"></nz-switch></div>
        </div>
        <button nz-button nzType="primary" (click)="applyFilters()" [nzLoading]="loading"><span nz-icon nzType="reload"></span> Refresh runs</button>
      </section>
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      <section class="fp-panel">
        <div class="fp-panel-title"><div><div class="fp-eyebrow">Execution ledger</div><h2>Runs</h2></div><span class="fp-muted">{{ total }} persisted runs · last refresh {{ refreshedAt | date:'HH:mm:ss' }}</span></div>
        <nz-spin [nzSpinning]="loading">
          @if (!loading && !runs.length) { <nz-empty nzNotFoundContent="No runs match the active filters."></nz-empty> }
          <nz-table #runsTable [nzData]="runs" nzSize="small" [nzPageSize]="25" [nzShowSizeChanger]="true">
            <thead><tr><th>Run</th><th>Root versions</th><th>Time contract</th><th>Source</th><th>Status</th><th>Producer</th><th>Duration</th><th>Error / revision</th></tr></thead>
            <tbody>@for (run of runsTable.data; track run.run_id) {
              <tr>
                <td><a class="fp-link fp-code" [routerLink]="[run.run_id]">{{ run.run_id }}</a><div class="fp-muted">{{ run.trigger_type }} · {{ run.created_at | date:'short' }}</div></td>
                <td><div class="fp-chip-list">@for (id of rootVersions(run); track id) { <span class="fp-chip">ID {{ id }}</span> } @empty { <span class="fp-muted">not recorded</span> }</div></td>
                <td><div><strong>as-of</strong> {{ run.as_of_time | date:'yyyy-MM-dd HH:mm' }}</div><div class="fp-muted"><strong>cutoff</strong> {{ run.data_cutoff_time | date:'yyyy-MM-dd HH:mm' }}</div></td>
                <td><span class="fp-code">{{ run.source_profile }}</span><div class="fp-muted">{{ run.market }}</div></td>
                <td><app-feature-status-badge [status]="run.status"></app-feature-status-badge></td>
                <td>{{ run.producer_service }}<div class="fp-muted fp-code">{{ run.worker_id || 'unassigned' }}</div></td>
                <td>{{ duration(run) }}</td>
                <td>
                  @if (run.error_code) { <div class="fp-alert danger" style="padding:6px 8px"><span class="fp-code">{{ run.error_code }}</span><br>{{ run.error_message }}</div> }
                  @else { <span class="fp-code">{{ run.code_revision }}</span> @if (dirty(run)) { <app-feature-status-badge status="dirty"></app-feature-status-badge> } }
                </td>
              </tr>
            }</tbody>
          </nz-table>
        </nz-spin>
      </section>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
})
export class RunsPageComponent implements OnInit, OnDestroy {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  runs: FeatureRun[] = [];
  total = 0;
  loading = false;
  error: ReturnType<typeof featurePlatformError> | null = null;
  refreshedAt: Date | null = null;
  status: string | null = null;
  producer = '';
  featureVersionId: number | null = null;
  backfillId = '';
  autoRefresh = true;
  readonly statuses = ['queued', 'planning', 'running', 'validating', 'succeeded', 'failed', 'aborted', 'cancelled'];
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    const query = this.route.snapshot.queryParamMap;
    this.status = query.get('status');
    this.producer = query.get('producer_service') || '';
    this.featureVersionId = Number(query.get('feature_version_id')) || null;
    this.backfillId = query.get('backfill_id') || '';
    this.load();
    this.timer = setInterval(() => { if (this.autoRefresh && this.runs.some((run) => this.isActive(run.status))) this.load(false); }, 10_000);
  }

  applyFilters(): void {
    this.router.navigate([], { relativeTo: this.route, replaceUrl: true, queryParams: {
      status: this.status || null,
      producer_service: this.producer.trim() || null,
      feature_version_id: this.featureVersionId || null,
      backfill_id: this.backfillId.trim() || null,
    }});
    this.load();
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading = true;
    this.error = null;
    this.api.listRuns({
      status: this.status || undefined,
      producer_service: this.producer.trim() || undefined,
      feature_version_id: this.featureVersionId || undefined,
      backfill_id: this.backfillId.trim() || undefined,
      limit: 500,
    }).subscribe({
      next: (response) => { this.runs = response.items; this.total = response.total; this.loading = false; this.refreshedAt = new Date(); },
      error: (error) => { this.error = featurePlatformError(error); this.loading = false; },
    });
  }

  rootVersions(run: FeatureRun): number[] { return run.request_payload.root_feature_version_ids || []; }
  dirty(run: FeatureRun): boolean { return isDirtyRevision(run.code_revision); }
  duration(run: FeatureRun): string {
    if (!run.started_at) return '-';
    const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
    const seconds = Math.max(0, Math.round((end - new Date(run.started_at).getTime()) / 1000));
    return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }
  isActive(status: string): boolean { return ['queued', 'planning', 'running', 'validating'].includes(status); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }
}
