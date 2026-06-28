import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type Trend = 'up' | 'down';

interface ProfitabilityKpi {
  label: string;
  value: string;
  samePeriod: string;
  industryAvg: string;
  trend: Trend;
}

interface RadarSeries {
  label: string;
  color: string;
  values: number[];
}

interface TrendSeries {
  label: string;
  color: string;
  values: number[];
}

interface ProfitMetric {
  key: string;
  label: string;
  current: string;
  samePeriod: string;
  industryAvg: string;
  trend: Trend;
  series: TrendSeries[];
}

interface ProfitabilityRow {
  category: string;
  org: string;
  roa: string;
  roe: string;
  cashCover: string;
  ebitda: string;
  costProfit: string;
  grossMargin: string;
  operatingMargin: string;
  netMargin: string;
}

@Component({
  selector: 'app-bi-profitability-analysis-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="profitability-page">
      <header class="page-header">
        <div>
          <h1>盈利能力分析</h1>
          <span>更新日期：2025年2月11日</span>
        </div>
        <div class="filters">
          <label>
            <span>年月</span>
            <input type="month" [(ngModel)]="selectedMonth" />
          </label>
          <label>
            <span>组织</span>
            <select [(ngModel)]="selectedOrg">
              @for (org of organizations; track org) {
                <option [value]="org">{{ org }}</option>
              }
            </select>
          </label>
          <label>
            <span>对标口径</span>
            <select [(ngModel)]="selectedBenchmark">
              @for (benchmark of benchmarks; track benchmark) {
                <option [value]="benchmark">{{ benchmark }}</option>
              }
            </select>
          </label>
        </div>
      </header>

      <section class="kpi-grid" aria-label="盈利能力核心指标">
        @for (kpi of kpis; track kpi.label) {
          <article class="kpi-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
            <div class="kpi-meta">
              <em>同期值：{{ kpi.samePeriod }}</em>
              <em>业内平均：{{ kpi.industryAvg }}</em>
              <b [class]="trendClass(kpi.trend)">{{ trendArrow(kpi.trend) }}</b>
            </div>
          </article>
        }
      </section>

      <section class="analysis-grid">
        <article class="panel radar-panel">
          <header>
            <h2>关键盈利能力指标对标</h2>
            <span>内部 / 外部 / 行业均值</span>
          </header>
          <div class="radar-layout">
            <svg class="radar-chart" viewBox="0 0 520 360" role="img" aria-label="关键盈利能力指标雷达图">
              @for (level of radarLevels; track level) {
                <polygon class="radar-ring" [attr.points]="radarPolygon(level)"></polygon>
              }
              @for (axis of radarAxes; track axis; let index = $index) {
                <line class="radar-axis" x1="260" y1="178" [attr.x2]="radarPoint(index, 100).x" [attr.y2]="radarPoint(index, 100).y"></line>
                <text class="radar-label" [attr.x]="radarPoint(index, 116).x" [attr.y]="radarPoint(index, 116).y">{{ axis }}</text>
              }
              @for (series of radarSeries; track series.label) {
                <polygon class="radar-series" [attr.points]="radarPolygonPoints(series.values)" [attr.stroke]="series.color" [attr.fill]="series.color"></polygon>
              }
            </svg>
            <div class="legend vertical">
              @for (series of radarSeries; track series.label) {
                <span><i [style.background]="series.color"></i>{{ series.label }}</span>
              }
            </div>
          </div>
        </article>

        <article class="panel trend-panel">
          <header>
            <h2>{{ selectedMetric.label }}变动趋势</h2>
            <label>
              <span>指标名称</span>
              <select [(ngModel)]="selectedMetricKey">
                @for (metric of metrics; track metric.key) {
                  <option [value]="metric.key">{{ metric.label }}</option>
                }
              </select>
            </label>
          </header>
          <div class="trend-summary">
            <strong>{{ selectedMetric.current }}</strong>
            <span>同期值：{{ selectedMetric.samePeriod }}</span>
            <span>业内平均：{{ selectedMetric.industryAvg }}</span>
            <b [class]="trendClass(selectedMetric.trend)">{{ trendArrow(selectedMetric.trend) }}</b>
          </div>
          <svg class="line-chart" viewBox="0 0 620 300" role="img" aria-label="盈利能力指标趋势">
            @for (tick of yTicks; track tick) {
              <line class="grid-line" x1="42" [attr.y1]="chartY(tick)" x2="594" [attr.y2]="chartY(tick)"></line>
              <text class="y-label" x="12" [attr.y]="chartY(tick) + 4">{{ tick }}%</text>
            }
            @for (month of months; track month; let index = $index) {
              <text class="x-label" [attr.x]="chartX(index)" y="284">{{ month }}</text>
            }
            @for (series of selectedMetric.series; track series.label) {
              <path class="line-path" [attr.d]="linePath(series.values)" [attr.stroke]="series.color"></path>
              @for (value of series.values; track indexValue(index, value); let index = $index) {
                <circle class="line-dot" r="4" [attr.cx]="chartX(index)" [attr.cy]="chartY(value)" [attr.fill]="series.color"></circle>
              }
            }
          </svg>
          <div class="legend">
            @for (series of selectedMetric.series; track series.label) {
              <span><i [style.background]="series.color"></i>{{ series.label }}</span>
            }
          </div>
        </article>

        <article class="panel table-panel">
          <header>
            <h2>各项指标明细</h2>
            <span>本期值 / 同期值 / 行业均值用于后续接数校验</span>
          </header>
          <table>
            <thead>
              <tr>
                <th>数据分类</th>
                <th>组织名称</th>
                <th>总资产报酬率</th>
                <th>净资产收益率</th>
                <th>盈余现金保障倍数</th>
                <th>EBITDA利润率</th>
                <th>成本费用利润率</th>
                <th>毛利率</th>
                <th>营业利润率</th>
                <th>净利润率</th>
              </tr>
            </thead>
            <tbody>
              @for (row of rows; track row.category + row.org) {
                <tr>
                  <td>{{ row.category }}</td>
                  <td>{{ row.org }}</td>
                  <td>{{ row.roa }}</td>
                  <td>{{ row.roe }}</td>
                  <td>{{ row.cashCover }}</td>
                  <td>{{ row.ebitda }}</td>
                  <td>{{ row.costProfit }}</td>
                  <td>{{ row.grossMargin }}</td>
                  <td>{{ row.operatingMargin }}</td>
                  <td>{{ row.netMargin }}</td>
                </tr>
              }
            </tbody>
          </table>
        </article>
      </section>
    </section>
  `,
  styles: [`
    :host {
      display: block;
      min-height: calc(100vh - 110px);
      background: #eef4fb;
      color: #172033;
      font-size: 14px;
    }

    .profitability-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: center;
      padding: 18px 22px;
      background: linear-gradient(100deg, #1f68d8 0%, #48a0eb 54%, #d9efe9 100%);
      color: #fff;
    }

    h1,
    h2 {
      margin: 0;
      letter-spacing: 0;
    }

    h1 {
      font-size: 30px;
      line-height: 1.2;
    }

    .page-header span {
      font-weight: 650;
    }

    .filters {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 650;
    }

    select,
    input {
      height: 34px;
      min-width: 136px;
      border: 1px solid rgba(34, 72, 112, 0.28);
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.68);
      color: #172033;
      padding: 0 10px;
      font-size: 14px;
      font-weight: 620;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(180px, 1fr));
      gap: 12px;
    }

    .kpi-card,
    .panel {
      background: #fff;
      border: 1px solid #dce7f2;
    }

    .kpi-card {
      padding: 16px;
      min-height: 132px;
    }

    .kpi-card span,
    .panel header span,
    .trend-summary span {
      color: #657386;
      font-size: 13px;
      line-height: 1.45;
    }

    .kpi-card strong {
      display: block;
      margin: 12px 0;
      color: #116ecf;
      font-size: 32px;
      line-height: 1;
    }

    .kpi-meta {
      display: grid;
      grid-template-columns: 1fr 1fr auto;
      gap: 8px;
      align-items: center;
      font-size: 14px;
      font-style: normal;
      line-height: 1.4;
    }

    .kpi-meta em {
      font-style: normal;
      font-weight: 650;
    }

    .trend-up {
      color: #19a45f;
    }

    .trend-down {
      color: #e84f63;
    }

    .analysis-grid {
      display: grid;
      grid-template-columns: 1fr 1.05fr;
      gap: 12px;
    }

    .panel {
      padding: 16px;
      min-height: 360px;
    }

    .panel header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 12px;
    }

    h2 {
      font-size: 18px;
      line-height: 1.25;
    }

    .radar-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 120px;
      gap: 12px;
      align-items: center;
    }

    .radar-chart,
    .line-chart {
      width: 100%;
      height: 300px;
    }

    .radar-ring {
      fill: none;
      stroke: #dce5ef;
      stroke-width: 1;
    }

    .radar-axis,
    .grid-line {
      stroke: #e6edf5;
      stroke-width: 1;
    }

    .radar-label,
    .x-label,
    .y-label {
      fill: #657386;
      font-size: 13px;
      text-anchor: middle;
    }

    .radar-series {
      fill-opacity: 0.1;
      stroke-width: 3;
    }

    .trend-summary {
      display: flex;
      gap: 16px;
      align-items: center;
      padding: 10px 12px;
      margin-bottom: 8px;
      background: #f7fbff;
      border: 1px solid #e1ebf6;
    }

    .trend-summary strong {
      color: #116ecf;
      font-size: 24px;
    }

    .line-path {
      fill: none;
      stroke-width: 3;
    }

    .line-dot {
      stroke: #fff;
      stroke-width: 2;
    }

    .legend {
      display: flex;
      gap: 16px;
      color: #657386;
      font-size: 13px;
      line-height: 1.45;
    }

    .legend.vertical {
      flex-direction: column;
    }

    .legend i {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 6px;
      vertical-align: -1px;
    }

    .table-panel {
      grid-column: 1 / -1;
      min-height: auto;
      overflow: auto;
    }

    table {
      width: 100%;
      min-width: 1040px;
      border-collapse: collapse;
      font-size: 14px;
    }

    th,
    td {
      padding: 12px 10px;
      border: 1px solid #e5edf6;
      text-align: center;
      white-space: nowrap;
    }

    th {
      background: #c9e2fb;
      color: #17304d;
      font-weight: 720;
    }

    @media (max-width: 1200px) {
      .page-header {
        align-items: flex-start;
        flex-direction: column;
      }

      .filters {
        justify-content: flex-start;
      }

      .kpi-grid {
        grid-template-columns: repeat(2, minmax(180px, 1fr));
      }

      .analysis-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 720px) {
      .kpi-grid,
      .radar-layout {
        grid-template-columns: 1fr;
      }

      .panel header,
      .trend-summary {
        align-items: flex-start;
        flex-direction: column;
      }

      label,
      select,
      input {
        width: 100%;
      }
    }
  `],
})
export class ProfitabilityAnalysisPageComponent {
  organizations = ['XXX集团', '华东事业群', '上市公司合并口径'];
  benchmarks = ['外部组织', '行业均值', '集团预算'];
  selectedMonth = '2025-02';
  selectedOrg = this.organizations[0];
  selectedBenchmark = this.benchmarks[0];
  selectedMetricKey = 'roa';

  kpis: ProfitabilityKpi[] = [
    { label: '总资产报酬率', value: '27.61%', samePeriod: '53.86%', industryAvg: '61.37%', trend: 'up' },
    { label: '净资产收益率', value: '75.80%', samePeriod: '50.42%', industryAvg: '79.53%', trend: 'up' },
    { label: '盈余现金保障倍数', value: '65.46%', samePeriod: '12.96%', industryAvg: '38.85%', trend: 'up' },
    { label: 'EBITDA利润率', value: '80.57%', samePeriod: '15.17%', industryAvg: '88.18%', trend: 'up' },
    { label: '成本费用利润率', value: '52.77%', samePeriod: '87.19%', industryAvg: '64.39%', trend: 'down' },
    { label: '毛利率', value: '50.48%', samePeriod: '16.81%', industryAvg: '30.12%', trend: 'up' },
    { label: '营业利润率', value: '21.51%', samePeriod: '74.17%', industryAvg: '31.37%', trend: 'down' },
    { label: '净利润率', value: '44.86%', samePeriod: '53.67%', industryAvg: '28.66%', trend: 'up' },
  ];

  radarAxes = ['总资产报酬率', '净资产收益率', '盈余现金保障倍数', 'EBITDA利润率', '成本费用利润率', '毛利率', '营业利润率', '净利润率'];
  radarLevels = [20, 40, 60, 80, 100];
  radarSeries: RadarSeries[] = [
    { label: '内部组织', color: '#1d78d6', values: [28, 76, 65, 81, 53, 50, 22, 45] },
    { label: '外部组织', color: '#51c9c3', values: [86, 36, 83, 57, 18, 60, 37, 77] },
    { label: '行业均值', color: '#a8a2ea', values: [61, 80, 39, 88, 64, 30, 31, 29] },
  ];

  months = ['2024-09', '2024-10', '2024-11', '2024-12', '2025-01', '2025-02'];
  yTicks = [0, 20, 40, 60, 80, 100];
  metrics: ProfitMetric[] = [
    {
      key: 'roa',
      label: '总资产报酬率',
      current: '27.61%',
      samePeriod: '53.86%',
      industryAvg: '61.37%',
      trend: 'down',
      series: [
        { label: '内部组织', color: '#1d78d6', values: [32, 14, 58, 68, 84, 62] },
        { label: '外部组织', color: '#51c9c3', values: [70, 12, 78, 55, 17, 28] },
        { label: '行业均值', color: '#a8a2ea', values: [70, 72, 88, 35, 90, 86] },
      ],
    },
    {
      key: 'roe',
      label: '净资产收益率',
      current: '75.80%',
      samePeriod: '50.42%',
      industryAvg: '79.53%',
      trend: 'up',
      series: [
        { label: '内部组织', color: '#1d78d6', values: [56, 61, 64, 70, 74, 76] },
        { label: '外部组织', color: '#51c9c3', values: [42, 48, 44, 57, 62, 59] },
        { label: '行业均值', color: '#a8a2ea', values: [72, 76, 78, 81, 80, 80] },
      ],
    },
    {
      key: 'netMargin',
      label: '净利润率',
      current: '44.86%',
      samePeriod: '53.67%',
      industryAvg: '28.66%',
      trend: 'down',
      series: [
        { label: '内部组织', color: '#1d78d6', values: [52, 48, 55, 47, 50, 45] },
        { label: '外部组织', color: '#51c9c3', values: [68, 62, 58, 60, 54, 77] },
        { label: '行业均值', color: '#a8a2ea', values: [26, 28, 29, 27, 30, 29] },
      ],
    },
  ];

  rows: ProfitabilityRow[] = [
    { category: '内部组织', org: 'XXX集团', roa: '27.61%', roe: '75.80%', cashCover: '65.46%', ebitda: '80.57%', costProfit: '52.77%', grossMargin: '50.48%', operatingMargin: '21.51%', netMargin: '44.86%' },
    { category: '外部组织', org: 'X公司', roa: '86.50%', roe: '36.19%', cashCover: '82.75%', ebitda: '56.68%', costProfit: '17.65%', grossMargin: '60.09%', operatingMargin: '37.03%', netMargin: '76.64%' },
    { category: '行业均值', org: '/', roa: '61.37%', roe: '79.53%', cashCover: '38.85%', ebitda: '88.18%', costProfit: '64.39%', grossMargin: '30.12%', operatingMargin: '31.37%', netMargin: '28.66%' },
  ];

  get selectedMetric(): ProfitMetric {
    return this.metrics.find(metric => metric.key === this.selectedMetricKey) ?? this.metrics[0];
  }

  trendArrow(trend: Trend): string {
    return trend === 'up' ? '▲' : '▼';
  }

  trendClass(trend: Trend): string {
    return `trend-${trend}`;
  }

  radarPoint(index: number, value: number): { x: number; y: number } {
    const angle = (Math.PI * 2 * index) / this.radarAxes.length - Math.PI / 2;
    const radius = 138 * (value / 100);
    return {
      x: 260 + Math.cos(angle) * radius,
      y: 178 + Math.sin(angle) * radius,
    };
  }

  radarPolygon(level: number): string {
    return this.radarAxes.map((_, index) => {
      const point = this.radarPoint(index, level);
      return `${point.x},${point.y}`;
    }).join(' ');
  }

  radarPolygonPoints(values: number[]): string {
    return values.map((value, index) => {
      const point = this.radarPoint(index, value);
      return `${point.x},${point.y}`;
    }).join(' ');
  }

  chartX(index: number): number {
    return 50 + index * 108;
  }

  chartY(value: number): number {
    return 252 - value * 2.08;
  }

  linePath(values: number[]): string {
    return values.map((value, index) => `${index === 0 ? 'M' : 'L'} ${this.chartX(index)} ${this.chartY(value)}`).join(' ');
  }

  indexValue(index: number, value: number): string {
    return `${index}-${value}`;
  }
}
