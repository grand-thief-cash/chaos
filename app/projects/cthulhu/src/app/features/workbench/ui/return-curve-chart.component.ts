import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { BacktestArtifacts } from '../models/workbench.model';

@Component({
  selector: 'app-return-curve-chart',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzEmptyModule, NgxEchartsModule],
  template: `
    <nz-card nzTitle="Return Rate Curve (收益率曲线)">
      @if (options) {
        <div echarts [options]="options" style="height: 350px;"></div>
      } @else {
        <nz-empty></nz-empty>
      }
    </nz-card>
  `,
})
export class ReturnCurveChartComponent implements OnChanges {
  @Input() artifacts: BacktestArtifacts | null = null;
  options: EChartsOption | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['artifacts'] && this.artifacts) {
      this.buildChart();
    }
  }

  private buildChart(): void {
    if (!this.artifacts) return;
    const curve = this.artifacts.return_curve || [];
    if (curve.length === 0) return;

    const timestamps = curve.map((p) => p.timestamp.split('T')[0]);
    const returns = curve.map((p) => Math.round(p.return_pct * 10000) / 100); // → percentage

    this.options = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          return `${p.axisValue}<br/>Return: <b>${p.value}%</b>`;
        },
      },
      legend: { data: ['Return Rate'] },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: timestamps, boundaryGap: false },
      yAxis: [
        {
          type: 'value',
          name: 'Return %',
          axisLabel: { formatter: '{value}%' },
        },
      ],
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100 },
      ],
      visualMap: {
        show: false,
        pieces: [
          { lte: 0, color: '#ff4d4f' },
          { gt: 0, color: '#52c41a' },
        ],
      },
      series: [
        {
          name: 'Return Rate',
          type: 'line',
          data: returns,
          smooth: true,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.15 },
          markLine: {
            silent: true,
            data: [{ yAxis: 0, lineStyle: { color: '#999', type: 'dashed' } }],
          },
        },
      ],
    };
  }
}

