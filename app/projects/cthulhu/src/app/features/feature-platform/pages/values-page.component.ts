import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import type { EChartsOption } from 'echarts';
import { NgxEchartsModule } from 'ngx-echarts';
import { forkJoin } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzTableModule } from 'ng-zorro-antd/table';
import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import { FeatureNumericStats, FeatureNumericStatsRequest, FeatureNumericValue, ValueFilters } from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-values-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NgxEchartsModule, NzButtonModule, NzEmptyModule,
    NzInputModule, NzSpinModule, NzStatisticModule, NzSwitchModule, NzTableModule,
    SecuritySearchInputComponent, FeatureStatusBadgeComponent,
  ],
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
        <div class="fp-panel"><nz-statistic nzTitle="Rows sampled" [nzValue]="values.length"></nz-statistic></div>
        <div class="fp-panel"><nz-statistic nzTitle="Total matched" [nzValue]="stats?.count || 0"></nz-statistic></div>
        <div class="fp-panel"><nz-statistic nzTitle="Valid coverage" [nzValue]="validCoverage()" nzSuffix="%"></nz-statistic></div>
        <div class="fp-panel">
          <div class="fp-eyebrow">Observed range</div>
          <strong>{{ stats?.observed_from ? (stats?.observed_from | date:'shortDate') : 'n/a' }}</strong>
          <div class="fp-muted">to {{ stats?.observed_to ? (stats?.observed_to | date:'shortDate') : 'n/a' }}</div>
        </div>
      </section>

      <nz-spin [nzSpinning]="loading">
        @if (!loading && !stats?.count) { <nz-empty nzNotFoundContent="No numeric values match this contract."></nz-empty> }
        @if (stats?.count) {
          <section class="chart-grid">
            <div class="fp-panel"><div class="fp-panel-title"><h3>Distribution</h3><span class="fp-muted">server-side histogram</span></div><div echarts [options]="histogramOptions" class="value-chart"></div></div>
            <div class="fp-panel"><div class="fp-panel-title"><h3>Five-number summary</h3><span class="fp-muted">P25 / median / P75</span></div><div echarts [options]="boxOptions" class="value-chart"></div></div>
            <div class="fp-panel"><div class="fp-panel-title"><h3>Quality mix</h3><span class="fp-muted">{{ stats?.count }} evaluated rows</span></div><div echarts [options]="qualityOptions" class="value-chart"></div></div>
            <div class="fp-panel"><div class="fp-panel-title"><h3>Observed trend</h3><span class="fp-muted">mean with min/max envelope</span></div><div echarts [options]="trendOptions" class="value-chart"></div></div>
          </section>
        }

        @if (values.length) {
          <section class="fp-panel">
            <div class="fp-panel-title"><h3>Value evidence sample</h3><span class="fp-muted">First {{ values.length }} of {{ stats?.count || 0 }} rows; charts use all matched rows.</span></div>
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
    .chart-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px; }
    .value-chart { height:300px;width:100%; }
    @media(max-width:1100px){.chart-grid{grid-template-columns:1fr}}
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
  stats: FeatureNumericStats | null = null;
  loading = false;
  error: ReturnType<typeof featurePlatformError> | null = null;
  histogramOptions: EChartsOption = {};
  boxOptions: EChartsOption = {};
  qualityOptions: EChartsOption = {};
  trendOptions: EChartsOption = {};

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
    const filters: ValueFilters = {
      feature_code: this.featureCode.trim() || undefined,
      version: this.version || undefined,
      run_id: this.runId.trim() || undefined,
      security_ids: securityIds.length ? securityIds : undefined,
      observed_from: observedFrom || undefined,
      observed_to: observedTo || undefined,
    };
    const statsRequest: FeatureNumericStatsRequest = {
      ...filters,
      latest: !this.runId && this.latest,
      histogram_buckets: 16,
    };
    this.router.navigate([], { relativeTo: this.route, replaceUrl: true, queryParams: {
      feature_code: filters.feature_code || null,
      version: filters.version || null,
      run_id: filters.run_id || null,
      latest: this.runId ? false : this.latest,
      security_ids: securityIds.length ? securityIds.join(',') : null,
      observed_from: observedFrom || null,
      observed_to: observedTo || null,
    }});
    forkJoin({
      values: this.api.queryValues({ ...filters, limit: 100 }, !this.runId && this.latest),
      stats: this.api.numericValueStats(statsRequest),
    }).subscribe({
      next: ({ values, stats }) => {
        this.values = values.items;
        this.stats = stats;
        this.buildCharts(stats);
        this.loading = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.values = [];
        this.stats = null;
        this.loading = false;
      },
    });
  }

  addSecurity(item: SecuritySearchItem | null): void {
    if (!item) return;
    const ids = this.parseSecurityIds(false) || [];
    if (!ids.includes(item.security_id)) ids.push(item.security_id);
    this.securityIdsText = ids.join(', ');
  }

  validCoverage(): number {
    return this.stats?.count ? Math.round(this.stats.valid_count / this.stats.count * 1000) / 10 : 0;
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

  private buildCharts(stats: FeatureNumericStats): void {
    this.histogramOptions = {
      color: ['#d66a2b'], tooltip: { trigger: 'axis' },
      grid: { left: 58, right: 18, top: 18, bottom: 58 },
      xAxis: { type: 'category', data: stats.histogram.map((bucket) => `${this.short(bucket.lower)}-${this.short(bucket.upper)}`), axisLabel: { rotate: 35 } },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ type: 'bar', data: stats.histogram.map((bucket) => bucket.count), barMaxWidth: 34 }],
    };
    const five = [stats.min, stats.p25, stats.p50, stats.p75, stats.max];
    this.boxOptions = five.every((value) => value !== null) ? {
      tooltip: { trigger: 'item' }, grid: { left: 58, right: 22, top: 25, bottom: 35 },
      xAxis: { type: 'category', data: ['matched values'] }, yAxis: { type: 'value', scale: true },
      series: [{ type: 'boxplot', data: [five as number[]], itemStyle: { color: '#d9e5df', borderColor: '#426f7d' } }],
    } : {};
    this.qualityOptions = {
      tooltip: { trigger: 'item' }, legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
        data: [
          { name: 'valid', value: stats.valid_count, itemStyle: { color: '#4b8062' } },
          { name: 'missing', value: stats.missing_count, itemStyle: { color: '#c49a45' } },
          { name: 'invalid', value: stats.invalid_count, itemStyle: { color: '#b44137' } },
        ],
        label: { formatter: '{b}: {c}' },
      }],
    };
    const dates = stats.trend.map((point) => new Date(point.observed_at).toLocaleDateString());
    this.trendOptions = {
      tooltip: { trigger: 'axis' }, legend: { top: 0 },
      grid: { left: 58, right: 18, top: 42, bottom: 48 },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
      yAxis: { type: 'value', scale: true },
      series: [
        { name: 'mean', type: 'line', showSymbol: stats.trend.length < 40, data: stats.trend.map((point) => point.mean), lineStyle: { width: 3, color: '#d66a2b' } },
        { name: 'min', type: 'line', showSymbol: false, data: stats.trend.map((point) => point.min), lineStyle: { type: 'dashed', color: '#7f969b' } },
        { name: 'max', type: 'line', showSymbol: false, data: stats.trend.map((point) => point.max), lineStyle: { type: 'dashed', color: '#7f969b' } },
      ],
    };
  }

  private short(value: number): string {
    return Math.abs(value) >= 1000 ? value.toExponential(1) : Number(value.toPrecision(4)).toString();
  }

  private toIso(value: string): string { return value ? new Date(value).toISOString() : ''; }
  private toLocalInput(value: string | null): string {
    if (!value) return '';
    const date = new Date(value);
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return shifted.toISOString().slice(0, 16);
  }
}
