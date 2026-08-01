import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import dayjs from 'dayjs';

import { Bar, TFill, TSignal, TStrategyName } from '../models/workbench.model';

const STRATEGY_VISUALS: Record<TStrategyName, {
  label: string;
  buy: string;
  sell: string;
}> = {
  causal_mean_reversion_v1: { label: '均值反转', buy: '#cf1322', sell: '#820014' },
  macd_volume_momentum_v1: { label: 'MACD 量价', buy: '#1677ff', sell: '#003a8c' },
  vwap_bollinger_reversion_v1: { label: 'VWAP/Bollinger', buy: '#722ed1', sell: '#391085' },
  opening_range_breakout_v1: { label: '开盘区间', buy: '#fa8c16', sell: '#ad4e00' },
  time_of_day_volume_momentum_v1: { label: '同分钟量比', buy: '#13c2c2', sell: '#006d75' },
  market_residual_reversal_v1: { label: '市场残差', buy: '#eb2f96', sell: '#9e1068' },
  multi_timeframe_pullback_v1: { label: '多周期回踩', buy: '#52c41a', sell: '#237804' },
};

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
    const fillPoints = this.fills.map((fill) => ({
      name: `${fill.side} fill`,
      value: [fill.fill_time, fill.fill_price],
      fill,
      itemStyle: { color: fill.side === 'BUY' ? '#fa541c' : '#08979c' },
    }));

    const activeStrategies = [...new Set(this.signals.map((signal) => signal.strategy))];
    const decisionSeries = activeStrategies.flatMap((strategy) => {
      const visual = STRATEGY_VISUALS[strategy];
      return (['BUY', 'SELL'] as const).map((side) => ({
        name: `${visual.label} · ${side === 'BUY' ? '买' : '卖'}`,
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: this.signals
          .filter((signal) => signal.strategy === strategy && signal.side === side)
          .map((signal) => ({
            name: `${visual.label} ${side}`,
            value: [signal.decision_time, signal.decision_price, signal.confidence],
            signal,
          })),
        symbol: 'pin',
        symbolRotate: side === 'SELL' ? 180 : 0,
        symbolSize: 42,
        itemStyle: { color: side === 'BUY' ? visual.buy : visual.sell },
        label: {
          show: true,
          formatter: side === 'BUY' ? '买' : '卖',
          color: '#fff',
          fontWeight: 'bold',
          fontSize: 11,
        },
      }));
    });

    const series: any[] = [
      {
        name: 'Minute K', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: this.bars.map((bar) => [bar.open, bar.close, bar.low, bar.high]),
        itemStyle: { color: '#f5222d', color0: '#13a8a8', borderColor: '#f5222d', borderColor0: '#13a8a8' },
      },
      ...decisionSeries,
      ...(fillPoints.length ? [{
        name: '下一根成交', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0,
        data: fillPoints, symbol: 'diamond', symbolSize: 12,
      }] : []),
      {
        name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: this.bars.map((bar) => bar.volume), itemStyle: { color: '#91a7ff', opacity: 0.55 },
      },
    ];

    this.options = {
      animation: false,
      legend: { type: 'scroll', top: 0, left: 60, right: 30 },
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
              const strategy = STRATEGY_VISUALS[signal.strategy].label;
              lines.push(`${strategy} · ${signal.side} 判断 ${signal.decision_price} · 置信度 ${(signal.confidence * 100).toFixed(1)}%`);
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
