import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { first } from 'rxjs';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { CompanyContextBarComponent } from '../ui/company-context-bar.component';
import { TrendChartComponent } from '../ui/trend-chart.component';
import { TrendControlsComponent } from '../ui/trend-controls.component';
import { BiApiService } from '../services/bi-api.service';
import { BIQualityPanel, BIQualityResponse, BIQualityTableRow } from '../models/bi.models';

@Component({
  selector: 'app-financial-quality-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzTagModule, NzSpinModule, NzEmptyModule, NzAlertModule, NzButtonModule, CompanyContextBarComponent, TrendChartComponent, TrendControlsComponent],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      @if (loading) {
        <nz-spin nzTip="Loading quality panels..."></nz-spin>
      } @else if (errorMessage) {
        <nz-alert nzType="error" [nzMessage]="'加载失败'" [nzDescription]="errorMessage" nzShowIcon></nz-alert>
        <button nz-button (click)="goBack()">返回</button>
      } @else if (data) {
        <app-company-context-bar [company]="data.company" [asOfDate]="data.as_of_date" [latestPeriod]="data.latest_period"></app-company-context-bar>

        <nz-card nzTitle="趋势设置" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <app-bi-trend-controls
            [periodLimit]="trendPeriodLimit"
            [viewMode]="trendViewMode"
            (periodLimitChange)="onTrendPeriodLimitChange($event)"
            (viewModeChange)="onTrendViewModeChange($event)">
          </app-bi-trend-controls>
        </nz-card>

        @for (panel of data.panels; track panel.code) {
          <nz-card [nzTitle]="panel.title" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px;">
                @for (metric of panel.metrics; track metric.code) {
                  <div style="padding: 12px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fafafa; min-height: 108px;">
                    <div style="display: flex; justify-content: space-between; gap: 8px; align-items: start;">
                      <div style="font-size: 13px; color: #595959;">{{ metric.label }}</div>
                      @if (metric.degraded) { <nz-tag nzColor="orange">Degraded</nz-tag> }
                    </div>
                    <div style="font-size: 22px; font-weight: 600; margin-top: 8px;">{{ display(metric.value, metric.unit) }}</div>
                    <div style="font-size: 12px; color: #8c8c8c; margin-top: 6px;">去年同期：{{ display(metric.same_period_last_year, metric.unit) }}</div>
                    <div style="font-size: 12px; color: #8c8c8c;">同比变动：{{ display(metric.yoy_delta, metric.unit) }}</div>
                  </div>
                }
              </div>

              @if (panel.warnings.length > 0) {
                <div style="display: flex; flex-direction: column; gap: 8px;">
                  @for (warning of panel.warnings; track warning.code) {
                    <nz-alert [nzType]="warning.severity === 'high' ? 'error' : warning.severity === 'medium' ? 'warning' : 'info'" [nzMessage]="warning.title" [nzDescription]="warning.message" nzShowIcon></nz-alert>
                  }
                </div>
              }

              @if (panel.trend_sections.length > 0) {
                <div style="display: flex; flex-direction: column; gap: 12px;">
                  @for (section of panel.trend_sections; track section.code) {
                    <div style="border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px; background: #fff;">
                      <div style="font-weight: 600; margin-bottom: 8px;">{{ section.title }}</div>
                      <app-bi-trend-chart
                        [section]="section"
                        [height]="280"
                        [periodLimit]="trendPeriodLimit"
                        [viewMode]="trendViewMode">
                      </app-bi-trend-chart>
                    </div>
                  }
                </div>
              }

              @if (filteredTableRows(panel).length > 0) {
                <div style="overflow-x: auto;">
                  <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead>
                      <tr>
                        <th style="text-align: left; padding: 6px; border-bottom: 1px solid #f0f0f0;">报告期</th>
                        @for (metric of panel.metrics; track metric.code) {
                          <th style="text-align: right; padding: 6px; border-bottom: 1px solid #f0f0f0;">{{ metric.label }}</th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (row of filteredTableRows(panel); track row.period) {
                        <tr>
                          <td style="padding: 6px; border-bottom: 1px solid #fafafa;">{{ row.period }}</td>
                          @for (metric of panel.metrics; track metric.code) {
                            <td style="padding: 6px; border-bottom: 1px solid #fafafa; text-align: right;">{{ row.values[metric.code] === null || row.values[metric.code] === undefined ? '-' : (row.values[metric.code] | number:'1.2-2') }}</td>
                          }
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              }
            </div>
          </nz-card>
        }
      } @else {
        <nz-empty nzNotFoundContent="No quality data"></nz-empty>
      }
    </div>
  `,
})
export class FinancialQualityPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIQualityResponse | null = null;
  errorMessage: string | null = null;
  trendPeriodLimit: 12 | 16 | 20 = 12;
  trendViewMode: 'quarterly' | 'annual' = 'quarterly';

  ngOnInit(): void {
    this.loadTrendSettings();
    // Get symbol from parent route (the :symbol parameter in /bi/financial/company/:symbol)
    this.route.parent?.paramMap.pipe(first()).subscribe((params) => {
      const symbol = params?.get('symbol') ?? this.route.snapshot.paramMap.get('symbol');

      if (!symbol) {
        this.router.navigate(['/bi/financial']);
        return;
      }

      const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
      this.loading = true;
      this.api.getCompanyQuality(symbol, asOfDate).subscribe({
        next: (resp) => {
          this.data = resp;
          this.loading = false;
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err?.error?.detail || err?.message || '加载数据失败，请稍后重试';
        },
      });
    });
  }

  display(value: number | null | undefined, unit: string): string {
    if (value === null || value === undefined) return '-';
    return `${value.toFixed(2)} ${unit === 'ratio' ? '' : unit}`.trim();
  }

  goBack(): void {
    this.router.navigate(['/bi/financial']);
  }

  onTrendPeriodLimitChange(limit: 12 | 16 | 20): void {
    this.trendPeriodLimit = limit;
    this.saveTrendSettings();
  }

  onTrendViewModeChange(mode: 'quarterly' | 'annual'): void {
    this.trendViewMode = mode;
    this.saveTrendSettings();
  }

  filteredTableRows(panel: BIQualityPanel): BIQualityTableRow[] {
    const filtered = panel.table_rows.filter((row) => this.trendViewMode === 'quarterly' || this.isAnnualPeriod(row.period));
    return filtered.slice(Math.max(0, filtered.length - this.trendPeriodLimit));
  }

  private isAnnualPeriod(period: string): boolean {
    return /-12-31$/.test(period);
  }

  private loadTrendSettings(): void {
    try {
      const raw = JSON.parse(localStorage.getItem('bi-trend-settings') || '{}') as {
        periodLimit?: 12 | 16 | 20;
        viewMode?: 'quarterly' | 'annual';
      };
      if (raw.periodLimit === 12 || raw.periodLimit === 16 || raw.periodLimit === 20) {
        this.trendPeriodLimit = raw.periodLimit;
      }
      if (raw.viewMode === 'quarterly' || raw.viewMode === 'annual') {
        this.trendViewMode = raw.viewMode;
      }
    } catch {
      // ignore storage failures
    }
  }

  private saveTrendSettings(): void {
    try {
      localStorage.setItem('bi-trend-settings', JSON.stringify({
        periodLimit: this.trendPeriodLimit,
        viewMode: this.trendViewMode,
      }));
    } catch {
      // ignore storage failures
    }
  }
}



