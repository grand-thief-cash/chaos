import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { BITrendSection } from '../models/bi.models';

@Component({
  selector: 'app-bi-trend-chart',
  standalone: true,
  imports: [CommonModule, NgxEchartsModule],
  template: `
    @if (options) {
      <div echarts [options]="options" [style.height.px]="height" style="width: 100%;"></div>
    }
  `,
})
export class TrendChartComponent implements OnChanges {
  @Input({ required: true }) section!: BITrendSection;
  @Input() height = 320;
  @Input() periodLimit: 12 | 16 | 20 = 12;
  @Input() viewMode: 'quarterly' | 'annual' = 'quarterly';

  options: EChartsOption | null = null;

  ngOnChanges(): void {
    this.options = this.buildOptions();
  }

  private buildOptions(): EChartsOption | null {
    if (!this.section?.periods?.length || !this.section?.series?.length) {
      return null;
    }

    // Defensive reorder: guarantee chronological plotting even if backend returns newest-first.
    const ordered = this.section.periods
      .map((period, index) => ({ period, index }))
      .sort((a, b) => a.period.localeCompare(b.period))
      .filter((item) => this.viewMode === 'quarterly' || this.isAnnualPeriod(item.period));

    const tail = ordered.slice(Math.max(0, ordered.length - this.periodLimit));
    if (tail.length === 0) {
      return null;
    }

    const orderedIndices = tail.map((item) => item.index);
    const orderedPeriods = tail.map((item) => item.period);

    const palette = ['#1677ff', '#52c41a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96'];
    return {
      color: palette,
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 56, right: 18, top: 40, bottom: 36 },
      xAxis: {
        type: 'category',
        data: orderedPeriods,
        axisLabel: { rotate: 30 },
      },
      yAxis: {
        type: 'value',
        scale: true,
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 8 },
      ],
      series: this.section.series.map((series, index) => ({
        name: series.label,
        type: index === 0 ? 'bar' : 'line',
        smooth: index !== 0,
        symbol: index === 0 ? 'none' : 'circle',
        symbolSize: 6,
        emphasis: { focus: 'series' },
        data: orderedIndices.map((i) => series.values[i]),
      })),
    } satisfies EChartsOption;
  }

  private isAnnualPeriod(period: string): boolean {
    return /-12-31$/.test(period);
  }
}

