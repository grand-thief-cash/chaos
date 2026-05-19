import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { BiApiService } from '../services/bi-api.service';
import { BIPeerComparisonResponse } from '../models/bi.models';

@Component({
  selector: 'app-peer-comparison-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzCardModule, NzInputModule, NzButtonModule, NzTagModule, NzTableModule, NzSelectModule, NzSpinModule, NzAlertModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card nzTitle="同行对比" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: end;">
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">Symbols（逗号分隔）</label>
            <input nz-input [(ngModel)]="symbolsInput" placeholder="000001,600519,000858" style="width: 280px;" />
          </div>
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">Industry Code / Index Code</label>
            <input nz-input [(ngModel)]="industryCode" placeholder="801120.SI" style="width: 180px;" />
          </div>
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">As Of Date</label>
            <input nz-input type="date" [(ngModel)]="asOfDate" style="width: 180px;" />
          </div>
          <div style="min-width: 260px;">
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">Metrics</label>
            <nz-select nzMode="multiple" style="width: 100%;" [(ngModel)]="selectedMetrics">
              @for (metric of metricOptions; track metric) {
                <nz-option [nzValue]="metric" [nzLabel]="metric"></nz-option>
              }
            </nz-select>
          </div>
          <button nz-button nzType="primary" (click)="runCompare()">开始对比</button>
        </div>
      </nz-card>

      @if (loading) {
        <nz-spin nzTip="Loading peer comparison..."></nz-spin>
      } @else if (errorMessage) {
        <nz-alert nzType="error" [nzMessage]="'对比失败'" [nzDescription]="errorMessage" nzShowIcon></nz-alert>
      } @else if (data) {
        <nz-card [nzTitle]="'结果：' + (data.industry_code || 'custom symbols')" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
            @for (metric of data.requested_metrics; track metric) {
              <nz-tag nzColor="blue">{{ metric }}</nz-tag>
            }
          </div>
          <nz-table #tbl [nzData]="data.rows" nzSize="small" [nzFrontPagination]="false" [nzScroll]="{ x: '1200px' }">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>公司</th>
                <th>行业</th>
                @for (metric of data.requested_metrics; track metric) {
                  <th>{{ metric }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of tbl.data; track row.symbol) {
                <tr>
                  <td>{{ row.symbol }}</td>
                  <td>{{ row.company_name }}</td>
                  <td>{{ row.industry_name }}</td>
                  @for (metric of data.requested_metrics; track metric) {
                    <td>{{ formatMetric(row.metrics[metric].value, row.metrics[metric].unit) }}</td>
                  }
                </tr>
              }
            </tbody>
          </nz-table>
        </nz-card>
      }
    </div>
  `,
})
export class PeerComparisonPageComponent {
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIPeerComparisonResponse | null = null;
  errorMessage: string | null = null;

  symbolsInput = '000001,600519,000858';
  industryCode = '';
  asOfDate = new Date().toISOString().slice(0, 10);
  selectedMetrics = ['revenue_total', 'net_profit_parent', 'roe', 'debt_ratio'];
  metricOptions = ['revenue_total', 'operating_profit', 'net_profit_parent', 'operating_cashflow', 'roe', 'roa', 'debt_ratio', 'asset_turnover', 'ocf_to_profit'];

  runCompare(): void {
    this.loading = true;
    const symbols = this.symbolsInput.split(',').map(item => item.trim()).filter(Boolean);
    this.api.getPeerComparison({
      symbols,
      industry_code: this.industryCode || undefined,
      as_of_date: this.asOfDate,
      market: 'zh_a',
      metrics: this.selectedMetrics,
      limit: 10,
    }).subscribe({
      next: (resp) => {
        this.data = resp;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err?.error?.detail || err?.message || '加载失败，请检查输入后重试';
      },
    });
  }

  formatMetric(value?: number | null, unit?: string): string {
    if (value === null || value === undefined) return '-';
    return `${value.toFixed(2)} ${unit === 'ratio' ? '' : (unit || '')}`.trim();
  }
}

