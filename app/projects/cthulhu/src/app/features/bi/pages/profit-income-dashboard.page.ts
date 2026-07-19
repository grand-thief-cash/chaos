import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink, RouterLinkActive } from '@angular/router';

type Trend = 'up' | 'down' | 'flat';
type ProfitIncomeKind = 'summary' | 'profitComparison' | 'revenue';
type Tone = 'blue' | 'cyan' | 'green' | 'gold' | 'red' | 'slate';

interface Delta {
  label: string;
  value: string;
  trend: Trend;
}

interface Kpi {
  label: string;
  value: string;
  deltas: Delta[];
}

interface CompareBar {
  label: string;
  value: string;
  height: number;
  tone: Tone;
}

interface CompareRow {
  name: string;
  bars: CompareBar[];
  note: string;
}

interface TrendSeries {
  label: string;
  color: string;
  points: number[];
}

interface Metric {
  key: string;
  label: string;
  current: string;
  samePeriod: string;
  yoy: string;
  trend: Trend;
  series: TrendSeries[];
}

interface FlowStep {
  label: string;
  value: string;
  sign: '+' | '-' | '=';
  width: number;
  tone: Tone;
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

interface ProfitIncomeConfig {
  title: string;
  subtitle: string;
  updatedAt: string;
  compareTitle: string;
  trendTitle: string;
  flowTitle: string;
  tableTitle: string;
  organizations: string[];
  compareLegends: { label: string; tone: Tone }[];
  kpis: Kpi[];
  compareRows: CompareRow[];
  metrics: Metric[];
  flowSteps: FlowStep[];
  tableColumns: string[];
  tableRows: DetailRow[];
  explain: ExplainBlock[];
}

@Component({
  selector: 'app-bi-profit-income-dashboard-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  template: `
    <section class="profit-income-page">
      <header class="page-header">
        <div>
          <h1>{{ config.title }}</h1>
          <span>{{ config.subtitle }} · 更新日期：{{ config.updatedAt }}</span>
        </div>
        <div class="filters">
          <label>
            <span>组织</span>
            <select [(ngModel)]="selectedOrg">
              @for (org of config.organizations; track org) {
                <option [value]="org">{{ org }}</option>
              }
            </select>
          </label>
          <label>
            <span>年月</span>
            <input type="month" [(ngModel)]="selectedMonth" />
          </label>
          <label>
            <span>口径</span>
            <select [(ngModel)]="selectedScope">
              @for (scope of scopes; track scope) {
                <option [value]="scope">{{ scope }}</option>
              }
            </select>
          </label>
        </div>
      </header>

      <nav class="local-tabs" aria-label="利润收入分析页签">
        @for (tab of tabs; track tab.path) {
          <a [routerLink]="tab.path" routerLinkActive="active">{{ tab.label }}</a>
        }
      </nav>

      <section class="kpi-grid" aria-label="利润收入核心指标">
        @for (kpi of config.kpis; track kpi.label) {
          <article class="kpi-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
            <div class="delta-list">
              @for (delta of kpi.deltas; track delta.label) {
                <em [class]="trendClass(delta.trend)">
                  {{ delta.label }} {{ trendArrow(delta.trend) }} {{ delta.value }}
                </em>
              }
            </div>
          </article>
        }
      </section>

      <section class="dashboard-grid">
        <article class="panel compare-panel">
          <header>
            <h2>{{ config.compareTitle }}</h2>
            <span>本期值 / 同期值 / 同比变化</span>
          </header>
          <div class="compare-chart" aria-label="组织指标对比">
            @for (row of config.compareRows; track row.name) {
              <div class="compare-item">
                <div class="compare-bars">
                  @for (bar of row.bars; track bar.label) {
                    <i [class]="bar.tone" [style.height.%]="bar.height" [title]="bar.label + '：' + bar.value"></i>
                  }
                </div>
                <strong>{{ row.name }}</strong>
                <span>{{ row.note }}</span>
              </div>
            }
          </div>
          <div class="legend">
            @for (legend of config.compareLegends; track legend.label) {
              <span><i [class]="legend.tone"></i>{{ legend.label }}</span>
            }
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
          <div class="metric-summary">
            <strong>{{ selectedMetric.current }}</strong>
            <span>{{ selectedMetric.label }}</span>
            <span>同期值：{{ selectedMetric.samePeriod }}</span>
            <b [class]="trendClass(selectedMetric.trend)">同比 {{ trendArrow(selectedMetric.trend) }} {{ selectedMetric.yoy }}</b>
          </div>
          <svg class="line-chart" viewBox="0 0 640 290" role="img" aria-label="利润收入指标趋势">
            @for (tick of yTicks; track tick) {
              <line class="grid-line" x1="46" [attr.y1]="chartY(tick)" x2="604" [attr.y2]="chartY(tick)"></line>
              <text class="y-label" x="20" [attr.y]="chartY(tick) + 4">{{ tick }}%</text>
            }
            @for (month of months; track month; let index = $index) {
              <text class="x-label" [attr.x]="chartX(index)" y="274">{{ month }}</text>
            }
            @for (series of selectedMetric.series; track series.label) {
              <path class="line-path" [attr.d]="linePath(series.points)" [attr.stroke]="series.color"></path>
              @for (point of series.points; track indexValue(index, point); let index = $index) {
                <circle class="line-dot" r="4" [attr.cx]="chartX(index)" [attr.cy]="chartY(point)" [attr.fill]="series.color"></circle>
              }
            }
          </svg>
          <div class="legend">
            @for (series of selectedMetric.series; track series.label) {
              <span><i [style.background]="series.color"></i>{{ series.label }}</span>
            }
          </div>
        </article>

        <article class="panel flow-panel">
          <header>
            <h2>{{ config.flowTitle }}</h2>
            <span>保留收入、成本、费用到利润的关系</span>
          </header>
          <div class="flow-list" aria-label="收入利润构成关系">
            @for (step of config.flowSteps; track step.label) {
              <div class="flow-row">
                <b [class]="step.sign === '-' ? 'minus' : step.sign === '=' ? 'equal' : 'plus'">{{ step.sign }}</b>
                <span>{{ step.label }}</span>
                <div class="flow-track"><i [class]="step.tone" [style.width.%]="step.width"></i></div>
                <strong>{{ step.value }}</strong>
              </div>
            }
          </div>
        </article>

        <article class="panel table-panel">
          <header>
            <h2>{{ config.tableTitle }}</h2>
            <span>Mock 数据，后续接入真实数据时按有数据的层级展示</span>
          </header>
          <table>
            <thead>
              <tr>
                <th>数据分类</th>
                <th>组织名称</th>
                @for (column of config.tableColumns; track column) {
                  <th>{{ column }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of config.tableRows; track row.category + row.org) {
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
    .profit-income-page { display: flex; flex-direction: column; gap: 14px; }
    .page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; padding: 18px 22px; background: linear-gradient(100deg, #1f68d8 0%, #45a2ed 56%, #d8eee6 100%); color: #fff; }
    h1, h2 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 30px; line-height: 1.2; }
    .page-header span { font-weight: 650; }
    .filters, .local-tabs, .legend { display: flex; gap: 12px; flex-wrap: wrap; }
    .filters { justify-content: flex-end; }
    label { display: flex; align-items: center; gap: 8px; font-weight: 650; }
    select, input { height: 34px; min-width: 132px; border: 1px solid rgba(34, 72, 112, 0.28); border-radius: 4px; background: rgba(255, 255, 255, 0.7); color: #172033; padding: 0 10px; font-size: 14px; font-weight: 620; }
    .local-tabs { padding: 10px 12px; background: #fff; border: 1px solid #dce7f2; }
    .local-tabs a { min-width: 120px; padding: 8px 12px; border-bottom: 3px solid transparent; color: #506176; text-align: center; text-decoration: none; font-weight: 720; }
    .local-tabs a.active { color: #126fcc; border-color: #126fcc; background: #f3f8ff; }
    .kpi-grid { display: grid; grid-template-columns: repeat(6, minmax(145px, 1fr)); gap: 12px; }
    .kpi-card, .panel, .explain-panel { background: #fff; border: 1px solid #dce7f2; }
    .kpi-card { padding: 14px; min-height: 126px; border-left: 4px solid #2588ef; }
    .kpi-card span, .panel header span, .compare-item span, .metric-summary span { color: #657386; font-size: 13px; line-height: 1.45; }
    .kpi-card strong { display: block; margin: 10px 0; color: #116ecf; font-size: 26px; line-height: 1; white-space: nowrap; }
    .delta-list { display: grid; gap: 4px; }
    .delta-list em { font-style: normal; font-size: 14px; font-weight: 720; }
    .trend-up { color: #e84f63; }
    .trend-down { color: #18a05e; }
    .trend-flat { color: #f0a532; }
    .dashboard-grid { display: grid; grid-template-columns: 1fr 1.05fr; gap: 12px; }
    .panel { min-height: 330px; padding: 16px; overflow: hidden; }
    .panel header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 12px; }
    h2 { font-size: 18px; line-height: 1.25; }
    .compare-chart { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; height: 230px; align-items: end; border-bottom: 1px solid #dce6f2; padding-top: 10px; }
    .compare-item { display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; min-width: 0; text-align: center; }
    .compare-item strong { font-size: 15px; }
    .compare-bars { display: flex; align-items: end; justify-content: center; gap: 6px; height: 150px; width: 72px; }
    .compare-bars i { width: 14px; min-height: 8px; }
    .metric-summary { display: flex; gap: 14px; align-items: center; padding: 10px 12px; margin-bottom: 8px; background: #f7fbff; border: 1px solid #e1ebf6; }
    .metric-summary strong { color: #116ecf; font-size: 24px; }
    .line-chart { width: 100%; height: 290px; }
    .grid-line { stroke: #e6edf5; stroke-width: 1; }
    .line-path { fill: none; stroke-width: 3; }
    .line-dot { stroke: #fff; stroke-width: 2; }
    .x-label, .y-label { fill: #657386; font-size: 13px; text-anchor: middle; }
    .legend { margin-top: 12px; color: #657386; font-size: 13px; line-height: 1.45; }
    .legend i { display: inline-block; width: 10px; height: 10px; margin-right: 6px; vertical-align: -1px; }
    .flow-panel { grid-column: 1 / -1; min-height: auto; }
    .flow-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
    .flow-row { display: grid; grid-template-columns: 28px 112px 1fr 82px; gap: 10px; align-items: center; min-height: 42px; font-size: 14px; }
    .flow-row b { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: #fff; }
    .flow-row .plus { background: #e84f63; }
    .flow-row .minus { background: #18a05e; }
    .flow-row .equal { background: #2588ef; }
    .flow-track { height: 10px; background: #edf3fb; }
    .flow-track i { display: block; height: 100%; }
    .blue { background: #2588ef; }
    .cyan { background: #49bdd6; }
    .green { background: #18a05e; }
    .gold { background: #f0a532; }
    .red { background: #e84f63; }
    .slate { background: #708199; }
    .table-panel { grid-column: 1 / -1; min-height: auto; overflow: auto; }
    table { width: 100%; min-width: 1080px; border-collapse: collapse; font-size: 14px; }
    th, td { padding: 11px 10px; border: 1px solid #e5edf6; text-align: center; white-space: nowrap; }
    th { background: #c9e2fb; color: #17304d; font-weight: 720; }
    .explain-panel { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; padding: 16px; }
    .explain-panel article { padding: 12px 14px; background: #f8fbff; border: 1px solid #e5edf6; }
    .explain-panel h2 { margin-bottom: 8px; font-size: 17px; color: #17304d; }
    .explain-panel p, .explain-panel li { margin: 0; color: #506176; font-size: 14px; line-height: 1.7; }
    .explain-panel ul { margin: 0; padding-left: 18px; }
    @media (max-width: 1200px) { .page-header { align-items: flex-start; flex-direction: column; } .filters { justify-content: flex-start; } .kpi-grid { grid-template-columns: repeat(3, minmax(145px, 1fr)); } .dashboard-grid, .explain-panel { grid-template-columns: 1fr; } .flow-list { grid-template-columns: 1fr; } }
    @media (max-width: 720px) { .kpi-grid, .compare-chart { grid-template-columns: repeat(2, minmax(0, 1fr)); } .compare-chart { height: auto; min-height: 260px; } .panel header, .metric-summary { align-items: flex-start; flex-direction: column; } .flow-row { grid-template-columns: 28px 1fr; } .flow-track, .flow-row strong { grid-column: 2; } label, select, input { width: 100%; } }
  `],
})
export class ProfitIncomeDashboardPageComponent {
  readonly months = ['2023-09', '2023-10', '2023-11', '2023-12', '2024-01', '2024-02'];
  readonly yTicks = [0, 25, 50, 75, 100];
  readonly scopes = ['合并口径', '母公司口径', '管理口径'];
  readonly tabs = [
    { label: '利润收入分析', path: '/bi/profit-income/summary' },
    { label: '利润对比分析', path: '/bi/profit-income/profit-comparison' },
    { label: '收入分析', path: '/bi/profit-income/revenue' },
  ];

  selectedMonth = '2024-02';
  selectedOrg = 'XXX集团';
  selectedScope = this.scopes[0];
  selectedMetricKey = '';
  config: ProfitIncomeConfig = PROFIT_INCOME_CONFIGS.summary;

  constructor(private route: ActivatedRoute) {
    this.route.data.subscribe(data => {
      const kind = (data['profitIncomeKind'] as ProfitIncomeKind) || 'summary';
      this.config = PROFIT_INCOME_CONFIGS[kind];
      this.selectedOrg = this.config.organizations[0];
      this.selectedMetricKey = this.config.metrics[0].key;
    });
  }

  get selectedMetric(): Metric {
    return this.config.metrics.find(metric => metric.key === this.selectedMetricKey) ?? this.config.metrics[0];
  }

  trendArrow(trend: Trend): string {
    return trend === 'up' ? '▲' : trend === 'down' ? '▼' : '■';
  }

  trendClass(trend: Trend): string {
    return `trend-${trend}`;
  }

  chartX(index: number): number {
    return 58 + index * 108;
  }

  chartY(value: number): number {
    return 246 - value * 2.05;
  }

  linePath(points: number[]): string {
    return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${this.chartX(index)} ${this.chartY(point)}`).join(' ');
  }

  indexValue(index: number, value: string | number): string {
    return `${index}-${value}`;
  }
}

const commonOrganizations = ['XXX集团', 'A分公司', 'B分公司', 'C分公司'];
const commonLegends = [
  { label: '营业收入', tone: 'blue' as const },
  { label: '净利润', tone: 'cyan' as const },
  { label: '净利率/费率', tone: 'gold' as const },
];

const PROFIT_INCOME_CONFIGS: Record<ProfitIncomeKind, ProfitIncomeConfig> = {
  summary: {
    title: '利润收入分析',
    subtitle: '展示收入、成本、费用和净利润的核心变化',
    updatedAt: '2025年1月21日',
    compareTitle: '分公司情况',
    trendTitle: '利润收入指标趋势',
    flowTitle: '收入成本费用到净利润',
    tableTitle: '利润收入明细',
    organizations: commonOrganizations,
    compareLegends: commonLegends,
    kpis: [
      { label: '营业收入', value: '1.56万元', deltas: [{ label: '同比', value: '-78.48%', trend: 'down' }, { label: '环比', value: '-67.44%', trend: 'down' }] },
      { label: '营业成本', value: '9.99万元', deltas: [{ label: '同比', value: '+678.24%', trend: 'up' }, { label: '环比', value: '+94.75%', trend: 'up' }] },
      { label: '销售费用', value: '6.75万元', deltas: [{ label: '同比', value: '+21.61%', trend: 'up' }, { label: '环比', value: '-13.33%', trend: 'down' }] },
      { label: '管理费用', value: '9.78万元', deltas: [{ label: '同比', value: '+958.30%', trend: 'up' }, { label: '环比', value: '+705.97%', trend: 'up' }] },
      { label: '研发费用', value: '2.70万元', deltas: [{ label: '同比', value: '+11.15%', trend: 'up' }, { label: '环比', value: '+12.65%', trend: 'up' }] },
      { label: '净利润', value: '-39.31万元', deltas: [{ label: '同比', value: '+175.69%', trend: 'up' }, { label: '环比', value: '+144.45%', trend: 'up' }] },
    ],
    compareRows: [
      { name: 'A分公司', note: '净利率 -26.31%', bars: [{ label: '营业收入', value: '32.86万元', height: 72, tone: 'blue' }, { label: '净利润', value: '-8.65万元', height: 34, tone: 'cyan' }, { label: '净利率', value: '-26.31%', height: 38, tone: 'gold' }] },
      { name: 'B分公司', note: '净利率 -17.50%', bars: [{ label: '营业收入', value: '23.35万元', height: 52, tone: 'blue' }, { label: '净利润', value: '-4.08万元', height: 22, tone: 'cyan' }, { label: '净利率', value: '-17.50%', height: 26, tone: 'gold' }] },
      { name: 'C分公司', note: '净利率 -35.04%', bars: [{ label: '营业收入', value: '32.25万元', height: 70, tone: 'blue' }, { label: '净利润', value: '-11.30万元', height: 42, tone: 'cyan' }, { label: '净利率', value: '-35.04%', height: 46, tone: 'gold' }] },
      { name: 'XXX集团', note: '净利率 -25.20%', bars: [{ label: '营业收入', value: '18.30万元', height: 44, tone: 'blue' }, { label: '净利润', value: '-4.61万元', height: 24, tone: 'cyan' }, { label: '净利率', value: '-25.20%', height: 34, tone: 'gold' }] },
    ],
    metrics: [
      { key: 'netMargin', label: '净利润率', current: '-25.20%', samePeriod: '-12.08%', yoy: '-13.12pct', trend: 'down', series: [{ label: '净利润率', color: '#2588ef', points: [56, 48, 44, 35, 24, 18] }, { label: '同期净利润率', color: '#9aa8bb', points: [62, 57, 52, 48, 36, 30] }] },
      { key: 'netProfit', label: '净利润', current: '-39.31万元', samePeriod: '-14.26万元', yoy: '+175.69%', trend: 'up', series: [{ label: '净利润', color: '#49bdd6', points: [62, 58, 46, 35, 24, 18] }, { label: '同期净利润', color: '#9aa8bb', points: [76, 68, 62, 54, 45, 36] }] },
      { key: 'revenue', label: '营业收入', current: '1.56万元', samePeriod: '7.25万元', yoy: '-78.48%', trend: 'down', series: [{ label: '营业收入', color: '#2588ef', points: [68, 42, 55, 34, 28, 74] }, { label: '同期营业收入', color: '#9aa8bb', points: [86, 79, 75, 72, 70, 66] }] },
    ],
    flowSteps: [
      { label: '营业收入', value: '1.56万元', sign: '+', width: 12, tone: 'blue' },
      { label: '其他收益', value: '2.18万元', sign: '+', width: 18, tone: 'cyan' },
      { label: '营业成本', value: '9.99万元', sign: '-', width: 64, tone: 'red' },
      { label: '销售费用', value: '6.75万元', sign: '-', width: 43, tone: 'gold' },
      { label: '管理费用', value: '9.78万元', sign: '-', width: 62, tone: 'gold' },
      { label: '研发费用', value: '2.70万元', sign: '-', width: 24, tone: 'slate' },
      { label: '所得税影响', value: '0.17万元', sign: '-', width: 10, tone: 'slate' },
      { label: '净利润', value: '-39.31万元', sign: '=', width: 88, tone: 'green' },
    ],
    tableColumns: ['营业收入', '营业成本', '销售费用', '管理费用', '研发费用', '净利润', '净利率'],
    tableRows: [
      { category: '内部组织', org: 'XXX集团', values: ['1.56万元', '9.99万元', '6.75万元', '9.78万元', '2.70万元', '-39.31万元', '-25.20%'] },
      { category: '内部组织', org: 'A分公司', values: ['32.86万元', '16.24万元', '4.20万元', '3.55万元', '1.42万元', '-8.65万元', '-26.31%'] },
      { category: '内部组织', org: 'B分公司', values: ['23.35万元', '10.68万元', '2.98万元', '2.74万元', '0.92万元', '-4.08万元', '-17.50%'] },
      { category: '内部组织', org: 'C分公司', values: ['32.25万元', '18.12万元', '4.86万元', '5.21万元', '1.68万元', '-11.30万元', '-35.04%'] },
    ],
    explain: [
      { title: '使用场景', lines: ['用于月度经营复盘、预算编制、成本控制和利润监控，帮助管理层快速观察收入、成本、费用和净利润的变化。'] },
      { title: '业务价值', lines: ['把收入、成本、费用和利润放在同一张看板中，便于识别利润下滑来自收入不足、成本上升还是费用扩张。'] },
      { title: '模块说明', lines: ['指标卡展示营业收入、成本、销售费用、管理费用、研发费用和净利润，并分别展示同比、环比方向。', '分公司情况对比收入、净利润和净利率，趋势图用于观察利润率和利润额的连续变化。', '构成关系保留“收入增加、成本费用扣减、得到净利润”的业务链路。'] },
      { title: '接入说明', lines: ['当前为静态 mock 版本；真实接入时若缺少某层明细，可只展示已有的指标、趋势或明细，不强行补齐无数据模块。'] },
    ],
  },
  profitComparison: {
    title: '利润对比分析',
    subtitle: '对比收入、成本率、费用率和净利率',
    updatedAt: '2025年1月21日',
    compareTitle: '营业收入对比',
    trendTitle: '利润率与费用率趋势',
    flowTitle: '利润表口径拆解',
    tableTitle: '利润表明细',
    organizations: commonOrganizations,
    compareLegends: [
      { label: '本期收入', tone: 'blue' },
      { label: '同期收入', tone: 'slate' },
      { label: '净利率', tone: 'gold' },
    ],
    kpis: [
      { label: '营业收入', value: '1.56万元', deltas: [{ label: '同比', value: '-78.48%', trend: 'down' }, { label: '环比', value: '-67.44%', trend: 'down' }] },
      { label: '营业成本率', value: '638.98%', deltas: [{ label: '同比', value: '+512.36%', trend: 'up' }] },
      { label: '营业成本', value: '9.99万元', deltas: [{ label: '同比', value: '+678.24%', trend: 'up' }, { label: '环比', value: '+94.75%', trend: 'up' }] },
      { label: '管理费率', value: '625.91%', deltas: [{ label: '同比', value: '+268.90%', trend: 'up' }] },
      { label: '净利润', value: '-39.31万元', deltas: [{ label: '同比', value: '+175.69%', trend: 'up' }, { label: '环比', value: '+144.45%', trend: 'up' }] },
      { label: '销售费率', value: '431.91%', deltas: [{ label: '同比', value: '+328.26%', trend: 'up' }] },
    ],
    compareRows: [
      { name: 'A分公司', note: '本期 32.86万元', bars: [{ label: '本期收入', value: '32.86万元', height: 76, tone: 'blue' }, { label: '同期收入', value: '30.42万元', height: 70, tone: 'slate' }, { label: '净利率', value: '-26.31%', height: 32, tone: 'gold' }] },
      { name: 'B分公司', note: '本期 23.35万元', bars: [{ label: '本期收入', value: '23.35万元', height: 54, tone: 'blue' }, { label: '同期收入', value: '26.18万元', height: 62, tone: 'slate' }, { label: '净利率', value: '-17.50%', height: 24, tone: 'gold' }] },
      { name: 'C分公司', note: '本期 32.25万元', bars: [{ label: '本期收入', value: '32.25万元', height: 74, tone: 'blue' }, { label: '同期收入', value: '29.54万元', height: 68, tone: 'slate' }, { label: '净利率', value: '-35.04%', height: 40, tone: 'gold' }] },
      { name: 'XXX集团', note: '本期 18.30万元', bars: [{ label: '本期收入', value: '18.30万元', height: 42, tone: 'blue' }, { label: '同期收入', value: '24.20万元', height: 56, tone: 'slate' }, { label: '净利率', value: '-25.20%', height: 30, tone: 'gold' }] },
    ],
    metrics: [
      { key: 'costRate', label: '成本率', current: '638.98%', samePeriod: '126.62%', yoy: '+512.36%', trend: 'up', series: [{ label: '成本率', color: '#e84f63', points: [28, 42, 35, 41, 32, 88] }, { label: '同期成本率', color: '#9aa8bb', points: [24, 26, 28, 25, 27, 31] }] },
      { key: 'managementRate', label: '管理费率', current: '625.91%', samePeriod: '357.01%', yoy: '+268.90%', trend: 'up', series: [{ label: '管理费率', color: '#f0a532', points: [18, 42, 36, 40, 32, 82] }, { label: '同期管理费率', color: '#9aa8bb', points: [16, 18, 21, 19, 23, 27] }] },
      { key: 'netMargin', label: '净利率', current: '-25.20%', samePeriod: '-9.12%', yoy: '-16.08pct', trend: 'down', series: [{ label: '净利率', color: '#2588ef', points: [52, 45, 48, 34, 28, 18] }, { label: '同期净利率', color: '#9aa8bb', points: [64, 60, 58, 54, 49, 46] }] },
    ],
    flowSteps: [
      { label: '营业收入', value: '1.56万元', sign: '+', width: 12, tone: 'blue' },
      { label: '营业成本', value: '9.99万元', sign: '-', width: 78, tone: 'red' },
      { label: '销售费用', value: '6.75万元', sign: '-', width: 53, tone: 'gold' },
      { label: '管理费用', value: '9.78万元', sign: '-', width: 76, tone: 'gold' },
      { label: '研发费用', value: '2.70万元', sign: '-', width: 28, tone: 'slate' },
      { label: '其他损益', value: '-11.65万元', sign: '-', width: 84, tone: 'green' },
      { label: '利润总额', value: '-39.14万元', sign: '=', width: 88, tone: 'green' },
      { label: '净利润', value: '-39.31万元', sign: '=', width: 90, tone: 'green' },
    ],
    tableColumns: ['营业收入', '营业成本', '营业成本率', '销售费用', '销售费率', '管理费用', '管理费率', '净利润', '净利率'],
    tableRows: [
      { category: '内部组织', org: 'XXX集团', values: ['1.56万元', '9.99万元', '638.98%', '6.75万元', '431.91%', '9.78万元', '625.91%', '-39.31万元', '-25.20%'] },
      { category: '内部组织', org: 'A分公司', values: ['32.86万元', '16.24万元', '49.42%', '4.20万元', '12.78%', '3.55万元', '10.80%', '-8.65万元', '-26.31%'] },
      { category: '内部组织', org: 'B分公司', values: ['23.35万元', '10.68万元', '45.74%', '2.98万元', '12.76%', '2.74万元', '11.73%', '-4.08万元', '-17.50%'] },
      { category: '内部组织', org: 'C分公司', values: ['32.25万元', '18.12万元', '56.19%', '4.86万元', '15.07%', '5.21万元', '16.16%', '-11.30万元', '-35.04%'] },
    ],
    explain: [
      { title: '使用场景', lines: ['用于财务部门比较各组织收入、成本、费用和利润率，支持利润异常追踪、成本控制和经营责任分析。'] },
      { title: '业务价值', lines: ['将营业收入、营业成本、净利润和费用率放在同一视图，帮助识别收入规模与成本费用之间是否匹配。'] },
      { title: '模块说明', lines: ['核心指标展示营业收入、营业成本、净利润及费用率，并分别标注同比或环比方向。', '营业收入对比、成本率对比、管理费率对比和净利率对比用于横向识别异常组织。', '利润表明细保留收入、成本、费用、利润构成，后续可替换为真实报表口径。'] },
      { title: '接入说明', lines: ['当前为静态 mock 数据；真实接入时费用率、成本率、净利率建议由后端统一计算，前端只按趋势方向渲染红色上升或绿色下降。'] },
    ],
  },
  revenue: {
    title: '收入分析',
    subtitle: '观察营业收入趋势、收入构成和组织贡献',
    updatedAt: '2025年1月21日',
    compareTitle: '收入构成对比',
    trendTitle: '营业收入趋势',
    flowTitle: '收入来源到经营结果',
    tableTitle: '收入明细',
    organizations: commonOrganizations,
    compareLegends: [
      { label: '主营业务收入', tone: 'blue' },
      { label: '其他业务收入', tone: 'cyan' },
      { label: '营业外收入', tone: 'gold' },
    ],
    kpis: [
      { label: '营业收入', value: '1.56万元', deltas: [{ label: '同比', value: '-78.48%', trend: 'down' }, { label: '环比', value: '-67.44%', trend: 'down' }] },
      { label: '净利润', value: '-39.31万元', deltas: [{ label: '同比', value: '+175.69%', trend: 'up' }, { label: '环比', value: '+144.45%', trend: 'up' }] },
      { label: '主营业务收入', value: '1.20万元', deltas: [{ label: '同比', value: '-76.82%', trend: 'down' }] },
      { label: '其他业务收入', value: '0.28万元', deltas: [{ label: '同比', value: '-18.40%', trend: 'down' }] },
      { label: '营业外收入', value: '0.08万元', deltas: [{ label: '同比', value: '+7.50%', trend: 'up' }] },
      { label: '收入净利率', value: '-25.20%', deltas: [{ label: '同比', value: '-13.12pct', trend: 'down' }] },
    ],
    compareRows: [
      { name: '2023', note: '收入 120.70万元', bars: [{ label: '主营业务收入', value: '120.70万元', height: 74, tone: 'blue' }, { label: '其他业务收入', value: '138.76万元', height: 86, tone: 'cyan' }, { label: '营业外收入', value: '126.72万元', height: 78, tone: 'gold' }] },
      { name: '2024', note: '收入 106.27万元', bars: [{ label: '主营业务收入', value: '100.77万元', height: 62, tone: 'blue' }, { label: '其他业务收入', value: '124.31万元', height: 76, tone: 'cyan' }, { label: '营业外收入', value: '106.27万元', height: 65, tone: 'gold' }] },
      { name: 'A分公司', note: '占比 32.4%', bars: [{ label: '主营业务收入', value: '32.86万元', height: 68, tone: 'blue' }, { label: '其他业务收入', value: '4.12万元', height: 18, tone: 'cyan' }, { label: '营业外收入', value: '0.62万元', height: 12, tone: 'gold' }] },
      { name: 'B分公司', note: '占比 23.1%', bars: [{ label: '主营业务收入', value: '23.35万元', height: 50, tone: 'blue' }, { label: '其他业务收入', value: '2.74万元', height: 16, tone: 'cyan' }, { label: '营业外收入', value: '0.45万元', height: 10, tone: 'gold' }] },
    ],
    metrics: [
      { key: 'revenue', label: '营业收入', current: '1.56万元', samePeriod: '7.25万元', yoy: '-78.48%', trend: 'down', series: [{ label: '营业收入', color: '#2588ef', points: [72, 21, 54, 32, 28, 86] }, { label: '同期营业收入', color: '#9aa8bb', points: [80, 76, 72, 70, 68, 65] }] },
      { key: 'mainRevenue', label: '主营业务收入', current: '1.20万元', samePeriod: '5.18万元', yoy: '-76.82%', trend: 'down', series: [{ label: '主营业务收入', color: '#2588ef', points: [66, 24, 48, 30, 25, 72] }, { label: '同期主营业务收入', color: '#9aa8bb', points: [74, 70, 68, 64, 60, 58] }] },
      { key: 'revenueMix', label: '收入结构占比', current: '主营 76.9%', samePeriod: '主营 71.4%', yoy: '+5.5pct', trend: 'up', series: [{ label: '主营占比', color: '#49bdd6', points: [62, 66, 68, 71, 74, 77] }, { label: '其他收入占比', color: '#f0a532', points: [38, 34, 32, 29, 26, 23] }] },
    ],
    flowSteps: [
      { label: '主营业务收入', value: '1.20万元', sign: '+', width: 76, tone: 'blue' },
      { label: '其他业务收入', value: '0.28万元', sign: '+', width: 22, tone: 'cyan' },
      { label: '营业外收入', value: '0.08万元', sign: '+', width: 10, tone: 'gold' },
      { label: '营业收入', value: '1.56万元', sign: '=', width: 86, tone: 'blue' },
      { label: '营业成本', value: '9.99万元', sign: '-', width: 82, tone: 'red' },
      { label: '期间费用', value: '19.23万元', sign: '-', width: 96, tone: 'gold' },
      { label: '其他损益', value: '-11.65万元', sign: '-', width: 70, tone: 'slate' },
      { label: '净利润', value: '-39.31万元', sign: '=', width: 90, tone: 'green' },
    ],
    tableColumns: ['营业收入', '主营业务收入', '其他业务收入', '营业外收入', '同比', '环比', '净利润', '净利率'],
    tableRows: [
      { category: '年度构成', org: '2024', values: ['106.27万元', '100.77万元', '4.82万元', '0.68万元', '-11.95%', '-6.24%', '-39.31万元', '-25.20%'] },
      { category: '年度构成', org: '2023', values: ['120.70万元', '113.85万元', '6.20万元', '0.65万元', '+18.40%', '+10.22%', '-14.26万元', '-12.08%'] },
      { category: '内部组织', org: 'A分公司', values: ['32.86万元', '30.52万元', '1.72万元', '0.62万元', '+10.00%', '+6.32%', '-8.65万元', '-26.31%'] },
      { category: '内部组织', org: 'B分公司', values: ['23.35万元', '21.86万元', '1.04万元', '0.45万元', '-6.80%', '-2.14%', '-4.08万元', '-17.50%'] },
    ],
    explain: [
      { title: '使用场景', lines: ['用于分析营业收入趋势、收入来源构成和组织贡献，支持经营复盘、销售目标跟踪和收入质量判断。'] },
      { title: '业务价值', lines: ['通过区分主营业务收入、其他业务收入和营业外收入，判断收入增长是否来自核心业务，以及收入变化对净利润的影响。'] },
      { title: '模块说明', lines: ['指标卡展示营业收入、净利润和收入构成，并保留同比、环比变化。', '趋势图展示本期与同期收入变化，收入构成对比展示不同年度或组织的收入来源。', '收入来源到经营结果模块将收入构成、成本费用和净利润串起来，避免只看收入不看利润质量。'] },
      { title: '接入说明', lines: ['当前为静态 mock 数据；真实接入时若只具备收入一层数据，可隐藏收入构成和利润拆解的缺失项，只保留营业收入趋势与明细。'] },
    ],
  },
};
