import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { BacktestSummary } from '../models/workbench.model';

@Component({
  selector: 'app-backtest-stats',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzStatisticModule, NzGridModule],
  template: `
    <nz-card nzTitle="Summary">
      <div nz-row [nzGutter]="[16, 16]">
        <div nz-col [nzSpan]="6">
          <nz-statistic
            nzTitle="PnL"
            [nzValue]="pnl"
            [nzValueStyle]="pnlStyle"
          ></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic
            nzTitle="Return"
            [nzValue]="returnPct"
            nzSuffix="%"
            [nzValueStyle]="pnlStyle"
          ></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic
            nzTitle="Win Rate"
            [nzValue]="winRate"
            nzSuffix="%"
          ></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic nzTitle="Sharpe" [nzValue]="sharpe"></nz-statistic>
        </div>
      </div>
      <div nz-row [nzGutter]="[16, 16]" style="margin-top: 16px;">
        <div nz-col [nzSpan]="6">
          <nz-statistic
            nzTitle="Max Drawdown"
            [nzValue]="maxDrawdown"
            nzSuffix="%"
            [nzValueStyle]="{ color: '#ff4d4f' }"
          ></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic nzTitle="Trades" [nzValue]="tradeCount"></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic nzTitle="Win / Loss" [nzValue]="winLoss"></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic nzTitle="Bars" [nzValue]="barsProcessed"></nz-statistic>
        </div>
      </div>
    </nz-card>
  `,
})
export class BacktestStatsComponent {
  @Input() summary: BacktestSummary | null = null;

  get pnl(): number { return this.summary?.pnl ?? 0; }
  get returnPct(): number { return Math.round((this.summary?.pnl_pct ?? 0) * 10000) / 100; }
  get winRate(): number { return Math.round((this.summary?.win_rate ?? 0) * 1000) / 10; }
  get sharpe(): number { return Math.round((this.summary?.sharpe ?? 0) * 100) / 100; }
  get maxDrawdown(): number { return Math.round((this.summary?.max_drawdown ?? 0) * 100) / 100; }
  get tradeCount(): number { return this.summary?.trade_count ?? 0; }
  get winLoss(): string { return `${this.summary?.win_count ?? 0} / ${this.summary?.loss_count ?? 0}`; }
  get barsProcessed(): number { return this.summary?.bars_processed ?? 0; }

  get pnlStyle(): { color: string } {
    return { color: this.pnl >= 0 ? '#52c41a' : '#ff4d4f' };
  }
}
