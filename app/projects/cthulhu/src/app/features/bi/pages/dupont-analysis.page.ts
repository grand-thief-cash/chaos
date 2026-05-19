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
import { BiApiService } from '../services/bi-api.service';
import { BIDupontResponse } from '../models/bi.models';

@Component({
  selector: 'app-dupont-analysis-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzTagModule, NzSpinModule, NzEmptyModule, NzAlertModule, NzButtonModule, CompanyContextBarComponent, TrendChartComponent],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      @if (loading) {
        <nz-spin nzTip="Loading dupont..."></nz-spin>
      } @else if (errorMessage) {
        <nz-alert nzType="error" [nzMessage]="'加载失败'" [nzDescription]="errorMessage" nzShowIcon></nz-alert>
        <button nz-button (click)="goBack()">返回</button>
      } @else if (data) {
        <app-company-context-bar [company]="data.company" [asOfDate]="data.as_of_date" [latestPeriod]="data.latest_period"></app-company-context-bar>

        <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px;">
          <nz-card nzTitle="三层杜邦拆解" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <div style="display: flex; flex-direction: column; gap: 12px;">
              <div style="padding: 12px; border-radius: 8px; background: #f6ffed; border: 1px solid #b7eb8f;">
                <div style="font-size: 18px; font-weight: 700;">{{ data.dupont_tree.label }}</div>
                <div style="margin-top: 6px; font-size: 24px; font-weight: 600;">{{ displayMetric(data.dupont_tree.metric.value) }}</div>
                <div style="font-size: 12px; color: #595959;">去年同期：{{ displayMetric(data.dupont_tree.metric.same_period_last_year) }} · 同比变动：{{ displayMetric(data.dupont_tree.metric.yoy_delta) }}</div>
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;">
                @for (child of data.dupont_tree.children; track child.code) {
                  <div style="padding: 12px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fafafa;">
                    <div style="font-weight: 600;">{{ child.label }}</div>
                    <div style="font-size: 20px; margin-top: 8px; font-weight: 600;">{{ displayMetric(child.metric.value) }}</div>
                    <div style="font-size: 12px; color: #8c8c8c; margin-top: 6px;">去年同期：{{ displayMetric(child.metric.same_period_last_year) }}</div>
                    <div style="font-size: 12px; color: #8c8c8c;">同比变动：{{ displayMetric(child.metric.yoy_delta) }}</div>
                  </div>
                }
              </div>
            </div>
          </nz-card>

          <nz-card nzTitle="驱动解释" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <div style="display: flex; flex-direction: column; gap: 10px;">
              @for (item of data.driver_summary; track item.driver) {
                <div style="padding: 10px 12px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fff;">
                  <div style="display: flex; justify-content: space-between; gap: 12px; align-items: center;">
                    <strong>{{ labelOf(item.driver) }}</strong>
                    <nz-tag [nzColor]="item.direction === 'up' ? 'green' : item.direction === 'down' ? 'red' : 'default'">{{ item.direction }}</nz-tag>
                  </div>
                  <div style="font-size: 12px; color: #595959; margin-top: 6px;">{{ item.message }}</div>
                </div>
              }
            </div>
          </nz-card>
        </div>

        <nz-card nzTitle="多期趋势" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px;">
            @for (section of data.trend_sections; track section.code) {
              <div style="border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px; background: #fff;">
                <div style="font-weight: 600; margin-bottom: 8px;">{{ section.title }}</div>
                <app-bi-trend-chart [section]="section" [height]="280"></app-bi-trend-chart>
              </div>
            }
          </div>
        </nz-card>

        <nz-card nzTitle="历史对比表" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
              <thead>
                <tr>
                  <th style="text-align: left; padding: 6px; border-bottom: 1px solid #f0f0f0;">报告期</th>
                  <th style="text-align: right; padding: 6px; border-bottom: 1px solid #f0f0f0;">ROE</th>
                  <th style="text-align: right; padding: 6px; border-bottom: 1px solid #f0f0f0;">净利率</th>
                  <th style="text-align: right; padding: 6px; border-bottom: 1px solid #f0f0f0;">总资产周转率</th>
                  <th style="text-align: right; padding: 6px; border-bottom: 1px solid #f0f0f0;">权益乘数</th>
                </tr>
              </thead>
              <tbody>
                @for (row of data.comparison_rows; track row.period) {
                  <tr>
                    <td style="padding: 6px; border-bottom: 1px solid #fafafa;">{{ row.period }}</td>
                    <td style="padding: 6px; border-bottom: 1px solid #fafafa; text-align: right;">{{ displayMetric(row.roe) }}</td>
                    <td style="padding: 6px; border-bottom: 1px solid #fafafa; text-align: right;">{{ displayMetric(row.net_margin) }}</td>
                    <td style="padding: 6px; border-bottom: 1px solid #fafafa; text-align: right;">{{ displayMetric(row.asset_turnover) }}</td>
                    <td style="padding: 6px; border-bottom: 1px solid #fafafa; text-align: right;">{{ displayMetric(row.equity_multiplier) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </nz-card>
      } @else {
        <nz-empty nzNotFoundContent="No dupont data"></nz-empty>
      }
    </div>
  `,
})
export class DupontAnalysisPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIDupontResponse | null = null;
  errorMessage: string | null = null;

  ngOnInit(): void {
    // Get symbol from parent route (the :symbol parameter in /bi/financial/company/:symbol)
    this.route.parent?.paramMap.pipe(first()).subscribe((params) => {
      const symbol = params?.get('symbol') ?? this.route.snapshot.paramMap.get('symbol');

      if (!symbol) {
        this.router.navigate(['/bi/financial']);
        return;
      }

      const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
      this.loading = true;
      this.api.getCompanyDupont(symbol, asOfDate).subscribe({
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

  displayMetric(value: number | null | undefined): string {
    if (value === null || value === undefined) return '-';
    return value.toFixed(4);
  }

  labelOf(code: string): string {
    const map: Record<string, string> = {
      net_margin: '净利率',
      asset_turnover: '总资产周转率',
      equity_multiplier: '权益乘数',
    };
    return map[code] || code;
  }

  goBack(): void {
    this.router.navigate(['/bi/financial']);
  }
}




