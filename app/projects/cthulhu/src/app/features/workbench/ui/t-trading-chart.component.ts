import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges } from '@angular/core';
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';
import { NgxEchartsModule } from 'ngx-echarts';

import {
  Bar,
  TFill,
  TIndicatorPoint,
  TIndicatorSet,
  TSignal,
  TStrategyName,
} from '../models/workbench.model';

const STRATEGY_VISUALS: Record<TStrategyName, {
  label: string;
  buy: string;
  sell: string;
}> = {
  causal_mean_reversion_v1: { label: '均值反转', buy: '#cf1322', sell: '#820014' },
  macd_volume_momentum_v1: { label: 'MACD 量价回归', buy: '#f5222d', sell: '#52c41a' },
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
      <div echarts [options]="options" style="width: 100%; height: 840px;"></div>
    }
  `,
})
export class TTradingChartComponent implements OnChanges {
  @Input() bars: Bar[] = [];
  @Input() signals: TSignal[] = [];
  @Input() fills: TFill[] = [];
  @Input() indicatorSet: TIndicatorSet | null = null;

  options: EChartsOption | null = null;

  ngOnChanges(): void {
    this.buildChart();
  }

  private values(key: keyof TIndicatorPoint): Array<number | null> {
    return (this.indicatorSet?.points ?? []).map((point) => {
      const value = point[key];
      return typeof value === 'number' ? value : null;
    });
  }

  private indicatorLine(
    name: string,
    key: keyof TIndicatorPoint,
    color: string,
    dashed = false,
  ): any {
    return {
      name,
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: this.values(key),
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.3, color, type: dashed ? 'dashed' : 'solid' },
      emphasis: { focus: 'series' },
    };
  }

  private priceIndicators(): any[] {
    const strategy = this.indicatorSet?.strategy;
    if (!strategy) return [];
    if (strategy === 'opening_range_breakout_v1') {
      return [
        this.indicatorLine('EMA 快', 'ema_fast', '#1677ff'),
        this.indicatorLine('EMA 慢', 'ema_slow', '#fa8c16'),
        this.indicatorLine('VWAP', 'vwap', '#722ed1', true),
        this.indicatorLine('开盘区间高', 'opening_range_high', '#389e0d', true),
        this.indicatorLine('开盘区间低', 'opening_range_low', '#cf1322', true),
      ];
    }
    if (
      strategy === 'causal_mean_reversion_v1'
      || strategy === 'vwap_bollinger_reversion_v1'
    ) {
      return [
        this.indicatorLine('VWAP', 'vwap', '#722ed1'),
        this.indicatorLine('Bollinger 上轨', 'bollinger_upper', '#cf1322', true),
        this.indicatorLine('Bollinger 下轨', 'bollinger_lower', '#389e0d', true),
      ];
    }
    return [
      this.indicatorLine('EMA 快', 'ema_fast', '#1677ff'),
      this.indicatorLine('EMA 慢', 'ema_slow', '#fa8c16'),
      this.indicatorLine('VWAP', 'vwap', '#722ed1', true),
    ];
  }

  private buildChart(): void {
    if (!this.bars.length) {
      this.options = null;
      return;
    }
    const categories = this.bars.map((bar) => bar.date);
    const label = (value: string) => dayjs(value).format('HH:mm');
    const macdLineRange = this.symmetricRange([
      ...this.values('macd'), ...this.values('macd_signal'),
    ]);
    const macdHistRange = this.symmetricRange(this.values('macd_hist'));
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
        name: '分钟 K', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: this.bars.map((bar) => [bar.open, bar.close, bar.low, bar.high]),
        itemStyle: { color: '#f5222d', color0: '#13a8a8', borderColor: '#f5222d', borderColor0: '#13a8a8' },
      },
      ...this.priceIndicators(),
      ...decisionSeries,
      ...(fillPoints.length ? [{
        name: '下一根成交', type: 'scatter', xAxisIndex: 0, yAxisIndex: 0,
        data: fillPoints, symbol: 'diamond', symbolSize: 12,
      }] : []),
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: this.bars.map((bar) => bar.volume), itemStyle: { color: '#91a7ff', opacity: 0.55 },
      },
      {
        name: this.indicatorSet?.strategy === 'time_of_day_volume_momentum_v1' ? '同分钟量比' : '滚动量比',
        type: 'line', xAxisIndex: 1, yAxisIndex: 2, showSymbol: false,
        data: this.indicatorSet?.strategy === 'time_of_day_volume_momentum_v1'
          ? this.values('relative_volume_tod') : this.values('volume_ratio'),
        lineStyle: { color: '#722ed1', width: 1.2 },
      },
      {
        name: 'MACD 柱', type: 'bar', xAxisIndex: 2, yAxisIndex: 4,
        data: this.values('macd_hist').map((value) => ({
          value,
          itemStyle: {
            color: value !== null && value >= 0 ? '#f5222d' : '#52c41a',
            opacity: 0.78,
          },
        })),
      },
      {
        name: 'MACD', type: 'line', xAxisIndex: 2, yAxisIndex: 3,
        data: this.values('macd'), showSymbol: false, lineStyle: { color: '#1677ff', width: 1.1 },
      },
      {
        name: 'MACD Signal', type: 'line', xAxisIndex: 2, yAxisIndex: 3,
        data: this.values('macd_signal'), showSymbol: false, lineStyle: { color: '#fa8c16', width: 1.1 },
      },
      {
        name: 'RSI', type: 'line', xAxisIndex: 3, yAxisIndex: 5,
        data: this.values('rsi'), showSymbol: false, lineStyle: { color: '#722ed1', width: 1.2 },
        markLine: {
          symbol: 'none', silent: true,
          data: [{ yAxis: 30, lineStyle: { color: '#389e0d', type: 'dashed' } }, { yAxis: 70, lineStyle: { color: '#cf1322', type: 'dashed' } }],
        },
      },
    ];

    this.options = {
      animation: false,
      legend: { type: 'scroll', top: 0, left: 60, right: 30 },
      axisPointer: { link: [{ xAxisIndex: [0, 1, 2, 3] }] },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) return '';
          const lines = [`<b>${label(items[0].axisValue)}</b>`];
          for (const item of items) {
            if (item.seriesName === '分钟 K' && Array.isArray(item.data)) {
              lines.push(`O ${item.data[1]} / C ${item.data[2]} / L ${item.data[3]} / H ${item.data[4]}`);
            } else if (item.data?.signal) {
              const signal = item.data.signal as TSignal;
              const strategy = STRATEGY_VISUALS[signal.strategy].label;
              lines.push(`${strategy} · ${signal.side} 判断 ${signal.decision_price} · 置信度 ${(signal.confidence * 100).toFixed(1)}%`);
            } else if (item.data?.fill) {
              const fill = item.data.fill as TFill;
              lines.push(`${fill.side} 成交 ${fill.fill_price} · 费用 ${fill.total_fee}`);
            } else if (typeof item.data === 'number') {
              lines.push(`${item.seriesName}: ${item.data.toFixed(4)}`);
            } else if (typeof item.data?.value === 'number') {
              lines.push(`${item.seriesName}: ${item.data.value.toFixed(4)}`);
            }
          }
          return lines.join('<br/>');
        },
      },
      grid: [
        { left: 64, right: 58, top: 48, height: 370 },
        { left: 64, right: 58, top: 442, height: 90 },
        { left: 64, right: 58, top: 557, height: 95 },
        { left: 64, right: 58, top: 677, height: 82 },
      ],
      xAxis: [0, 1, 2, 3].map((gridIndex) => ({
        type: 'category', data: categories, gridIndex, boundaryGap: true,
        axisLabel: { formatter: label, show: gridIndex === 3 }, min: 'dataMin', max: 'dataMax',
      })),
      yAxis: [
        { scale: true, splitArea: { show: true } },
        { gridIndex: 1, scale: true, splitNumber: 2, axisLabel: { show: false } },
        { gridIndex: 1, scale: true, position: 'right', splitLine: { show: false }, name: '量比' },
        {
          gridIndex: 2, min: macdLineRange.min, max: macdLineRange.max,
          splitNumber: 2, name: 'DIF / DEA',
        },
        {
          gridIndex: 2, min: macdHistRange.min, max: macdHistRange.max,
          splitNumber: 2, position: 'right', name: 'MACD 柱',
          splitLine: { show: false },
        },
        { gridIndex: 3, min: 0, max: 100, splitNumber: 2 },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 4, start: 0, end: 100 },
      ],
      series,
    };
  }

  private symmetricRange(values: Array<number | null>): { min: number; max: number } {
    const finite = values.filter((value): value is number => (
      typeof value === 'number' && Number.isFinite(value)
    ));
    const magnitude = Math.max(
      ...finite.map((value) => Math.abs(value)), 1e-6,
    ) * 1.1;
    return { min: -magnitude, max: magnitude };
  }
}
