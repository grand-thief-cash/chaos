import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { CompanyContextBarComponent } from '../ui/company-context-bar.component';
import { TrendChartComponent } from '../ui/trend-chart.component';
import { BiApiService } from '../services/bi-api.service';
import { BIQualityResponse } from '../models/bi.models';

@Component({
  selector: 'app-financial-quality-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzTagModule, NzSpinModule, NzEmptyModule, NzAlertModule, CompanyContextBarComponent, TrendChartComponent],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      @if (loading) {
        <nz-spin nzTip="Loading quality panels..."></nz-spin>
      } @else if (data) {
        <app-company-context-bar [company]="data.company" [asOfDate]="data.as_of_date" [latestPeriod]="data.latest_period"></app-company-context-bar>

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
                      <app-bi-trend-chart [section]="section" [height]="280"></app-bi-trend-chart>
                    </div>
                  }
                </div>
              }

              @if (panel.table_rows.length > 0) {
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
                      @for (row of panel.table_rows; track row.period) {
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
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIQualityResponse | null = null;

  ngOnInit(): void {
    const symbol = this.route.snapshot.paramMap.get('symbol') ?? '';
    const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
    this.loading = true;
    this.api.getCompanyQuality(symbol, asOfDate).subscribe({
      next: (resp) => {
        this.data = resp;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  display(value: number | null | undefined, unit: string): string {
    if (value === null || value === undefined) return '-';
    return `${value.toFixed(2)} ${unit === 'ratio' ? '' : unit}`.trim();
  }
}



