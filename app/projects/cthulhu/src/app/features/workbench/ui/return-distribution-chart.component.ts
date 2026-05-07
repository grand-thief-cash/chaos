import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NgxEchartsModule } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { BacktestArtifacts, Bar } from '../models/workbench.model';

interface DistributionStats {
  mean: number;
  stdDev: number;
  skewness: number;
  kurtosis: number;  // excess kurtosis
  count: number;
  min: number;
  max: number;
  median: number;
}

@Component({
  selector: 'app-return-distribution-chart',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzEmptyModule, NzStatisticModule, NzGridModule, NgxEchartsModule, DecimalPipe],
  template: `
    <nz-card nzTitle="Return Distribution">
      @if (!stats) {
        <nz-empty nzNotFoundContent="No data available"></nz-empty>
      } @else {
        <!-- Stats row -->
        <div style="display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 16px; padding: 12px; background: #fafafa; border-radius: 6px;">
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Mean</div>
            <div style="font-size: 16px; font-weight: 500;">{{ stats.mean * 100 | number:'1.4-4' }}%</div>
          </div>
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Std Dev</div>
            <div style="font-size: 16px; font-weight: 500;">{{ stats.stdDev * 100 | number:'1.4-4' }}%</div>
          </div>
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Skewness</div>
            <div style="font-size: 16px; font-weight: 500;" [style.color]="skewnessColor">{{ stats.skewness | number:'1.4-4' }}</div>
          </div>
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Kurtosis (Excess)</div>
            <div style="font-size: 16px; font-weight: 500;" [style.color]="kurtosisColor">{{ stats.kurtosis | number:'1.4-4' }}</div>
          </div>
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Median</div>
            <div style="font-size: 16px; font-weight: 500;">{{ stats.median * 100 | number:'1.4-4' }}%</div>
          </div>
          <div style="text-align: center; min-width: 100px;">
            <div style="color: #8c8c8c; font-size: 12px;">Samples</div>
            <div style="font-size: 16px; font-weight: 500;">{{ stats.count }}</div>
          </div>
        </div>

        <!-- Histogram + Normal overlay -->
        @if (chartOptions) {
          <div echarts [options]="chartOptions" style="height: 360px;"></div>
        }

        <!-- Interpretation -->
        <div style="margin-top: 12px; padding: 10px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; font-size: 12px; color: #595959;">
          <strong>Interpretation:</strong>
          Skewness {{ stats.skewness >= 0 ? '> 0 (right-skewed: tail risk on upside)' : '< 0 (left-skewed: tail risk on downside, more common in equities)' }}.
          Excess Kurtosis {{ stats.kurtosis > 0 ? '> 0 (leptokurtic: fat tails, more extreme events than normal distribution)' : stats.kurtosis < 0 ? '< 0 (platykurtic: thin tails, fewer extreme events)' : '≈ 0 (mesokurtic: similar to normal distribution)' }}.
        </div>
      }
    </nz-card>
  `,
})
export class ReturnDistributionChartComponent implements OnChanges {
  @Input() artifacts: BacktestArtifacts | null = null;
  @Input() bars: Bar[] | null = null;

  stats: DistributionStats | null = null;
  chartOptions: EChartsOption | null = null;

  get skewnessColor(): string {
    if (!this.stats) return '#000';
    return Math.abs(this.stats.skewness) > 1 ? '#cf1322' : Math.abs(this.stats.skewness) > 0.5 ? '#fa8c16' : '#3f8600';
  }

