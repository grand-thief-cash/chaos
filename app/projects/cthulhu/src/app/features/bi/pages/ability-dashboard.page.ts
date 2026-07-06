import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

type Trend = 'up' | 'down';
type AbilityKind = 'operation' | 'solvency';

interface AbilityKpi {
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

interface AbilityMetric {
  key: string;
  label: string;
  current: string;
  samePeriod: string;
  industryAvg: string;
  trend: Trend;
  series: TrendSeries[];
}

interface DetailRow {
  category: string;
  org: string;
  values: string[];
}

interface ExplainBlock {
  title: string;
  lines: string[];
}

interface AbilityConfig {
  title: string;
  updatedAt: string;
  radarTitle: string;
  trendTitle: string;
  tableTitle: string;
  columns: string[];
  organizations: string[];
  kpis: AbilityKpi[];
  radarAxes: string[];
  radarSeries: RadarSeries[];
  metrics: AbilityMetric[];
  rows: DetailRow[];
  explain: ExplainBlock[];
}

@Component({
  selector: 'app-bi-ability-dashboard-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="ability-page">
      <header class="page-header">
        <div>
          <h1>{{ config.title }}</h1>
          <span>更新日期：{{ config.updatedAt }}</span>
        </div>
        <div class="filters">
          <label>
            <span>年月</span>
            <input type="month" [(ngModel)]="selectedMonth" />
          </label>
          <label>
            <span>公司名称</span>
            <select [(ngModel)]="selectedOrg">
              @for (org of config.organizations; track org) {
                <option [value]="org">{{ org }}</option>
              }
            </select>
          </label>
          <label>
            <span>对标公司</span>
            <select [(ngModel)]="selectedBenchmark">
              @for (benchmark of benchmarks; track benchmark) {
                <option [value]="benchmark">{{ benchmark }}</option>
              }
            </select>
          </label>
        </div>
      </header>

      <section class="kpi-grid" aria-label="核心指标">
        @for (kpi of config.kpis; track kpi.label) {
          <article class="kpi-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
            <div class="kpi-meta">
              <em>同期：{{ kpi.samePeriod }}</em>
              <em>业内平均：{{ kpi.industryAvg }}</em>
              <b [class]="trendClass(kpi.trend)">{{ trendArrow(kpi.trend) }}</b>
            </div>
          </article>
        }
      </section>

      <section class="analysis-grid">
        <article class="panel radar-panel">
          <header>
            <h2>{{ config.radarTitle }}</h2>
            <span>公司 / 对标公司 / 行业均值</span>
          </header>
          <div class="radar-layout">
            <svg class="radar-chart" viewBox="0 0 540 360" role="img">
              @for (level of radarLevels; track level) {
                <polygon class="radar-ring" [attr.points]="radarPolygon(level)"></polygon>
              }
              @for (axis of config.radarAxes; track axis; let index = $index) {
                <line class="radar-axis" x1="270" y1="180" [attr.x2]="radarPoint(index, 100).x" [attr.y2]="radarPoint(index, 100).y"></line>
                <text class="radar-label" [attr.x]="radarPoint(index, 118).x" [attr.y]="radarPoint(index, 118).y">{{ axis }}</text>
              }
              @for (series of config.radarSeries; track series.label) {
                <polygon class="radar-series" [attr.points]="radarPolygonPoints(series.values)" [attr.stroke]="series.color" [attr.fill]="series.color"></polygon>
              }
            </svg>
            <div class="legend vertical">
              @for (series of config.radarSeries; track series.label) {
                <span><i [style.background]="series.color"></i>{{ series.label }}</span>
              }
            </div>
          </div>
        </article>

        <article class="panel trend-panel">
          <header>
            <h2>{{ config.trendTitle }}</h2>
            <label>
              <span>指标筛选</span>
              <select [(ngModel)]="selectedMetricKey">
                @for (metric of config.metrics; track metric.key) {
                  <option [value]="metric.key">{{ metric.label }}</option>
                }
              </select>
            </label>
          </header>
          <div class="trend-summary">
            <strong>{{ selectedMetric.current }}</strong>
            <span>{{ selectedMetric.label }}</span>
            <span>同期：{{ selectedMetric.samePeriod }}</span>
            <span>业内平均：{{ selectedMetric.industryAvg }}</span>
            <b [class]="trendClass(selectedMetric.trend)">{{ trendArrow(selectedMetric.trend) }}</b>
          </div>
          <svg class="line-chart" viewBox="0 0 640 300" role="img">
            @for (tick of yTicks; track tick) {
              <line class="grid-line" x1="46" [attr.y1]="chartY(tick)" x2="606" [attr.y2]="chartY(tick)"></line>
              <text class="y-label" x="18" [attr.y]="chartY(tick) + 4">{{ tick }}%</text>
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
            <h2>{{ config.tableTitle }}</h2>
            <span>本期值、同期值和行业均值用于后续真实数据口径校验</span>
          </header>
          <table>
            <thead>
              <tr>
                <th>数据分类</th>
                <th>组织名称</th>
                @for (column of config.columns; track column) {
                  <th>{{ column }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of config.rows; track row.category + row.org) {
                <tr>
                  <td>{{ row.category }}</td>
                  <td>{{ row.org }}</td>
                  @for (value of row.values; track indexValue(index, value); let index = $index) {
                    <td>{{ value }}</td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </article>
      </section>

      <section class="explain-panel" [attr.aria-label]="config.title + '说明'">
        @for (block of config.explain; track block.title) {
          <article>
            <h2>{{ block.title }}</h2>
            @if (block.lines.length === 1) {
              <p>{{ block.lines[0] }}</p>
            } @else {
              <ul>
                @for (line of block.lines; track line) {
                  <li>{{ line }}</li>
                }
              </ul>
            }
          </article>
        }
      </section>
    </section>
  `,
  styles: [`
    :host { display: block; min-height: calc(100vh - 110px); background: #eef4fb; color: #172033; font-size: 14px; }
    .ability-page { display: flex; flex-direction: column; gap: 16px; }
    .page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; padding: 18px 22px; background: linear-gradient(100deg, #1f68d8 0%, #48a0eb 54%, #d9efe9 100%); color: #fff; }
    h1, h2 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 30px; line-height: 1.2; }
    .filters { display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
    label { display: flex; align-items: center; gap: 8px; font-weight: 650; }
    select, input { height: 34px; min-width: 136px; border: 1px solid rgba(34, 72, 112, 0.28); border-radius: 4px; background: rgba(255, 255, 255, 0.68); color: #172033; padding: 0 10px; font-size: 14px; font-weight: 620; }
    .kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 12px; }
    .kpi-card, .panel, .explain-panel { background: #fff; border: 1px solid #dce7f2; }
    .kpi-card { padding: 16px; min-height: 132px; }
    .kpi-card span, .panel header span, .trend-summary span, .page-header span { color: #657386; font-size: 13px; line-height: 1.45; }
    .page-header span { color: #fff; font-weight: 650; }
    .kpi-card strong { display: block; margin: 12px 0; color: #116ecf; font-size: 32px; line-height: 1; }
    .kpi-meta { display: grid; grid-template-columns: 1fr 1fr auto; gap: 8px; align-items: center; font-size: 14px; line-height: 1.4; }
    .kpi-meta em { font-style: normal; font-weight: 650; }
    .trend-up { color: #19a45f; }
    .trend-down { color: #e84f63; }
    .analysis-grid { display: grid; grid-template-columns: 1fr 1.05fr; gap: 12px; }
    .panel { min-height: 360px; padding: 16px; }
    .panel header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 12px; }
    h2 { font-size: 18px; line-height: 1.25; }
    .radar-layout { display: grid; grid-template-columns: minmax(0, 1fr) 120px; gap: 12px; align-items: center; }
    .radar-chart, .line-chart { width: 100%; height: 300px; }
    .radar-ring { fill: none; stroke: #dce5ef; stroke-width: 1; }
    .radar-axis, .grid-line { stroke: #e6edf5; stroke-width: 1; }
    .radar-label, .x-label, .y-label { fill: #657386; font-size: 13px; text-anchor: middle; }
    .radar-series { fill-opacity: 0.1; stroke-width: 3; }
    .trend-summary { display: flex; gap: 16px; align-items: center; padding: 10px 12px; margin-bottom: 8px; background: #f7fbff; border: 1px solid #e1ebf6; }
    .trend-summary strong { color: #116ecf; font-size: 24px; }
    .line-path { fill: none; stroke-width: 3; }
    .line-dot { stroke: #fff; stroke-width: 2; }
    .legend { display: flex; gap: 16px; color: #657386; font-size: 13px; line-height: 1.45; }
    .legend.vertical { flex-direction: column; }
    .legend i { display: inline-block; width: 10px; height: 10px; margin-right: 6px; vertical-align: -1px; }
    .table-panel { grid-column: 1 / -1; min-height: auto; overflow: auto; }
    table { width: 100%; min-width: 1160px; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 12px 10px; border: 1px solid #e5edf6; text-align: center; white-space: nowrap; }
    th { background: #c9e2fb; color: #17304d; font-weight: 720; }
    .explain-panel { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; padding: 16px; }
    .explain-panel article { padding: 12px 14px; background: #f8fbff; border: 1px solid #e5edf6; }
    .explain-panel h2 { margin-bottom: 8px; font-size: 17px; color: #17304d; }
    .explain-panel p, .explain-panel li { margin: 0; color: #506176; font-size: 14px; line-height: 1.7; }
    .explain-panel ul { margin: 0; padding-left: 18px; }
    @media (max-width: 1200px) { .page-header { align-items: flex-start; flex-direction: column; } .filters { justify-content: flex-start; } .kpi-grid { grid-template-columns: repeat(2, minmax(180px, 1fr)); } .analysis-grid, .explain-panel { grid-template-columns: 1fr; } }
    @media (max-width: 720px) { .kpi-grid, .radar-layout { grid-template-columns: 1fr; } .panel header, .trend-summary { align-items: flex-start; flex-direction: column; } label, select, input { width: 100%; } }
  `],
})
export class AbilityDashboardPageComponent {
  readonly months = ['2023-11', '2023-12', '2024-01', '2024-02', '2024-03', '2024-04'];
  readonly yTicks = [0, 25, 50, 75, 100, 125, 150];
  readonly radarLevels = [20, 40, 60, 80, 100];
  readonly benchmarks = ['Z公司', '行业均值', '集团预算'];

  selectedMonth = '2024-04';
  selectedOrg = 'XXX集团';
  selectedBenchmark = 'Z公司';
  selectedMetricKey = '';
  config: AbilityConfig = ABILITY_CONFIGS.operation;

  constructor(private route: ActivatedRoute) {
    this.route.data.subscribe(data => {
      const kind = (data['abilityKind'] as AbilityKind) || 'operation';
      this.config = ABILITY_CONFIGS[kind];
      this.selectedOrg = this.config.organizations[0];
      this.selectedMetricKey = this.config.metrics[0].key;
    });
  }

  get selectedMetric(): AbilityMetric {
    return this.config.metrics.find(metric => metric.key === this.selectedMetricKey) ?? this.config.metrics[0];
  }

  trendArrow(trend: Trend): string {
    return trend === 'up' ? '▲' : '▼';
  }

  trendClass(trend: Trend): string {
    return `trend-${trend}`;
  }

  radarPoint(index: number, value: number): { x: number; y: number } {
    const angle = (Math.PI * 2 * index) / this.config.radarAxes.length - Math.PI / 2;
    const radius = 134 * (value / 100);
    return { x: 270 + Math.cos(angle) * radius, y: 180 + Math.sin(angle) * radius };
  }

  radarPolygon(level: number): string {
    return this.config.radarAxes.map((_, index) => {
      const point = this.radarPoint(index, level);
      return `${point.x},${point.y}`;
    }).join(' ');
  }

  radarPolygonPoints(values: number[]): string {
    return values.map((value, index) => {
      const point = this.radarPoint(index, Math.min(value, 100));
      return `${point.x},${point.y}`;
    }).join(' ');
  }

  chartX(index: number): number {
    return 58 + index * 108;
  }

  chartY(value: number): number {
    return 252 - value * 1.42;
  }

  linePath(values: number[]): string {
    return values.map((value, index) => `${index === 0 ? 'M' : 'L'} ${this.chartX(index)} ${this.chartY(value)}`).join(' ');
  }

  indexValue(index: number, value: string | number): string {
    return `${index}-${value}`;
  }
}

const ABILITY_CONFIGS: Record<AbilityKind, AbilityConfig> = {
  operation: {
    title: '营运能力分析',
    updatedAt: '2025年1月21日',
    radarTitle: '关键营运能力指标对标',
    trendTitle: '营运能力指标变动趋势',
    tableTitle: '各项营运能力指标明细',
    columns: ['总资产周转率', '应收账款周转率', '存货周转率', '营业周期', '流动资产周转率', '固定资产周转率', '净资产周转率', '资产现金回收率'],
    organizations: ['XXX集团', 'Z公司', 'X公司', 'W公司'],
    kpis: [
      { label: '总资产周转率', value: '31.18%', samePeriod: '10.39%', industryAvg: '55.86%', trend: 'up' },
      { label: '应收账款周转率', value: '60.92%', samePeriod: '21.92%', industryAvg: '36.37%', trend: 'up' },
      { label: '存货周转率', value: '25.72%', samePeriod: '86.43%', industryAvg: '54.47%', trend: 'down' },
      { label: '营业周期', value: '10.32%', samePeriod: '31.74%', industryAvg: '43.65%', trend: 'down' },
      { label: '流动资产周转率', value: '17.54%', samePeriod: '22.91%', industryAvg: '49.73%', trend: 'down' },
      { label: '固定资产周转率', value: '34.50%', samePeriod: '69.20%', industryAvg: '86.62%', trend: 'down' },
      { label: '净资产周转率', value: '49.78%', samePeriod: '46.16%', industryAvg: '15.77%', trend: 'up' },
      { label: '资产现金回收率', value: '58.12%', samePeriod: '71.86%', industryAvg: '53.00%', trend: 'down' },
    ],
    radarAxes: ['总资产周转率', '应收账款周转率', '存货周转率', '营业周期', '流动资产周转率', '固定资产周转率', '净资产周转率', '资产现金回收率'],
    radarSeries: [
      { label: 'XXX集团', color: '#1d78d6', values: [31, 61, 26, 10, 18, 35, 50, 58] },
      { label: 'Z公司', color: '#51c9c3', values: [70, 58, 62, 45, 54, 68, 47, 74] },
      { label: '行业均值', color: '#a8a2ea', values: [56, 36, 54, 44, 50, 87, 16, 53] },
    ],
    metrics: [
      {
        key: 'assetTurnover',
        label: '总资产周转率',
        current: '31.18%',
        samePeriod: '10.39%',
        industryAvg: '55.86%',
        trend: 'up',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [34, 53, 36, 92, 11, 76] },
          { label: 'Z公司', color: '#51c9c3', values: [24, 53, 73, 51, 71, 75] },
          { label: '行业均值', color: '#a8a2ea', values: [68, 76, 62, 88, 20, 28] },
        ],
      },
      {
        key: 'receivableTurnover',
        label: '应收账款周转率',
        current: '60.92%',
        samePeriod: '21.92%',
        industryAvg: '36.37%',
        trend: 'up',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [22, 31, 44, 55, 58, 61] },
          { label: 'Z公司', color: '#51c9c3', values: [43, 48, 52, 50, 55, 58] },
          { label: '行业均值', color: '#a8a2ea', values: [35, 37, 36, 38, 37, 36] },
        ],
      },
      {
        key: 'inventoryTurnover',
        label: '存货周转率',
        current: '25.72%',
        samePeriod: '86.43%',
        industryAvg: '54.47%',
        trend: 'down',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [86, 72, 64, 48, 32, 26] },
          { label: 'Z公司', color: '#51c9c3', values: [62, 60, 57, 56, 55, 54] },
          { label: '行业均值', color: '#a8a2ea', values: [52, 54, 55, 54, 56, 54] },
        ],
      },
    ],
    rows: [
      { category: '内部组织', org: 'XXX集团', values: ['31.18%', '60.92%', '25.72%', '10.32%', '17.54%', '34.50%', '49.78%', '58.12%'] },
      { category: '外部组织', org: 'Z公司', values: ['70.45%', '58.33%', '61.74%', '44.20%', '53.90%', '68.42%', '47.30%', '74.12%'] },
      { category: '外部组织', org: 'X公司', values: ['42.15%', '46.20%', '39.44%', '36.72%', '44.18%', '58.64%', '41.91%', '63.77%'] },
      { category: '行业均值', org: '/', values: ['55.86%', '36.37%', '54.47%', '43.65%', '49.73%', '86.62%', '15.77%', '53.00%'] },
    ],
    explain: [
      { title: '使用场景', lines: ['适用于财务分析、运营效率优化和经营复盘，帮助企业观察资产、应收账款、存货和现金回收效率。'] },
      { title: '业务价值', lines: ['通过周转率、营业周期和资产现金回收指标识别运营效率短板，支持库存管理、信用政策和资产配置优化。'] },
      { title: '模块说明', lines: ['总资产周转率、流动资产周转率、固定资产周转率用于衡量资产使用效率。', '应收账款周转率和资产现金回收率用于观察回款能力和现金回收质量。', '存货周转率和营业周期用于判断库存周转效率和供应链效率。'] },
      { title: '使用条件', lines: ['当前为静态 mock 数据版本；后续接入真实数据时，需要提供本期、同期、对标公司和行业均值等同口径数据。'] },
    ],
  },
  solvency: {
    title: '偿债能力分析',
    updatedAt: '2025年1月20日',
    radarTitle: '关键偿债能力指标对标',
    trendTitle: '偿债指标变动趋势分析',
    tableTitle: '各项偿债能力指标明细',
    columns: ['流动比率', '速动比率', '现金比率', '现金流动负债率', '资产负债率', '产权比率', '利息保障倍数', '带息负债率'],
    organizations: ['XXX集团', 'Z公司', 'X公司', 'W公司'],
    kpis: [
      { label: '流动比率', value: '183.42%', samePeriod: '156.30%', industryAvg: '142.80%', trend: 'up' },
      { label: '速动比率', value: '126.71%', samePeriod: '118.44%', industryAvg: '110.35%', trend: 'up' },
      { label: '现金比率', value: '48.52%', samePeriod: '42.16%', industryAvg: '36.90%', trend: 'up' },
      { label: '现金流动负债率', value: '61.38%', samePeriod: '54.72%', industryAvg: '45.66%', trend: 'up' },
      { label: '资产负债率', value: '38.64%', samePeriod: '42.88%', industryAvg: '51.20%', trend: 'down' },
      { label: '有形净值负债率', value: '72.45%', samePeriod: '81.36%', industryAvg: '96.14%', trend: 'down' },
      { label: '产权比率', value: '64.18%', samePeriod: '74.63%', industryAvg: '92.50%', trend: 'down' },
      { label: '利息保障倍数', value: '8.72', samePeriod: '6.45', industryAvg: '5.18', trend: 'up' },
    ],
    radarAxes: ['流动比率', '速动比率', '现金比率', '现金流动负债率', '资产负债率', '产权比率', '利息保障倍数', '带息负债率'],
    radarSeries: [
      { label: 'XXX集团', color: '#1d78d6', values: [92, 82, 70, 74, 39, 64, 88, 32] },
      { label: 'Z公司', color: '#51c9c3', values: [75, 68, 51, 56, 58, 86, 62, 48] },
      { label: '行业均值', color: '#a8a2ea', values: [71, 63, 47, 50, 51, 93, 55, 45] },
    ],
    metrics: [
      {
        key: 'currentRatio',
        label: '流动比率',
        current: '183.42%',
        samePeriod: '156.30%',
        industryAvg: '142.80%',
        trend: 'up',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [132, 144, 156, 168, 176, 183] },
          { label: 'Z公司', color: '#51c9c3', values: [116, 123, 130, 136, 142, 148] },
          { label: '行业均值', color: '#a8a2ea', values: [136, 138, 140, 141, 143, 143] },
        ],
      },
      {
        key: 'assetLiabilityRatio',
        label: '资产负债率',
        current: '38.64%',
        samePeriod: '42.88%',
        industryAvg: '51.20%',
        trend: 'down',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [48, 46, 44, 42, 40, 39] },
          { label: 'Z公司', color: '#51c9c3', values: [54, 56, 55, 57, 58, 58] },
          { label: '行业均值', color: '#a8a2ea', values: [51, 52, 51, 51, 52, 51] },
        ],
      },
      {
        key: 'interestCoverage',
        label: '利息保障倍数',
        current: '8.72',
        samePeriod: '6.45',
        industryAvg: '5.18',
        trend: 'up',
        series: [
          { label: 'XXX集团', color: '#1d78d6', values: [58, 63, 66, 72, 81, 87] },
          { label: 'Z公司', color: '#51c9c3', values: [45, 48, 52, 54, 57, 62] },
          { label: '行业均值', color: '#a8a2ea', values: [49, 50, 51, 52, 52, 52] },
        ],
      },
    ],
    rows: [
      { category: '内部组织', org: 'XXX集团', values: ['183.42%', '126.71%', '48.52%', '61.38%', '38.64%', '64.18%', '8.72', '32.48%'] },
      { category: '外部组织', org: 'Z公司', values: ['148.60%', '112.34%', '41.20%', '52.16%', '58.44%', '86.77%', '6.21', '48.13%'] },
      { category: '外部组织', org: 'X公司', values: ['121.76%', '94.68%', '33.14%', '45.60%', '63.28%', '102.45%', '4.92', '55.72%'] },
      { category: '行业均值', org: '/', values: ['142.80%', '110.35%', '36.90%', '45.66%', '51.20%', '92.50%', '5.18', '45.30%'] },
    ],
    explain: [
      { title: '使用场景', lines: ['适用于财务健康度监控、融资风险评估和债务结构复盘，帮助管理层判断短期与长期偿债压力。'] },
      { title: '业务价值', lines: ['通过流动性、杠杆水平和利息保障指标识别偿债风险，支持资本结构优化、融资计划和风险预警。'] },
      { title: '模块说明', lines: ['流动比率、速动比率、现金比率用于衡量短期偿债能力。', '现金流动负债率用于评估经营现金流对短期债务的覆盖程度。', '资产负债率、产权比率和带息负债率用于观察杠杆水平和长期偿债风险。', '利息保障倍数用于判断利润对利息支出的覆盖能力。'] },
      { title: '使用条件', lines: ['当前为静态 mock 数据版本；后续接入真实数据时，需要统一资产、负债、现金流和利息费用等指标口径。'] },
    ],
  },
};
