import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { BacktestArtifacts } from '../models/workbench.model';

@Component({
  selector: 'app-backtest-chart',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzEmptyModule, NgxEchartsModule],
  template: `
    <nz-card nzTitle="Equity Curve">
      @if (options) {
        <div echarts [options]="options" style="height: 400px;"></div>
      } @else {
        <nz-empty></nz-empty>
      }
    </nz-card>
  `,
})
export class BacktestChartComponent implements OnChanges {
  @Input() artifacts: BacktestArtifacts | null = null;
  options: EChartsOption | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['artifacts'] && this.artifacts) {
      this.buildChart();
    }
  }

  private buildChart(): void {
    if (!this.artifacts) return;
    const curve = this.artifacts.equity_curve || [];
    const signals = this.artifacts.signals || [];

    const timestamps = curve.map((p) => p.timestamp.split('T')[0]);
    const values = curve.map((p) => Math.round(p.value * 100) / 100);

    const buySignals = signals
      .filter((s) => s.signal === 'BUY')
      .map((s) => [s.timestamp.split('T')[0], s.close]);

    const sellSignals = signals
      .filter((s) => s.signal === 'SELL')
      .map((s) => [s.timestamp.split('T')[0], s.close]);

    this.options = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: ['Portfolio Value', 'Buy', 'Sell'] },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: timestamps, boundaryGap: false },
      yAxis: [{ type: 'value', name: 'Value' }],
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100 },
      ],
      series: [
        {
          name: 'Portfolio Value',
          type: 'line',
          data: values,
          smooth: true,
          lineStyle: { width: 2, color: '#1890ff' },
          areaStyle: { opacity: 0.1, color: '#1890ff' },
        },
        {
          name: 'Buy',
          type: 'scatter',
          data: buySignals,
          symbol: 'triangle',
          symbolSize: 12,
          itemStyle: { color: '#52c41a' },
        },
        {
          name: 'Sell',
          type: 'scatter',
          data: sellSignals,
          symbol: 'triangle',
          symbolSize: 12,
          symbolRotate: 180,
          itemStyle: { color: '#ff4d4f' },
        },
      ],
    };
  }
}
