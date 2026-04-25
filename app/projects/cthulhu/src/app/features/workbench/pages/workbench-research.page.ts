import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { StrategyConfigComponent } from '../ui/strategy-config.component';
import { BacktestChartComponent } from '../ui/backtest-chart.component';
import { BacktestKLineChartComponent } from '../ui/backtest-kline-chart.component';
import { BacktestStatsComponent } from '../ui/backtest-stats.component';
import { ReturnCurveChartComponent } from '../ui/return-curve-chart.component';
import { ReturnDistributionChartComponent } from '../ui/return-distribution-chart.component';
import { BacktestBarDetailsComponent } from '../ui/backtest-diagnostics.component';
import { WorkbenchStore } from '../state/workbench.store';

@Component({
  selector: 'app-workbench-research',
  standalone: true,
  imports: [
    CommonModule,
    NzSpinModule,
    NzGridModule,
    NzButtonModule,
    StrategyConfigComponent,
    BacktestChartComponent,
    BacktestKLineChartComponent,
    BacktestStatsComponent,
    ReturnCurveChartComponent,
    ReturnDistributionChartComponent,
    BacktestBarDetailsComponent,
  ],
  template: `
    <div style="padding: 24px;">
      <nz-spin [nzSpinning]="store.loading()">
        <app-strategy-config></app-strategy-config>

        @if (store.result(); as result) {
          <div style="margin-top: 24px;">
            <div nz-row [nzGutter]="[24, 24]">
              <div nz-col [nzSpan]="24">
                <app-backtest-stats [summary]="result.summary"></app-backtest-stats>
              </div>
              <div nz-col [nzSpan]="24">
                <app-backtest-kline-chart [artifacts]="result.artifacts"></app-backtest-kline-chart>
              </div>
              <div nz-col [nzSpan]="24">
                <app-backtest-chart [artifacts]="result.artifacts"></app-backtest-chart>
              </div>
              <div nz-col [nzSpan]="24">
                <app-return-curve-chart [artifacts]="result.artifacts"></app-return-curve-chart>
              </div>
              <div nz-col [nzSpan]="24" style="text-align: right;">
                <button nz-button nzSize="small" [nzType]="showDistribution ? 'primary' : 'default'"
                  (click)="showDistribution = !showDistribution">
                  {{ showDistribution ? 'Hide' : 'Show' }} Return Distribution
                </button>
              </div>
              @if (showDistribution) {
                <div nz-col [nzSpan]="24">
                  <app-return-distribution-chart [artifacts]="result.artifacts"></app-return-distribution-chart>
                </div>
              }
              @if (result.artifacts.bar_details?.length) {
                <div nz-col [nzSpan]="24">
                  <app-backtest-bar-details [barDetails]="result.artifacts.bar_details"></app-backtest-bar-details>
                </div>
              }
            </div>
          </div>
        }
      </nz-spin>
    </div>
  `,
})
export class WorkbenchResearchPageComponent {
  store = inject(WorkbenchStore);
  showDistribution = false;
}
