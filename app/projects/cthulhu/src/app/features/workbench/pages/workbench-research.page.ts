import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { StrategyConfigComponent } from '../ui/strategy-config.component';
import { BacktestChartComponent } from '../ui/backtest-chart.component';
import { BacktestKLineChartComponent } from '../ui/backtest-kline-chart.component';
import { BacktestStatsComponent } from '../ui/backtest-stats.component';
import { ReturnCurveChartComponent } from '../ui/return-curve-chart.component';
import { WorkbenchStore } from '../state/workbench.store';

@Component({
  selector: 'app-workbench-research',
  standalone: true,
  imports: [
    CommonModule,
    NzSpinModule,
    NzGridModule,
    StrategyConfigComponent,
    BacktestChartComponent,
    BacktestKLineChartComponent,
    BacktestStatsComponent,
    ReturnCurveChartComponent,
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
            </div>
          </div>
        }
      </nz-spin>
    </div>
  `,
})
export class WorkbenchResearchPageComponent {
  store = inject(WorkbenchStore);
}
