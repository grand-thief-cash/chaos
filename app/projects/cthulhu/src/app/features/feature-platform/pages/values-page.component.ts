import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import { FeatureNumericValue } from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-values-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzButtonModule, NzEmptyModule, NzInputModule, NzSpinModule, NzStatisticModule, NzSwitchModule, NzTableModule, NgxEchartsModule, SecuritySearchInputComponent, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar value-toolbar">
        <div class="fp-toolbar-fields">
          <div class="fp-field"><label>Feature code</label><input nz-input [(ngModel)]="featureCode" placeholder="platform.security.constant_one" style="width:270px" /></div>
          <div class="fp-field"><label>Version</label><input nz-input type="number" [(ngModel)]="version" style="width:90px" /></div>
          <div class="fp-field"><label>Run ID</label><input nz-input [(ngModel)]="runId" placeholder="optional UUID" style="width:270px" /></div>
          <div class="fp-field"><label>Latest succeeded</label><nz-switch [(ngModel)]="latest" [nzDisabled]="!!runId"></nz-switch></div>
          <div class="fp-field"><label>Security IDs</label><input nz-input [(ngModel)]="securityIdsText" placeholder="1, 2, 3" style="width:180px" /></div>
          <div class="fp-field"><label>Security search</label><app-security-search-input placeholder="name or symbol" (securitySelected)="addSecurity($event)"></app-security-search-input></div>
          <div class="fp-field"><label>Observed from</label><input nz-input type="datetime-local" [(ngModel)]="observedFrom" /></div>
          <div class="fp-field"><label>Observed to</label><input nz-input type="datetime-local" [(ngModel)]="observedTo" /></div>
        </div>
        <button nz-button nzType="primary" (click)="load()" [nzLoading]="loading">Query values</button>
      </section>
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      <section class="summary-grid">
        <div class="fp-panel"><nz-statistic nzTitle="Rows returned" [nzValue]="values.length"></nz-statistic></div>
        <div class="fp-panel"><nz-statistic nzTitle="Total matched" [nzValue]="total"></nz-statistic></div>
        <div class="fp-panel"><nz-statistic nzTitle="Valid coverage" [nzValue]="validCoverage()" nzSuffix="%"></nz-statistic></div>
        <div class="fp-panel"><div class="fp-eyebrow">Preview mode</div><strong>{{ previewMode }}</strong><div class="fp-muted">Succeeded materializations remain explicit.</div></div>
      </section>
      <nz-spin [nzSpinning]="loading">
        @if (!loading && !values.length) { <nz-empty nzNotFoundContent="No numeric values match this contract."></nz-empty> }
        @if (chartOptions) { <section class="fp-panel"><div class="fp-panel-title"><h3>{{ previewMode }} preview</h3><span class="fp-muted">Numeric values only · quality remains in the table</span></div><div echarts [options]="chartOptions" style="height:340px;width:100%"></div></section> }
        @if (values.length) {
          <section class="fp-panel">
            <div class="fp-panel-title"><h3>Value evidence</h3><span class="fp-muted">{{ total }} total rows</span></div>
            <nz-table #valuesTable [nzData]="values" nzSize="small" [nzPageSize]="25" [nzShowSizeChanger]="true">
              <thead><tr><th>Run</th><th>Version</th><th>Security</th><th>Observed</th><th>Value</th><th>Status</th><th>Source max available</th><th>Quality flags</th><th>Computed</th></tr></thead>
              <tbody>@for (value of valuesTable.data; track value.run_id + '-' + value.feature_version_id + '-' + value.security_id + '-' + value.observed_at) {<tr>
                <td class="fp-code">{{ value.run_id }}</td><td>{{ value.feature_version_id }}</td><td>{{ value.security_id }}</td><td>{{ value.observed_at | date:'medium' }}</td>
                <td><strong>{{ value.value ?? '-' }}</strong></td><td><app-feature-status-badge [status]="value.value_status"></app-feature-status-badge></td>
                <td>{{ value.source_max_available_at ? (value.source_max_available_at | date:'medium') : '-' }}</td><td><pre class="fp-json">{{ value.quality_flags | json }}</pre></td><td>{{ value.computed_at | date:'medium' }}</td>
              </tr>}</tbody>
            </nz-table>
          </section>
        }
      </nz-spin>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .value-toolbar { align-items:stretch; }
    .summary-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:10px; }
    .summary-grid .fp-panel { padding:14px; }
    @media(max-width:900px){.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:520px){.summary-grid{grid-template-columns:minmax(0,1fr)}}
  `],
})
export class ValuesPageComponent implements OnInit {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  featureCode = '';
  version: number | null = null;
  runId = '';
  latest = true;
  securityIdsText = '';
  observedFrom = '';
  observedTo = '';
  values: FeatureNumericValue[] = [];
  total = 0;
  loading = false;
  error: ReturnType<typeof featurePlatformError> | null = null;
  chartOptions: EChartsOption | null = null;
  previewMode = 'Cross-section';

  ngOnInit(): void {
    const query = this.route.snapshot.queryParamMap;
    this.featureCode = query.get('feature_code') || '';
    this.version = Number(query.get('version')) || null;
    this.runId = query.get('run_id') || '';
    this.latest = query.get('latest') !== 'false';
    this.securityIdsText = query.get('security_ids') || '';
    this.observedFrom = this.toLocalInput(query.get('observed_from'));
    this.observedTo = this.toLocalInput(query.get('observed_to'));
    if (this.featureCode || this.runId) this.load();
  }

  load(): void {
    const securityIds = this.parseSecurityIds();
    if (securityIds === null) return;
    if (!this.featureCode.trim() && !this.runId.trim()) {
      this.error = { code: 'QUERY_CONTEXT_REQUIRED', message: 'Feature code or Run ID is required.' };
      return;
    }
    this.loading = true;
    this.error = null;
    const observedFrom = this.toIso(this.observedFrom);
    const observedTo = this.toIso(this.observedTo);
    this.router.navigate([], { relativeTo: this.route, replaceUrl: true, queryParams: {
      feature_code: this.featureCode.trim() || null,
      version: this.version || null,
      run_id: this.runId.trim() || null,
      latest: this.runId ? false : this.latest,
      security_ids: securityIds.length ? securityIds.join(',') : null,
      observed_from: observedFrom || null,
      observed_to: observedTo || null,
    }});
    this.api.queryValues({
      feature_code: this.featureCode.trim() || undefined,
      version: this.version || undefined,
      run_id: this.runId.trim() || undefined,
      security_ids: securityIds.length ? securityIds : undefined,
      observed_from: observedFrom || undefined,
      observed_to: observedTo || undefined,
      limit: 500,
    }, !this.runId && this.latest).subscribe({
      next: (response) => { this.values = response.items; this.total = response.total; this.buildChart(); this.loading = false; },
      error: (error) => { this.error = featurePlatformError(error); this.values = []; this.chartOptions = null; this.loading = false; },
    });
  }

  addSecurity(item: SecuritySearchItem | null): void {
    if (!item) return;
    const ids = this.parseSecurityIds(false) || [];
    if (!ids.includes(item.security_id)) ids.push(item.security_id);
    this.securityIdsText = ids.join(', ');
  }

  validCoverage(): number {
    return this.values.length ? Math.round(this.values.filter((value) => value.value_status === 'valid').length / this.values.length * 1000) / 10 : 0;
  }

  private parseSecurityIds(showError = true): number[] | null {
    if (!this.securityIdsText.trim()) return [];
    const tokens = this.securityIdsText.split(/[\s,]+/).filter(Boolean);
    const ids = tokens.map(Number);
    if (ids.some((id) => !Number.isInteger(id) || id <= 0)) {
      if (showError) this.error = { code: 'SECURITY_IDS_INVALID', message: 'Security IDs must be positive integers.' };
      return null;
    }
    return [...new Set(ids)];
  }

  private buildChart(): void {
    const numeric = this.values.filter((value) => value.value !== null);
    if (!numeric.length) { this.chartOptions = null; return; }
    const observed = [...new Set(numeric.map((value) => value.observed_at))].sort();
    if (observed.length === 1) {
      this.previewMode = 'Cross-section';
      this.chartOptions = {
        color: ['#d96c24'], tooltip: { trigger: 'axis' }, grid: { left: 75, right: 24, top: 20, bottom: 42 },
        xAxis: { type: 'category', data: numeric.map((value) => `#${value.security_id}`), axisLabel: { rotate: 35 } },
        yAxis: { type: 'value', scale: true }, series: [{ type: 'bar', data: numeric.map((value) => value.value) }],
      };
      return;
    }
    this.previewMode = 'Time series';
    const securityIds = [...new Set(numeric.map((value) => value.security_id))].slice(0, 12);
    this.chartOptions = {
      tooltip: { trigger: 'axis' }, legend: { type: 'scroll' }, grid: { left: 65, right: 24, top: 48, bottom: 55 },
      xAxis: { type: 'category', data: observed.map((time) => new Date(time).toLocaleDateString()), axisLabel: { rotate: 30 } }, yAxis: { type: 'value', scale: true },
      series: securityIds.map((securityId) => ({ name: `#${securityId}`, type: 'line', showSymbol: false, data: observed.map((time) => numeric.find((value) => value.security_id === securityId && value.observed_at === time)?.value ?? null) })),
    };
  }

  private toIso(value: string): string { return value ? new Date(value).toISOString() : ''; }
  private toLocalInput(value: string | null): string { if (!value) return ''; const date = new Date(value); const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000); return shifted.toISOString().slice(0, 16); }
}
