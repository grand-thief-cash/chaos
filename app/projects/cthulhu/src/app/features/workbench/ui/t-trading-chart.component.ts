import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import dayjs from 'dayjs';

import { Bar, TFill, TSignal } from '../models/workbench.model';

@Component({
  selector: 'app-t-trading-chart',
  standalone: true,
  imports: [CommonModule, NgxEchartsModule],
  template: `
    @if (options) {
      <div echarts [options]="options" style="width: 100%; height: 620px;"></div>
    }
  `,
})
export class TTradingChartComponent implements OnChanges {
  @Input() bars: Bar[] = [];
  @Input() signals: TSignal[] = [];
  @Input() fills: TFill[] = [];

  options: EChartsOption | null = null;

  ngOnChanges(): void {
    this.buildChart();
  }

  private buildChart(): void {
    if (!this.bars.length) {
      this.options = null;
      return;
    }
    const categories = this.bars.map((bar) => bar.date);
    const label = (value: string) => dayjs(value).format('HH:mm');
    const decisions = (side: 'BUY' | 'SELL') => this.signals
      .filter((signal) => signal.side === side)
      .map((signal) => ({
        name: `${side} decision`,
        value: [signal.decision_time, signal.decision_price, signal.confidence],
        signal,
      }));
    const fillPoints = this.fills.map((fill) => ({
      name: `${fill.side} fill`,
      value: [fill.fill_time, fill.fill_price],
      fill,
      itemStyle: { color: fill.side === 'BUY' ? '#fa541c' : '#08979c' },
    }));

    const series: any[] = [
      {
        name: 'Minute K', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: this.bars.map((bar) => [bar.open, bar.close, bar.low, bar.high]),
        itemStyle: { color: '#f5222d', color0: '#13a8a8', borderColor: '#f5222d', borderColor0: '#13a8a8' },
      },
      {
        name: '买点判断', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0,
        data: decisions('BUY'), symbol: 'pin', symbolSize: 42,
        itemStyle: { color: '#cf1322' },
        label: { show: true, formatter: '买', color: '#fff', fontWeight: 'bold', fontSize: 11 },
      },
      {
        name: '卖点判断', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0,
        data: decisions('SELL'), symbol: 'pin', symbolRotate: 180, symbolSize: 42,
        itemStyle: { color: '#237804' },
        label: { show: true, formatter: '卖', color: '#fff', fontWeight: 'bold', fontSize: 11 },
      },
      {
        name: '下一根成交', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0,
        data: fillPoints, symbol: 'diamond', symbolSize: 12,
      },
      {
        name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: this.bars.map((bar) => bar.volume), itemStyle: { color: '#91a7ff', opacity: 0.55 },
      },
    ];

    this.options = {
      animation: false,
      legend: { top: 0 },
      axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) return '';
          const time = label(items[0].axisValue);
          const lines = [`<b>${time}</b>`];
          for (const item of items) {
            if (item.seriesName === 'Minute K' && Array.isArray(item.data)) {
              lines.push(`O ${item.data[1]} / C ${item.data[2]} / L ${item.data[3]} / H ${item.data[4]}`);
            } else if (item.data?.signal) {
              const signal = item.data.signal as TSignal;
              lines.push(`${signal.side} 判断 ${signal.decision_price} · 置信度 ${(signal.confidence * 100).toFixed(1)}%`);
            } else if (item.data?.fill) {
              const fill = item.data.fill as TFill;
              lines.push(`${fill.side} 成交 ${fill.fill_price} · 费用 ${fill.total_fee}`);
            }
          }
          return lines.join('<br/>');
        },
      },
      grid: [
        { left: 64, right: 30, top: 42, height: 410 },
        { left: 64, right: 30, top: 480, height: 82 },
      ],
      xAxis: [
        { type: 'category', data: categories, boundaryGap: true, axisLabel: { formatter: label }, min: 'dataMin', max: 'dataMax' },
        { type: 'category', data: categories, gridIndex: 1, boundaryGap: true, axisLabel: { formatter: label }, min: 'dataMin', max: 'dataMax' },
      ],
      yAxis: [
        { scale: true, splitArea: { show: true } },
        { gridIndex: 1, scale: true, splitNumber: 2, axisLabel: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1], bottom: 8, start: 0, end: 100 },
      ],
      series,
    };
  }
}
