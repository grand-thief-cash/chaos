import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { BacktestArtifacts, Bar } from '../models/workbench.model';

@Component({
  selector: 'app-backtest-kline-chart',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzEmptyModule, NgxEchartsModule],
  template: `
    <nz-card nzTitle="Price Chart (K-Line + Signals)">
      @if (options) {
        <div echarts [options]="options" style="height: 500px;"></div>
      } @else {
        <nz-empty></nz-empty>
      }
    </nz-card>
  `,
})
export class BacktestKLineChartComponent implements OnChanges {
  @Input() artifacts: BacktestArtifacts | null = null;
  options: EChartsOption | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['artifacts'] && this.artifacts) {
      this.buildChart();
    }
  }

  private buildChart(): void {
    if (!this.artifacts) return;
    const bars: Bar[] = this.artifacts.bars || [];
    const signals = this.artifacts.signals || [];
    if (bars.length === 0) return;

    const dates = bars.map((b: Bar) => b.date);
    const ohlc = bars.map((b: Bar) => [b.open, b.close, b.low, b.high]);
    const volumes = bars.map((b: Bar) => b.volume);

    // Map signals to [date, price] pairs for scatter series
    const buySignals = signals
      .filter((s) => s.signal === 'BUY')
      .map((s) => {
        const date = s.timestamp.split('T')[0];
        return { value: [date, s.close], signal: s.signal };
      });

    const sellSignals = signals
      .filter((s) => s.signal === 'SELL')
      .map((s) => {
        const date = s.timestamp.split('T')[0];
        return { value: [date, s.close], signal: s.signal };
      });

    this.options = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: { data: ['K-Line', 'Buy', 'Sell', 'Volume'], top: 0 },
      grid: [
        { left: '8%', right: '3%', top: 40, height: 320, containLabel: true },
        { left: '8%', right: '3%', top: 390, height: 80, containLabel: true },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, show: false, boundaryGap: true },
        { type: 'category', data: dates, gridIndex: 1, show: true, boundaryGap: true },
      ],
      yAxis: [
        { type: 'value', gridIndex: 0, scale: true, name: 'Price' },
        { type: 'value', gridIndex: 1, scale: true, splitNumber: 2 },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1], bottom: 5 },
      ],
      series: [
        {
          name: 'K-Line',
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ohlc,
          itemStyle: {
            color: '#ef5350',
            color0: '#26a69a',
            borderColor: '#ef5350',
            borderColor0: '#26a69a',
          },
        },
        {
          name: 'Buy',
          type: 'scatter',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: buySignals,
          symbol: 'triangle',
          symbolSize: 14,
          symbolOffset: [0, 10],
          itemStyle: { color: '#52c41a' },
          label: {
            show: true,
            position: 'bottom',
            formatter: 'B',
            fontSize: 10,
            fontWeight: 'bold',
            color: '#52c41a',
          },
        },
        {
          name: 'Sell',
          type: 'scatter',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: sellSignals,
          symbol: 'triangle',
          symbolSize: 14,
          symbolRotate: 180,
          symbolOffset: [0, -10],
          itemStyle: { color: '#ff4d4f' },
          label: {
            show: true,
            position: 'top',
            formatter: 'S',
            fontSize: 10,
            fontWeight: 'bold',
            color: '#ff4d4f',
          },
        },
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: { color: '#7986cb', opacity: 0.5 },
        },
      ],
    };
  }
}

