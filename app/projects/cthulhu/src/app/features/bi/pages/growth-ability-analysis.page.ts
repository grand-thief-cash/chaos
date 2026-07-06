import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type Trend = 'up' | 'down';

interface GrowthKpi {
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

interface GrowthMetric {
  key: string;
  label: string;
  current: string;
  samePeriod: string;
  industryAvg: string;
  trend: Trend;
  series: TrendSeries[];
}

interface GrowthRow {
  category: string;
  org: string;
  mainRevenueAvg: string;
  fixedAssetGrowth: string;
  fixedAssetRenewal: string;
  totalAssetGrowth: string;
  techInput: string;
  operatingProfitGrowth: string;
  revenueGrowth: string;
  capitalAccumulation: string;
}

@Component({
  selector: 'app-bi-growth-ability-analysis-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="growth-page">
      <header class="page-header">
        <div>
          <h1>发展能力分析</h1>
          <span>更新日期：2025年1月20日</span>
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

      <section class="kpi-grid" aria-label="发展能力核心指标">
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
            <h2>关键发展能力指标对标</h2>
            <span>公司 / 对标公司 / 行业均值</span>
          </header>
          <div class="radar-layout">
            <svg class="radar-chart" viewBox="0 0 540 360" role="img" aria-label="关键发展能力指标雷达图">
              @for (level of radarLevels; track level) {
                <polygon class="radar-ring" [attr.points]="radarPolygon(level)"></polygon>
              }
              @for (axis of radarAxes; track axis; let index = $index) {
                <line class="radar-axis" x1="270" y1="180" [attr.x2]="radarPoint(index, 100).x" [attr.y2]="radarPoint(index, 100).y"></line>
                <text class="radar-label" [attr.x]="radarPoint(index, 118).x" [attr.y]="radarPoint(index, 118).y">{{ axis }}</text>
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
            <h2>发展能力指标变动趋势分析</h2>
            <label>
              <span>指标筛选</span>
              <select [(ngModel)]="selectedMetricKey">
                @for (metric of metrics; track metric.key) {
                  <option [value]="metric.key">{{ metric.label }}</option>
                }
              </select>
            </label>
          </header>
          <div class="trend-summary">
            <strong>{{ selectedMetric.current }}</strong>
            <span>{{ selectedMetric.label }}</span>
            <span>同期值：{{ selectedMetric.samePeriod }}</span>
            <span>业内平均：{{ selectedMetric.industryAvg }}</span>
            <b [class]="trendClass(selectedMetric.trend)">{{ trendArrow(selectedMetric.trend) }}</b>
          </div>
          <svg class="line-chart" viewBox="0 0 640 300" role="img" aria-label="发展能力指标趋势">
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
            <h2>各项指标明细</h2>
            <span>本期指标值与同期指标值用于后续接入真实数据时校验口径</span>
          </header>
          <table>
            <thead>
              <tr>
                <th>数据分类</th>
                <th>组织名称</th>
                <th>主营业务收入近三年平均增长率</th>
                <th>固定资产增长率</th>
                <th>固定资产成新率</th>
                <th>总资产增长率</th>
                <th>技术投入比率</th>
                <th>营业利润增长率</th>
                <th>营业收入增长率</th>
                <th>资本累计率</th>
              </tr>
            </thead>
            <tbody>
              @for (row of rows; track row.category + row.org) {
                <tr>
                  <td>{{ row.category }}</td>
                  <td>{{ row.org }}</td>
                  <td>{{ row.mainRevenueAvg }}</td>
                  <td>{{ row.fixedAssetGrowth }}</td>
                  <td>{{ row.fixedAssetRenewal }}</td>
                  <td>{{ row.totalAssetGrowth }}</td>
                  <td>{{ row.techInput }}</td>
                  <td>{{ row.operatingProfitGrowth }}</td>
                  <td>{{ row.revenueGrowth }}</td>
                  <td>{{ row.capitalAccumulation }}</td>
                </tr>
              }
            </tbody>
          </table>
        </article>
      </section>

      <section class="explain-panel" aria-label="发展能力分析说明">
        <article>
          <h2>使用场景</h2>
          <p>用于战略规划、年度经营复盘和市场竞争力评估，帮助管理层观察收入、利润、资产投入和技术投入等增长指标的变化。</p>
        </article>
        <article>
          <h2>业务价值</h2>
          <p>通过增长指标、对标组织和行业均值的横向比较，识别增长机会、资源投入效率和潜在经营风险，为扩张节奏和资源配置提供依据。</p>
        </article>
        <article>
          <h2>模块说明</h2>
          <ul>
            <li>营业收入增长率、营业利润增长率用于观察业务扩张和利润增长质量。</li>
            <li>总资产增长率、固定资产增长率、固定资产成新率用于判断资产扩张和资产更新情况。</li>
            <li>技术投入比率、资本累计率、资本保值增值率用于衡量创新投入、资本积累和资本保全能力。</li>
            <li>雷达图展示不同组织和行业均值的综合对标，趋势图展示单项指标的时间变化。</li>
          </ul>
        </article>
        <article>
          <h2>使用条件</h2>
          <p>当前页面为静态 mock 数据版本；后续接入真实数据时，需要提供本期值、同期值、对标组织值和行业均值等口径一致的数据。</p>
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

    .growth-page {
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
    .trend-summary span,
    .page-header span {
      color: #657386;
      font-size: 13px;
      line-height: 1.45;
    }

    .page-header span {
      color: #fff;
      font-weight: 650;
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
      min-height: 360px;
      padding: 16px;
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
      min-width: 1140px;
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

    .explain-panel {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      background: #fff;
      border: 1px solid #dce7f2;
      padding: 16px;
    }

    .explain-panel article {
      padding: 12px 14px;
      background: #f8fbff;
      border: 1px solid #e5edf6;
    }

    .explain-panel h2 {
      margin-bottom: 8px;
      font-size: 17px;
      color: #17304d;
    }

    .explain-panel p,
    .explain-panel li {
      margin: 0;
      color: #506176;
      font-size: 14px;
      line-height: 1.7;
    }

    .explain-panel ul {
      margin: 0;
      padding-left: 18px;
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

      .explain-panel {
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
export class GrowthAbilityAnalysisPageComponent {
  organizations = ['XXX集团', 'Z公司', 'X公司', 'W公司'];
  benchmarks = ['外部组织', '行业均值', '集团预算'];
  selectedMonth = '2025-02';
  selectedOrg = this.organizations[0];
  selectedBenchmark = this.benchmarks[0];
  selectedMetricKey = 'revenueGrowth';

  kpis: GrowthKpi[] = [
    { label: '营业收入增长率', value: '120.48%', samePeriod: '43.70%', industryAvg: '24.84%', trend: 'up' },
    { label: '主营业务收入近三年平均增长率', value: '88.62%', samePeriod: '51.47%', industryAvg: '53.17%', trend: 'up' },
    { label: '营业利润增长率', value: '129.96%', samePeriod: '51.06%', industryAvg: '87.77%', trend: 'up' },
    { label: '总资产增长率', value: '134.38%', samePeriod: '34.56%', industryAvg: '12.97%', trend: 'up' },
    { label: '资本保值增值率', value: '167.80%', samePeriod: '101.10%', industryAvg: '63.31%', trend: 'up' },
    { label: '固定资产增长率', value: '96.98%', samePeriod: '55.02%', industryAvg: '41.71%', trend: 'up' },
    { label: '固定资产成新率', value: '156.78%', samePeriod: '155.48%', industryAvg: '68.64%', trend: 'up' },
    { label: '技术投入比率', value: '134.64%', samePeriod: '163.44%', industryAvg: '25.15%', trend: 'down' },
  ];

  radarAxes = ['主营业务收入近三年平均增长率', '固定资产成新率', '总资产增长率', '技术投入比率', '营业利润增长率', '营业收入增长率', '资本保值增值率', '固定资产增长率'];
  radarLevels = [20, 40, 60, 80, 100];
  radarSeries: RadarSeries[] = [
    { label: 'C分公司', color: '#1d78d6', values: [82, 72, 86, 67, 78, 74, 70, 62] },
    { label: 'Z公司', color: '#51c9c3', values: [90, 76, 88, 82, 84, 80, 72, 70] },
    { label: '行业均值', color: '#a8a2ea', values: [53, 69, 13, 25, 88, 25, 63, 42] },
  ];

  months = ['2023-11', '2023-12', '2024-01', '2024-02', '2024-03', '2024-04'];
  yTicks = [0, 25, 50, 75, 100, 125, 150];
  metrics: GrowthMetric[] = [
    {
      key: 'revenueGrowth',
      label: '营业收入增长率',
      current: '120.48%',
      samePeriod: '43.70%',
      industryAvg: '24.84%',
      trend: 'up',
      series: [
        { label: 'C分公司', color: '#1d78d6', values: [35, 53, 36, 92, 11, 90] },
        { label: 'Z公司', color: '#51c9c3', values: [24, 53, 73, 51, 71, 18] },
        { label: '行业均值', color: '#a8a2ea', values: [25, 17, 63, 86, 17, 28] },
      ],
    },
    {
      key: 'totalAssetGrowth',
      label: '总资产增长率',
      current: '134.38%',
      samePeriod: '34.56%',
      industryAvg: '12.97%',
      trend: 'up',
      series: [
        { label: 'C分公司', color: '#1d78d6', values: [52, 68, 72, 95, 118, 134] },
        { label: 'Z公司', color: '#51c9c3', values: [45, 58, 64, 75, 91, 102] },
        { label: '行业均值', color: '#a8a2ea', values: [10, 11, 13, 12, 14, 13] },
      ],
    },
    {
      key: 'techInput',
      label: '技术投入比率',
      current: '134.64%',
      samePeriod: '163.44%',
      industryAvg: '25.15%',
      trend: 'down',
      series: [
        { label: 'C分公司', color: '#1d78d6', values: [118, 142, 156, 151, 140, 135] },
        { label: 'Z公司', color: '#51c9c3', values: [62, 84, 96, 106, 111, 107] },
        { label: '行业均值', color: '#a8a2ea', values: [18, 21, 23, 25, 26, 25] },
      ],
    },
  ];

  rows: GrowthRow[] = [
    { category: '外部组织', org: 'Z公司', mainRevenueAvg: '120.48%', fixedAssetGrowth: '96.98%', fixedAssetRenewal: '156.78%', totalAssetGrowth: '134.38%', techInput: '134.64%', operatingProfitGrowth: '129.96%', revenueGrowth: '120.48%', capitalAccumulation: '167.80%' },
    { category: '外部组织', org: 'X公司', mainRevenueAvg: '122.80%', fixedAssetGrowth: '26.86%', fixedAssetRenewal: '22.50%', totalAssetGrowth: '167.80%', techInput: '106.90%', operatingProfitGrowth: '153.20%', revenueGrowth: '122.80%', capitalAccumulation: '101.10%' },
    { category: '外部组织', org: 'W公司', mainRevenueAvg: '63.94%', fixedAssetGrowth: '57.98%', fixedAssetRenewal: '156.38%', totalAssetGrowth: '156.02%', techInput: '84.94%', operatingProfitGrowth: '154.24%', revenueGrowth: '63.94%', capitalAccumulation: '162.60%' },
    { category: '行业均值', org: '/', mainRevenueAvg: '24.84%', fixedAssetGrowth: '41.71%', fixedAssetRenewal: '68.64%', totalAssetGrowth: '12.97%', techInput: '25.15%', operatingProfitGrowth: '87.77%', revenueGrowth: '24.84%', capitalAccumulation: '63.31%' },
  ];

  get selectedMetric(): GrowthMetric {
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
    const radius = 134 * (value / 100);
    return {
      x: 270 + Math.cos(angle) * radius,
      y: 180 + Math.sin(angle) * radius,
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

  indexValue(index: number, value: number): string {
    return `${index}-${value}`;
  }
}
