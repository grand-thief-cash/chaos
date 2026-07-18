import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import { FeatureComputeResponse, FeatureRegistryRow } from '../models/feature-platform.models';
import { computeValidationError, featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-manual-compute-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NzButtonModule, NzInputModule, NzSelectModule, NzSwitchModule, SecuritySearchInputComponent, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page compute-layout">
      <section class="fp-panel compute-form">
        <div class="fp-panel-title"><div><div class="fp-eyebrow">TaskEngine submission</div><h2>Manual Compute</h2></div><app-feature-status-badge [status]="selectedReadiness()"></app-feature-status-badge></div>
        <div class="fp-alert">Manual compute is restricted to registered Published versions. The request freezes security IDs, as-of time, data cutoff and source profile.</div>
        <div class="form-grid">
          <div class="fp-field wide"><label>Feature</label><nz-select [(ngModel)]="featureCode" (ngModelChange)="selectFeature()" nzShowSearch nzPlaceHolder="Choose a registered Feature">
            @for (row of publishedRows(); track row.definition.feature_code) { <nz-option [nzValue]="row.definition.feature_code" [nzLabel]="row.definition.feature_code + ' · ' + row.definition.display_name"></nz-option> }
          </nz-select></div>
          <div class="fp-field"><label>Published version</label><nz-select [(ngModel)]="version">
            @for (published of selectedRow()?.published_versions || []; track published.id) { <nz-option [nzValue]="published.version_number" [nzLabel]="'v' + published.version_number + ' · ID ' + published.id"></nz-option> }
          </nz-select></div>
          <div class="fp-field"><label>Source profile</label><input nz-input [(ngModel)]="sourceProfile" /></div>
          <div class="fp-field"><label>Market</label><input nz-input [(ngModel)]="market" /></div>
          <div class="fp-field"><label>As-of time</label><input nz-input type="datetime-local" [(ngModel)]="asOf" /></div>
          <div class="fp-field"><label>Data cutoff time</label><input nz-input type="datetime-local" [(ngModel)]="cutoff" /></div>
          <div class="fp-field wide"><label>Security search</label><app-security-search-input placeholder="Add by company name or symbol" [market]="market" (securitySelected)="addSecurity($event)"></app-security-search-input></div>
          <div class="fp-field wide"><label>Security IDs</label><textarea nz-input rows="4" [(ngModel)]="securityIdsText" placeholder="One or more positive IDs separated by commas or whitespace"></textarea><small class="fp-muted">{{ securityIds().length }} unique subjects frozen into the Run.</small></div>
          <div class="fp-field wide"><label>Idempotency key</label><input nz-input [(ngModel)]="idempotencyKey" placeholder="optional stable caller key" /></div>
          <div class="fp-field wide"><label>Retry of Run ID</label><input nz-input [(ngModel)]="retryOfRunId" placeholder="optional UUID" /></div>
          <div class="fp-field"><label>Force new run</label><nz-switch [(ngModel)]="force"></nz-switch></div>
        </div>
        @if (validationMessage) { <div class="fp-alert danger"><strong>Request blocked.</strong> {{ validationMessage }}</div> }
        @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
        <div class="fp-actions" style="margin-top:14px"><button nz-button nzType="primary" (click)="submit()" [nzLoading]="submitting">Submit asynchronous Run</button><a nz-button [routerLink]="['../runs']">Open Runs</a></div>
      </section>

      <aside class="fp-panel evidence-panel">
        <div class="fp-eyebrow">Frozen request preview</div>
        <h3>{{ featureCode || 'No feature selected' }} @if (version) { · v{{ version }} }</h3>
        <div class="fp-meta-grid">
          <div class="fp-meta"><label>Readiness</label><app-feature-status-badge [status]="selectedReadiness()"></app-feature-status-badge></div>
          <div class="fp-meta"><label>Subjects</label>{{ securityIds().length }}</div>
          <div class="fp-meta"><label>Source</label><span class="fp-code">{{ sourceProfile }}</span></div>
          <div class="fp-meta"><label>Force / Retry</label>{{ force ? 'force' : 'idempotent' }} · {{ retryOfRunId ? 'retry' : 'original' }}</div>
        </div>
        @if (selectedRow()?.availability?.reasons?.length) { <div class="fp-alert" style="margin-top:12px">{{ selectedRow()?.availability?.reasons?.join(' · ') }}</div> }
        @if (result; as run) {
          <div class="result-card">
            <div class="fp-eyebrow">Submission accepted</div><app-feature-status-badge [status]="run.status"></app-feature-status-badge>
            <h3 class="fp-code">{{ run.run_id }}</h3>
            <p>{{ run.reused ? 'An existing active/succeeded Run was reused.' : 'A new asynchronous Run was created.' }}</p>
            <a nz-button nzType="primary" [routerLink]="['../runs', run.run_id]">Open Run Detail</a>
          </div>
        }
      </aside>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .compute-layout{grid-template-columns:minmax(0,1.45fr) minmax(280px,.65fr);align-items:start}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}.wide{grid-column:1/-1}.evidence-panel{position:sticky;top:12px}.result-card{margin-top:18px;padding:16px;border:1px solid #a7ddc5;background:#effaf4}.result-card h3{font-size:13px}@media(max-width:900px){.compute-layout{grid-template-columns:1fr}.evidence-panel{position:static}}@media(max-width:520px){.form-grid{grid-template-columns:minmax(0,1fr)}.wide{grid-column:auto}}
  `],
})
export class ManualComputePageComponent implements OnInit {
  readonly store = inject(FeaturePlatformStore);
  private readonly api = inject(FeaturePlatformApiService);
  private readonly route = inject(ActivatedRoute);
  featureCode = '';
  version: number | null = null;
  sourceProfile = this.store.sourceProfile();
  market = 'zh_a';
  asOf = this.localDateTime(new Date());
  cutoff = this.localDateTime(new Date());
  securityIdsText = '';
  idempotencyKey = '';
  retryOfRunId = '';
  force = false;
  submitting = false;
  validationMessage: string | null = null;
  error: ReturnType<typeof featurePlatformError> | null = null;
  result: FeatureComputeResponse | null = null;

  ngOnInit(): void {
    this.featureCode = this.route.snapshot.queryParamMap.get('feature_code') || '';
    this.version = Number(this.route.snapshot.queryParamMap.get('version')) || null;
    this.retryOfRunId = this.route.snapshot.queryParamMap.get('retry_of_run_id') || '';
    this.store.loadRegistry({ status: 'active' });
  }

  publishedRows(): FeatureRegistryRow[] { return this.store.registryRows().filter((row) => !!row.latest_published_version); }
  selectedRow(): FeatureRegistryRow | undefined { return this.store.registryRows().find((row) => row.definition.feature_code === this.featureCode); }
  selectedReadiness(): string { return this.selectedRow()?.availability.execution_readiness || 'unknown'; }
  selectFeature(): void { this.version = this.selectedRow()?.latest_published_version?.version_number || null; this.result = null; }

  securityIds(): number[] {
    if (!this.securityIdsText.trim()) return [];
    const ids = this.securityIdsText.split(/[\s,]+/).filter(Boolean).map(Number);
    return ids.every((id) => Number.isInteger(id) && id > 0) ? [...new Set(ids)] : [];
  }

  addSecurity(item: SecuritySearchItem | null): void {
    if (!item) return;
    const ids = this.securityIds();
    if (!ids.includes(item.security_id)) ids.push(item.security_id);
    this.securityIdsText = ids.join(', ');
  }

  submit(): void {
    const rawTokens = this.securityIdsText.split(/[\s,]+/).filter(Boolean);
    const parsed = rawTokens.map(Number);
    if (parsed.some((id) => !Number.isInteger(id) || id <= 0)) {
      this.validationMessage = 'Security IDs must be positive integers.';
      return;
    }
    const ids = parsed;
    this.validationMessage = computeValidationError(this.featureCode, this.version, ids, this.asOf, this.cutoff);
    if (!this.validationMessage && !this.sourceProfile.trim()) this.validationMessage = 'Source profile is required.';
    if (!this.validationMessage && !this.market.trim()) this.validationMessage = 'Market is required.';
    if (!this.validationMessage && this.retryOfRunId.trim() && !this.isUuid(this.retryOfRunId.trim())) this.validationMessage = 'Retry of Run ID must be a UUID.';
    if (!this.validationMessage && this.selectedReadiness() !== 'ready') this.validationMessage = `Execution readiness is ${this.selectedReadiness()}; compute fails closed.`;
    if (this.validationMessage) return;
    this.submitting = true;
    this.error = null;
    this.result = null;
    this.store.setSourceProfile(this.sourceProfile);
    this.api.compute({
      features: [{ code: this.featureCode, version: this.version! }],
      security_ids: ids,
      as_of_time: new Date(this.asOf).toISOString(),
      data_cutoff_time: new Date(this.cutoff).toISOString(),
      market: this.market.trim(),
      source_profile: this.sourceProfile.trim(),
      trigger_type: 'manual',
      idempotency_key: this.idempotencyKey.trim() || undefined,
      parameters: {},
      force: this.force,
      retry_of_run_id: this.retryOfRunId.trim() || undefined,
    }).subscribe({
      next: (result) => { this.result = result; this.submitting = false; },
      error: (error) => { this.error = featurePlatformError(error); this.submitting = false; },
    });
  }

  private localDateTime(date: Date): string { const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000); return shifted.toISOString().slice(0, 16); }
  private isUuid(value: string): boolean { return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value); }
}
