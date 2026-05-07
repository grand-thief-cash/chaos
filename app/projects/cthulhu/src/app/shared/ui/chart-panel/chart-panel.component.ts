import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { Bar, IndicatorSeriesMeta } from './chart-panel.models';

@Component({
  selector: 'app-chart-panel',
  standalone: true,
  imports: [CommonModule, NgxEchartsModule],
  template: `
    @if (options) {
      <div echarts [options]="options" [style.height.px]="containerHeight" style="width: 100%;"></div>
    }
  `,
})
export class ChartPanelComponent implements OnChanges {
  @Input() bars: Bar[] = [];
  @Input() indicators: Record<string, (number | null)[]> = {};
  @Input() indicatorMeta: Record<string, IndicatorSeriesMeta> = {};
  @Input() lockYAxis = false;
  @Input() showVolume = true;
  @Input() mainHeight = 450;
  @Input() volumeHeight = 120;
  @Input() subChartHeight = 150;

  options: EChartsOption | null = null;
  containerHeight = 0;

  ngOnChanges(changes: SimpleChanges): void {
    if (
      changes['bars'] || changes['indicators'] || changes['indicatorMeta']
      || changes['lockYAxis'] || changes['showVolume']
      || changes['mainHeight'] || changes['volumeHeight'] || changes['subChartHeight']
    ) {
      this.buildChart();
    }
  }

  private buildChart(): void {
    if (!this.bars.length) {
      this.options = null;
      return;
    }

    const dates = this.bars.map((b) => b.date);
    const ohlc = this.bars.map((b) => [b.open, b.close, b.low, b.high]);
    const volumes = this.bars.map((b) => b.volume);

    // Y 轴锁定：计算全量数据范围
    let mainYMin: number | undefined;
    let mainYMax: number | undefined;
    if (this.lockYAxis) {
      let lo = Infinity;
      let hi = -Infinity;
      for (const b of this.bars) {
        if (b.low < lo) lo = b.low;
        if (b.high > hi) hi = b.high;
      }
      // overlay 指标也纳入范围
      for (const [key, values] of Object.entries(this.indicators)) {
        const meta = this.indicatorMeta[key];
        if (meta?.overlay) {
          for (const v of values) {
            if (v !== null) {
              if (v < lo) lo = v;
              if (v > hi) hi = v;
            }
          }
        }
      }
      const padding = (hi - lo) * 0.05;
      mainYMin = lo - padding;
      mainYMax = hi + padding;
    }

    // 子图指标分组
    const subChartGroups: Record<string, string[]> = {};
    const overlaySeries: any[] = [];

    for (const [key, values] of Object.entries(this.indicators)) {
      const meta = this.indicatorMeta[key];
      if (!meta) continue;

      if (meta.overlay) {
        overlaySeries.push({
          name: key,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: values,
          smooth: true,
          lineStyle: { width: 1.5, color: Array.isArray(meta.color) ? meta.color[0] : meta.color },
          symbol: 'none',
        });
      } else {
        const yName = meta.y_axis || key;
        if (!subChartGroups[yName]) subChartGroups[yName] = [];
        subChartGroups[yName].push(key);
      }
    }

    // ---- 像素级网格布局，彻底避免百分比溢出 ----
    const gap = 18; // 充足间距避免轴标签溢出重叠
    const legendH = 30;

    let curTop = legendH;
    const grids: any[] = [];
    const xAxes: any[] = [];
    const yAxes: any[] = [];
    const xAxisIndices: number[] = [];

    // 主图 grid（containLabel 将轴标签约束在 grid 内，防止溢出到相邻图表）
    grids.push({ left: '8%', right: '3%', top: curTop, height: this.mainHeight, containLabel: true });
    xAxes.push({ type: 'category', data: dates, gridIndex: 0, show: false });
    const mainYAxis: any = { type: 'value', gridIndex: 0, scale: true };
    if (this.lockYAxis) {
      mainYAxis.min = mainYMin;
      mainYAxis.max = mainYMax;
    }
    yAxes.push(mainYAxis);
    xAxisIndices.push(0);
    curTop += this.mainHeight + gap;

    // Volume grid（可选）
    if (this.showVolume) {
      grids.push({ left: '8%', right: '3%', top: curTop, height: this.volumeHeight, containLabel: true });
      xAxes.push({ type: 'category', data: dates, gridIndex: grids.length - 1, show: false });
      yAxes.push({ type: 'value', gridIndex: grids.length - 1, scale: true });
      xAxisIndices.push(grids.length - 1);
      curTop += this.volumeHeight + gap;
    }

    // 子图 grids
    const subGroupNames = Object.keys(subChartGroups);
    subGroupNames.forEach((groupName, idx) => {
      const gi = grids.length;
      grids.push({ left: '8%', right: '3%', top: curTop, height: this.subChartHeight, containLabel: true });
      xAxes.push({ type: 'category', data: dates, gridIndex: gi, show: idx === subGroupNames.length - 1 });
      yAxes.push({ type: 'value', gridIndex: gi, scale: true, name: groupName });
      xAxisIndices.push(gi);
      curTop += this.subChartHeight + gap;
    });

    // 容器高度 = 所有图表 + dataZoom 滑块 + 底部边距
    this.containerHeight = curTop + 40;

    // Series
    const allSeries: any[] = [
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
    ];

    if (this.showVolume) {
      allSeries.push({
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#7986cb', opacity: 0.5 },
      });
    }

    allSeries.push(...overlaySeries);

    // 子图 series
    let subGridOffset = (this.showVolume ? 2 : 1);
    for (const groupName of subGroupNames) {
      const gi = subGridOffset;
      for (const key of subChartGroups[groupName]) {
        const meta = this.indicatorMeta[key];
        const color = Array.isArray(meta.color) ? meta.color[0] : meta.color;

        if (meta.type === 'bar') {
          const barData = (this.indicators[key] || []).map((v) => ({
            value: v,
            itemStyle: { color: v !== null && v >= 0 ? '#26a69a' : '#ef5350' },
          }));
          allSeries.push({
            name: key, type: 'bar', xAxisIndex: gi, yAxisIndex: gi, data: barData,
          });
        } else {
          allSeries.push({
            name: key, type: 'line', xAxisIndex: gi, yAxisIndex: gi,
            data: this.indicators[key],
            smooth: true, lineStyle: { width: 1.5, color }, symbol: 'none',
          });
        }
      }
      subGridOffset++;
    }

    this.options = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: allSeries.map((s) => s.name), top: 0 },
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      dataZoom: [
        { type: 'inside', xAxisIndex: xAxisIndices, start: 0, end: 100 },
        { type: 'slider', xAxisIndex: xAxisIndices, bottom: 5 },
      ],
      series: allSeries,
    };
  }
}
