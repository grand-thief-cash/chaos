import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { first } from 'rxjs';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { CompanyContextBarComponent } from '../ui/company-context-bar.component';
import { TrendChartComponent } from '../ui/trend-chart.component';
import { TrendControlsComponent } from '../ui/trend-controls.component';
import { BiApiService } from '../services/bi-api.service';
import { BIDashboardResponse } from '../models/bi.models';

@Component({
  selector: 'app-financial-dashboard-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzButtonModule, NzGridModule, NzStatisticModule, NzTagModule, NzSpinModule, NzEmptyModule, NzAlertModule, CompanyContextBarComponent, TrendChartComponent, TrendControlsComponent],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      @if (loading) {
        <nz-spin nzTip="Loading dashboard..."></nz-spin>
      } @else if (errorMessage) {
        <nz-alert nzType="error" [nzMessage]="'加载失败'" [nzDescription]="errorMessage" nzShowIcon></nz-alert>
        <button nz-button (click)="goBack()">返回</button>
      } @else if (data) {
        <app-company-context-bar [company]="data.company" [asOfDate]="data.as_of_date" [latestPeriod]="data.latest_period"></app-company-context-bar>

        <div nz-row [nzGutter]="16">
          @for (metric of data.kpis; track metric.code) {
            <div nz-col [nzXs]="24" [nzSm]="12" [nzLg]="6">
              <nz-card nzSize="small" [nzBordered]="false" style="height: 100%; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
                <div style="display: flex; flex-direction: column; gap: 8px;">
                  <div style="display: flex; justify-content: space-between; gap: 8px; align-items: start;">
                    <div style="font-size: 13px; color: #595959;">{{ metric.label }}</div>
                    @if (metric.degraded) { <nz-tag nzColor="orange">Degraded</nz-tag> }
                  </div>
                  <div style="font-size: 24px; font-weight: 600; color: #262626;">{{ displayMetric(metric.value, metric.unit) }}</div>
                  <div style="font-size: 12px; color: #8c8c8c; display: flex; flex-direction: column; gap: 2px;">
                    <span>去年同期: {{ displayMetric(metric.same_period_last_year, metric.unit) }}</span>
                    <span>同比变动: {{ displayMetric(metric.yoy_delta, metric.unit) }}</span>
                    <span>同比增长: {{ displayGrowth(metric.yoy_growth) }}</span>
                  </div>
                </div>
              </nz-card>
            </div>
          }
        </div>

        <div nz-row [nzGutter]="16">
          <div nz-col [nzXs]="24" [nzLg]="16">
            <nz-card nzTitle="趋势概览" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
              <div style="display: flex; flex-direction: column; gap: 16px;">
                <app-bi-trend-controls
                  [periodLimit]="trendPeriodLimit"
                  [viewMode]="trendViewMode"
                  (periodLimitChange)="onTrendPeriodLimitChange($event)"
                  (viewModeChange)="onTrendViewModeChange($event)">
                </app-bi-trend-controls>
                @for (section of data.trend_sections; track section.code) {
                  <div style="border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px;">
                    <div style="font-weight: 600; margin-bottom: 8px;">{{ section.title }}</div>
                    <app-bi-trend-chart
                      [section]="section"
                      [height]="320"
                      [periodLimit]="trendPeriodLimit"
                      [viewMode]="trendViewMode">
                    </app-bi-trend-chart>
                  </div>
                }
              </div>
            </nz-card>
          </div>
          <div nz-col [nzXs]="24" [nzLg]="8">
            <nz-card nzTitle="预警" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 16px;">
              @if (data.warnings.length > 0) {
                <div style="display: flex; flex-direction: column; gap: 8px;">
                  @for (warning of data.warnings; track warning.code) {
                    <nz-alert [nzType]="alertType(warning.severity)" [nzMessage]="warning.title" [nzDescription]="warning.message" nzShowIcon></nz-alert>
                  }
                </div>
              } @else {
                <nz-empty nzNotFoundContent="当前无预警"></nz-empty>
              }
            </nz-card>

            <nz-card nzTitle="摘要卡" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
              <div style="display: flex; flex-direction: column; gap: 12px;">
                @for (summary of data.summary_cards; track summary.code) {
                  <div style="border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px;">
                    <div style="font-weight: 600; margin-bottom: 6px;">{{ summary.title }}</div>
                    <div style="display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #595959;">
                      @for (item of summary.items; track item.code) {
                        <div style="display: flex; justify-content: space-between; gap: 12px;">
                          <span>{{ item.label }}</span>
                          <span>{{ displayMetric(item.value, item.unit) }}</span>
                        </div>
                      }
                    </div>
                  </div>
                }
              </div>
            </nz-card>

            <nz-card nzTitle="延展分析" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-top: 16px;">
              <div style="display: flex; flex-direction: column; gap: 8px; font-size: 12px; color: #595959;">
                <div>你可以继续查看同行对比或结构化摘要，进一步从横向和规则层面理解当前公司财务状态。</div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <button nz-button nzSize="small" (click)="goToCompare()">去同行对比</button>
                  <button nz-button nzSize="small" (click)="goToInsight()">去结构化摘要</button>
                </div>
              </div>
            </nz-card>
          </div>
        </div>

        <nz-card nzTitle="数据来源说明" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #595959;">
            @for (note of data.source_notes; track note.section) {
              <div style="padding: 8px 12px; border-radius: 6px; background: #fafafa; border: 1px solid #f0f0f0;">
                <strong>{{ note.section }}</strong> · {{ note.statement_types.join(', ') }} · PIT={{ note.pit_rule }} · {{ note.metric_version }}
              </div>
            }
          </div>
        </nz-card>
      } @else {
        <nz-empty nzNotFoundContent="No dashboard data"></nz-empty>
      }
    </div>
  `,
})
export class FinancialDashboardPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIDashboardResponse | null = null;
  errorMessage: string | null = null;
  currentSymbol: string | null = null;
  trendPeriodLimit: 12 | 16 | 20 = 12;
  trendViewMode: 'quarterly' | 'annual' = 'quarterly';

  ngOnInit(): void {
    this.loadTrendSettings();
    // Get symbol from parent route (the :symbol parameter in /bi/financial/company/:symbol)
    this.route.parent?.paramMap.pipe(first()).subscribe((params) => {
      const symbol = params?.get('symbol') ?? this.route.snapshot.paramMap.get('symbol');
      this.currentSymbol = symbol;

      if (!symbol) {
        this.router.navigate(['/bi/financial']);
        return;
      }

      const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
      this.loading = true;
      this.api.getCompanyDashboard(symbol, asOfDate).subscribe({
        next: (resp) => {
          this.data = resp;
          this.remember(symbol);
          this.loading = false;
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err?.error?.detail || err?.message || '加载数据失败，请稍后重试';
        },
      });
    });
  }

  displayMetric(value: number | null | undefined, unit: string): string {
    if (value === null || value === undefined) return '-';
    return `${value.toFixed(2)} ${unit === 'ratio' ? '' : unit}`.trim();
  }

  displayGrowth(value: number | null | undefined): string {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(2)}%`;
  }

  alertType(severity: string): 'success' | 'info' | 'warning' | 'error' {
    if (severity === 'high') return 'error';
    if (severity === 'medium') return 'warning';
    return 'info';
  }

  goToCompare(): void {
    this.router.navigate(['/bi/financial/compare']);
  }

  goToInsight(): void {
    const symbol = this.currentSymbol ?? '';
    const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
    this.router.navigate(['/bi/financial/company', symbol, 'insight'], { queryParams: { as_of_date: asOfDate } });
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

  private remember(symbol: string): void {
    try {
      const current = JSON.parse(localStorage.getItem('bi-recent-symbols') || '[]') as string[];
      localStorage.setItem('bi-recent-symbols', JSON.stringify([symbol, ...current.filter(item => item !== symbol)].slice(0, 8)));
    } catch {
      // ignore storage failures
    }
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