  get kurtosisColor(): string {
    if (!this.stats) return '#000';
    return Math.abs(this.stats.kurtosis) > 3 ? '#cf1322' : Math.abs(this.stats.kurtosis) > 1 ? '#fa8c16' : '#3f8600';
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['artifacts'] || changes['bars']) {
      this.compute();
    }
  }

  private compute(): void {
    const bars = this.artifacts?.bars ?? this.bars;
    if (!bars || bars.length < 3) {
      this.stats = null;
      this.chartOptions = null;
      return;
    }

    // Compute daily returns
    const returns: number[] = [];
    for (let i = 1; i < bars.length; i++) {
      const prev = bars[i - 1].close;
      const curr = bars[i].close;
      if (prev > 0) {
        returns.push((curr - prev) / prev);
      }
    }

    if (returns.length < 3) {
      this.stats = null;
      this.chartOptions = null;
      return;
    }

    const n = returns.length;
    const mean = returns.reduce((a, b) => a + b, 0) / n;
    const sorted = [...returns].sort((a, b) => a - b);
    const median = n % 2 === 0 ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2 : sorted[Math.floor(n / 2)];

    // Variance, std dev
    const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / (n - 1);
    const stdDev = Math.sqrt(variance);

    // Skewness (adjusted Fisher-Pearson)
    const m3 = returns.reduce((sum, r) => sum + ((r - mean) / stdDev) ** 3, 0);
    const skewness = (n / ((n - 1) * (n - 2))) * m3;

    // Excess Kurtosis (Fisher)
    const m4 = returns.reduce((sum, r) => sum + ((r - mean) / stdDev) ** 4, 0);
    const kurtosis = ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * m4
                     - (3 * (n - 1) ** 2) / ((n - 2) * (n - 3));

    this.stats = {
      mean, stdDev, skewness, kurtosis,
      count: n,
      min: sorted[0],
      max: sorted[n - 1],
      median,
    };

    this.buildChart(returns, mean, stdDev);
  }

  private buildChart(returns: number[], mean: number, stdDev: number): void {
    const nBins = Math.min(50, Math.max(15, Math.ceil(Math.sqrt(returns.length))));
    this.chartOptions = this.buildProperChart(returns, mean, stdDev, nBins);
  }

  private buildProperChart(returns: number[], mean: number, stdDev: number, nBins: number): EChartsOption {
    const min = Math.min(...returns);
    const max = Math.max(...returns);
    const range = max - min || 0.01;
    const binWidth = range / nBins;

    const bins: number[] = new Array(nBins).fill(0);
    const binEdges: number[] = [];
    for (let i = 0; i <= nBins; i++) {
      binEdges.push(min + binWidth * i);
    }

    for (const r of returns) {
      let idx = Math.floor((r - min) / binWidth);
      if (idx >= nBins) idx = nBins - 1;
      if (idx < 0) idx = 0;
      bins[idx]++;
    }

    const totalArea = returns.length * binWidth;
    const density = bins.map(b => b / totalArea);

    // Bar data with bin centers as x
    const barData = density.map((d, i) => {
      const center = (binEdges[i] + binEdges[i + 1]) / 2;
      return [center * 100, d]; // x in %, y in density
    });

    // Normal curve
    const normalData: [number, number][] = [];
    const plotMin = (mean - 4 * stdDev) * 100;
    const plotMax = (mean + 4 * stdDev) * 100;
    for (let i = 0; i <= 100; i++) {
      const xPct = plotMin + (plotMax - plotMin) * i / 100;
      const x = xPct / 100;
      const y = (1 / (stdDev * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * ((x - mean) / stdDev) ** 2);
      normalData.push([xPct, y]);
    }

    // Mean line
    const maxDensity = Math.max(...density) * 1.1;

    return {
      tooltip: {
        trigger: 'item',
      },
      legend: {
        data: ['Return Distribution', 'Normal Fit', 'Mean'],
        top: 0,
      },
      grid: { left: 60, right: 30, top: 40, bottom: 50 },
      xAxis: {
        type: 'value',
        name: 'Daily Return (%)',
        nameLocation: 'middle',
        nameGap: 30,
        min: Math.min(plotMin, min * 100) - 0.5,
        max: Math.max(plotMax, max * 100) + 0.5,
        axisLabel: { formatter: '{value}%' },
      },
      yAxis: {
        type: 'value',
        name: 'Density',
        axisLabel: { formatter: (v: number) => v.toFixed(1) },
      },
      series: [
        {
          name: 'Return Distribution',
          type: 'bar',
          data: barData,
          barWidth: binWidth * 100 * 0.9,
          itemStyle: {
            color: (params: any) => {
              const x = params.data[0];
              return x >= 0 ? 'rgba(24,144,255,0.6)' : 'rgba(255,77,79,0.5)';
            },
          },
          tooltip: {
            formatter: (params: any) =>
              `Return: ${params.data[0].toFixed(2)}%<br/>Density: ${params.data[1].toFixed(4)}`,
          },
        },
        {
          name: 'Normal Fit',
          type: 'line',
          data: normalData,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#ff7a45', width: 2, type: 'dashed' },
          tooltip: {
            formatter: (params: any) =>
              `Normal: ${params.data[0].toFixed(2)}%<br/>Density: ${params.data[1].toFixed(4)}`,
          },
        },
        {
          name: 'Mean',
          type: 'line',
          data: [[mean * 100, 0], [mean * 100, maxDensity]],
          lineStyle: { color: '#722ed1', width: 1.5, type: 'dotted' },
          showSymbol: false,
          tooltip: {
            formatter: () => `Mean: ${(mean * 100).toFixed(4)}%`,
          },
        },
      ],
    } as EChartsOption;
  }
}
