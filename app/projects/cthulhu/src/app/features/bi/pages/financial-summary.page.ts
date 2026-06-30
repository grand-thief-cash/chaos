import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type Trend = 'up' | 'down' | 'flat';

interface KpiCard {
  label: string;
  value: string;
  samePeriod: string;
  yoy: string;
  trend: Trend;
  note: string;
}

interface MiniBar {
  label: string;
  value: string;
  width: number;
  tone: 'blue' | 'green' | 'gold' | 'red' | 'slate';
}

interface StatementRow {
  item: string;
  current: string;
  previous: string;
  delta: string;
  trend: Trend;
}

interface TrendPoint {
  period: string;
  revenue: number;
  profit: number;
  cash: number;
}

interface MetricComparison {
  org: string;
  value: string;
  samePeriod: string;
  yoy: string;
  trend: Trend;
  height: number;
  sameHeight: number;
  tone: 'blue' | 'green' | 'gold' | 'red';
}

interface MetricTrendPoint {
  period: string;
  value: string;
  samePeriod: string;
  height: number;
  sameHeight: number;
}

interface IndicatorMetric {
  key: string;
  label: string;
  unit: string;
  current: string;
  samePeriod: string;
  yoy: string;
  direction: Trend;
  comparison: MetricComparison[];
  trendPoints: MetricTrendPoint[];
}

@Component({
  selector: 'app-bi-financial-summary-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="financial-page">
      <header class="financial-header">
        <div>
          <h1>财务综合分析</h1>
          <span>更新日期：2025年2月11日</span>
        </div>
        <div class="filters" aria-label="财务综合分析筛选条件">
          <label>
            <span>组织</span>
            <select [(ngModel)]="selectedOrg">
              @for (org of organizations; track org) {
                <option [value]="org">{{ org }}</option>
              }
            </select>
          </label>
          <label>
            <span>期间</span>
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

      <section class="kpi-grid" aria-label="核心财务指标">
        @for (kpi of kpis; track kpi.label) {
          <article class="kpi-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
            <div class="same-period">同期值：{{ kpi.samePeriod }}</div>
            <div class="delta" [class]="trendClass(kpi.trend)">
              <b>{{ trendArrow(kpi.trend) }}</b>
              <em>同比 {{ kpi.yoy }}</em>
            </div>
            <small>{{ kpi.note }}</small>
          </article>
        }
      </section>

      <section class="indicator-section">
        <header class="indicator-toolbar">
          <div>
            <h2>指标选择</h2>
            <span>当前指标：{{ selectedMetric.label }}，同期值：{{ selectedMetric.samePeriod }}</span>
          </div>
          <label class="metric-picker">
            <span>指标名称</span>
            <select [(ngModel)]="selectedMetricKey">
              @for (metric of indicatorMetrics; track metric.key) {
                <option [value]="metric.key">{{ metric.label }}</option>
              }
            </select>
          </label>
        </header>

        <div class="indicator-grid">
          <article class="panel indicator-panel">
            <header>
              <h2>指标值对比</h2>
              <span>{{ selectedMetric.unit }} / {{ selectedOrg }}</span>
            </header>
            <div class="compare-chart" aria-label="指标值对比">
              @for (item of selectedMetric.comparison; track item.org) {
                <div class="compare-column">
                  <div class="compare-bars">
                    <i class="same" [style.height.%]="item.sameHeight"></i>
                    <i [class]="item.tone" [style.height.%]="item.height"></i>
                  </div>
                  <strong>{{ item.value }}</strong>
                  <span>{{ item.org }}</span>
                  <small [class]="trendClass(item.trend)">同比 {{ trendArrow(item.trend) }} {{ item.yoy }}</small>
                </div>
              }
            </div>
            <div class="compare-legend">
              <span><i class="same"></i>同期值</span>
              <span><i class="blue"></i>本期值</span>
            </div>
          </article>

          <article class="panel indicator-panel">
            <header>
              <h2>指标趋势</h2>
              <span [class]="trendClass(selectedMetric.direction)">同比 {{ trendArrow(selectedMetric.direction) }} {{ selectedMetric.yoy }}</span>
            </header>
            <div class="trend-chart metric-trend" aria-label="指标本期与同期趋势">
              @for (point of selectedMetric.trendPoints; track point.period) {
                <div class="trend-column">
                  <div class="bars">
                    <i class="slate same" [style.height.%]="point.sameHeight"></i>
                    <i class="blue" [style.height.%]="point.height"></i>
                  </div>
                  <strong>{{ point.value }}</strong>
                  <span>{{ point.period }}</span>
                </div>
              }
            </div>
            <div class="legend">
              <span><i class="blue"></i>本期值</span>
              <span><i class="slate"></i>同期值</span>
            </div>
          </article>
        </div>
      </section>

      <section class="dashboard-grid">
        <article class="panel profit-panel">
          <header>
            <h2>营业收入与净利润</h2>
            <span>利润质量</span>
          </header>
          <div class="profit-layout">
            <div class="waterfall">
              @for (bar of profitBars; track bar.label) {
                <div class="bar-line">
                  <span>{{ bar.label }}</span>
                  <div class="bar-track">
                    <i [class]="bar.tone" [style.width.%]="bar.width"></i>
                  </div>
                  <strong>{{ bar.value }}</strong>
                </div>
              }
            </div>
            <div class="margin-box">
              <span>销售净利率</span>
              <strong>12.36%</strong>
              <small>收入增长放缓，费用率小幅改善</small>
            </div>
          </div>
        </article>

        <article class="panel cash-panel">
          <header>
            <h2>现金流分析</h2>
            <span>资金效率</span>
          </header>
          <div class="cash-flow">
            <div class="cash-node inflow">
              <span>现金流入</span>
              <strong>31.42亿</strong>
            </div>
            <div class="cash-node outflow">
              <span>现金流出</span>
              <strong>29.24亿</strong>
            </div>
            <div class="cash-node net">
              <span>净流入</span>
              <strong>2.18亿</strong>
            </div>
          </div>
          <div class="cash-ratio">
            <span>经营现金 / 净利润</span>
            <strong>0.62</strong>
            <small>现金回款弱于利润确认，需要关注应收周转</small>
          </div>
        </article>

        <article class="panel balance-panel">
          <header>
            <h2>资产负债结构</h2>
            <span>偿债能力</span>
          </header>
          <div class="stack-compare">
            @for (group of balanceGroups; track group.title) {
              <div class="stack-group">
                <div class="stack-title">
                  <span>{{ group.title }}</span>
                  <strong>{{ group.total }}</strong>
                </div>
                @for (bar of group.items; track bar.label) {
                  <div class="stack-row">
                    <span>{{ bar.label }}</span>
                    <i [class]="bar.tone" [style.width.%]="bar.width"></i>
                    <strong>{{ bar.value }}</strong>
                  </div>
                }
              </div>
            }
          </div>
        </article>

        <article class="panel trend-panel">
          <header>
            <h2>指标趋势对比</h2>
            <span>近6期</span>
          </header>
          <div class="trend-chart" aria-label="收入利润现金流趋势">
            @for (point of trendPoints; track point.period) {
              <div class="trend-column">
                <div class="bars">
                  <i class="blue" [style.height.%]="point.revenue"></i>
                  <i class="green" [style.height.%]="point.profit"></i>
                  <i class="gold" [style.height.%]="point.cash"></i>
                </div>
                <span>{{ point.period }}</span>
              </div>
            }
          </div>
          <div class="legend">
            <span><i class="blue"></i>营业收入</span>
            <span><i class="green"></i>净利润</span>
            <span><i class="gold"></i>现金净流入</span>
          </div>
        </article>

        <article class="panel table-panel">
          <header>
            <h2>周转与费用监控</h2>
            <span>风险项</span>
          </header>
          <table>
            <thead>
              <tr>
                <th>项目</th>
                <th>本期</th>
                <th>上期</th>
                <th>变化</th>
              </tr>
            </thead>
            <tbody>
              @for (row of statementRows; track row.item) {
                <tr>
                  <td>{{ row.item }}</td>
                  <td>{{ row.current }}</td>
                  <td>{{ row.previous }}</td>
                  <td [class]="trendClass(row.trend)">{{ trendArrow(row.trend) }} {{ row.delta }}</td>
                </tr>
              }
            </tbody>
          </table>
        </article>

        <article class="panel tax-panel">
          <header>
            <h2>企业纳税分析</h2>
            <span>税务执行</span>
          </header>
          <div class="tax-grid">
            <div>
              <span>应缴纳税总额</span>
              <strong>1.28亿</strong>
            </div>
            <div>
              <span>实缴纳税总额</span>
              <strong>1.16亿</strong>
            </div>
            <div>
              <span>缴纳完成率</span>
              <strong>90.6%</strong>
            </div>
          </div>
          <div class="tax-bar">
            <i style="width: 90.6%"></i>
          </div>
        </article>
      </section>
    </section>
  `,
  styles: [`
    :host {
      display: block;
      min-height: calc(100vh - 110px);
      background: #f3f6fb;
      color: #152033;
      font-size: 14px;
    }

    .financial-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .financial-header {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: center;
      padding: 18px 24px;
      background: linear-gradient(100deg, #235fd9 0%, #52a8f1 55%, #c8e8df 100%);
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

    .financial-header span {
      font-weight: 650;
    }

    .filters {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .filters label {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #203047;
      font-weight: 650;
    }

    select,
    input {
      height: 34px;
      min-width: 132px;
      border: 1px solid rgba(34, 72, 112, 0.26);
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.52);
      color: #1b2a3c;
      padding: 0 10px;
      font-size: 14px;
      font-weight: 620;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(150px, 1fr));
      gap: 12px;
    }

    .kpi-card,
    .panel {
      background: #fff;
      border: 1px solid #dfe7f0;
    }

    .kpi-card {
      padding: 14px;
      border-left: 4px solid #2588ef;
    }

    .kpi-card span,
    .kpi-card small,
    .same-period,
    .panel header span,
    .cash-ratio span,
    .margin-box span,
    .tax-grid span {
      color: #667386;
      font-size: 13px;
      line-height: 1.45;
    }

    .kpi-card strong {
      display: block;
      margin: 5px 0;
      font-size: 22px;
      line-height: 1.1;
    }

    .same-period {
      margin-bottom: 5px;
      white-space: nowrap;
    }

    .delta {
      display: flex;
      gap: 6px;
      align-items: center;
      font-size: 14px;
      font-weight: 720;
    }

    .trend-up {
      color: #e84f63;
    }

    .trend-down {
      color: #19a45f;
    }

    .trend-flat {
      color: #f0a532;
    }

    .indicator-section {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .indicator-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      padding: 14px 16px;
      background: #fff;
      border: 1px solid #dfe7f0;
    }

    .indicator-toolbar h2 {
      margin-bottom: 4px;
    }

    .indicator-toolbar > div > span {
      color: #667386;
      font-size: 13px;
      line-height: 1.45;
    }

    .metric-picker {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 650;
      color: #203047;
    }

    .indicator-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .indicator-panel {
      min-height: 288px;
    }

    .compare-chart {
      height: 190px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      align-items: end;
      border-bottom: 1px solid #dce6f2;
      padding-top: 8px;
    }

    .compare-column {
      display: flex;
      flex-direction: column;
      gap: 5px;
      align-items: center;
      height: 100%;
      min-width: 0;
      color: #667386;
      font-size: 13px;
      line-height: 1.35;
    }

    .compare-column strong {
      color: #152033;
      font-size: 15px;
    }

    .compare-column small {
      font-size: 13px;
      line-height: 1.35;
    }

    .compare-bars {
      display: flex;
      align-items: end;
      gap: 6px;
      height: 120px;
      width: 48px;
    }

    .compare-bars i {
      width: 16px;
      min-height: 8px;
      background: #2588ef;
    }

    .compare-bars .same,
    .compare-legend .same,
    .metric-trend .same {
      background: #b9c4d2;
      opacity: 0.75;
    }

    .compare-legend {
      display: flex;
      gap: 16px;
      margin-top: 12px;
      color: #667386;
      font-size: 13px;
    }

    .compare-legend i {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 5px;
      vertical-align: -1px;
    }

    .dashboard-grid {
      display: grid;
      grid-template-columns: 1.1fr 1fr 1.2fr;
      gap: 12px;
      align-items: stretch;
    }

    .panel {
      min-height: 250px;
      padding: 16px;
    }

    .panel header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 14px;
    }

    h2 {
      font-size: 18px;
      line-height: 1.25;
    }

    .profit-panel,
    .trend-panel {
      grid-column: span 2;
    }

    .profit-layout,
    .stack-compare,
    .cash-flow,
    .tax-grid {
      display: grid;
      gap: 12px;
    }

    .profit-layout {
      grid-template-columns: 1fr 160px;
    }

    .bar-line,
    .stack-row {
      display: grid;
      grid-template-columns: 90px 1fr 70px;
      gap: 10px;
      align-items: center;
      min-height: 38px;
      font-size: 14px;
    }

    .bar-track {
      height: 10px;
      background: #edf3fb;
    }

    .bar-track i,
    .stack-row i,
    .tax-bar i {
      display: block;
      height: 100%;
    }

    .blue { background: #2588ef; }
    .green { background: #19a45f; }
    .gold { background: #f0a532; }
    .red { background: #e84f63; }
    .slate { background: #708199; }

    .margin-box,
    .cash-ratio {
      padding: 14px;
      background: #f8fbff;
      border: 1px solid #e5edf6;
    }

    .margin-box small,
    .cash-ratio small {
      color: #667386;
      font-size: 13px;
      line-height: 1.45;
    }

    .margin-box strong,
    .cash-ratio strong {
      display: block;
      margin: 6px 0;
      font-size: 26px;
    }

    .cash-flow {
      grid-template-columns: repeat(3, 1fr);
    }

    .cash-node {
      padding: 14px;
      background: #f8fbff;
      border-top: 4px solid #2588ef;
    }

    .cash-node strong,
    .tax-grid strong {
      display: block;
      margin-top: 6px;
      font-size: 20px;
    }

    .cash-node.outflow { border-top-color: #e84f63; }
    .cash-node.net { border-top-color: #19a45f; }

    .stack-compare {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .stack-title {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
      font-weight: 760;
    }

    .stack-row {
      grid-template-columns: 88px 1fr 62px;
      margin-bottom: 9px;
    }

    .stack-row i {
      height: 9px;
      background: #2588ef;
    }

    .trend-chart {
      height: 170px;
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 12px;
      align-items: end;
      border-bottom: 1px solid #dce6f2;
      padding-top: 10px;
    }

    .trend-column {
      display: flex;
      flex-direction: column;
      gap: 8px;
      align-items: center;
      height: 100%;
    }

    .bars {
      display: flex;
      align-items: end;
      gap: 4px;
      height: 130px;
      width: 42px;
    }

    .bars i {
      width: 10px;
      min-height: 8px;
    }

    .metric-trend .bars {
      gap: 7px;
      width: 34px;
    }

    .metric-trend .bars i {
      width: 12px;
    }

    .metric-trend strong {
      color: #152033;
      font-size: 14px;
      line-height: 1;
    }

    .legend {
      display: flex;
      gap: 16px;
      margin-top: 12px;
      color: #667386;
      font-size: 13px;
    }

    .legend i {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 5px;
      vertical-align: -1px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }

    th,
    td {
      padding: 10px 8px;
      border-bottom: 1px solid #edf2f7;
      text-align: left;
    }

    th {
      color: #667386;
      font-weight: 650;
      background: #f8fbff;
    }

    .tax-grid {
      grid-template-columns: repeat(3, 1fr);
    }

    .tax-grid div {
      padding: 12px;
      background: #f8fbff;
      border: 1px solid #e5edf6;
    }

    .tax-bar {
      height: 12px;
      margin-top: 18px;
      background: #edf3fb;
    }

    @media (max-width: 1200px) {
      .financial-header {
        align-items: flex-start;
        flex-direction: column;
      }

      .filters {
        justify-content: flex-start;
      }

      .kpi-grid {
        grid-template-columns: repeat(3, minmax(150px, 1fr));
      }

      .dashboard-grid {
        grid-template-columns: 1fr;
      }

      .indicator-grid {
        grid-template-columns: 1fr;
      }

      .profit-panel,
      .trend-panel {
        grid-column: auto;
      }
    }

    @media (max-width: 720px) {
      .kpi-grid,
      .indicator-toolbar,
      .profit-layout,
      .stack-compare,
      .cash-flow,
      .tax-grid {
        grid-template-columns: 1fr;
      }

      .indicator-toolbar {
        align-items: flex-start;
        flex-direction: column;
      }

      .compare-chart {
        grid-template-columns: repeat(2, 1fr);
        height: auto;
        min-height: 220px;
      }

      .filters label,
      .metric-picker,
      select,
      input {
        width: 100%;
      }
    }
  `],
})
export class FinancialSummaryPageComponent {
  organizations = ['XXX集团', '华东事业群', '上市公司合并口径'];
  scopes = ['合并报表', '母公司口径'];
  selectedOrg = this.organizations[0];
  selectedMonth = '2025-02';
  selectedScope = this.scopes[0];
  selectedMetricKey = 'revenue';

  kpis: KpiCard[] = [
    { label: '营业收入', value: '28.46亿', samePeriod: '26.18亿', yoy: '+8.7%', trend: 'up', note: '主营业务恢复增长' },
    { label: '净利润', value: '3.52亿', samePeriod: '3.67亿', yoy: '-4.1%', trend: 'down', note: '投资收益回落' },
    { label: '资产总额', value: '19.68亿', samePeriod: '18.58亿', yoy: '+5.9%', trend: 'up', note: '流动资产占比提升' },
    { label: '负债总额', value: '6.79亿', samePeriod: '6.60亿', yoy: '+2.8%', trend: 'up', note: '短债压力可控' },
    { label: '现金净流入', value: '2.18亿', samePeriod: '1.76亿', yoy: '+0.42亿', trend: 'up', note: '经营现金改善' },
    { label: '费用总额', value: '7.58亿', samePeriod: '7.70亿', yoy: '-1.6%', trend: 'down', note: '费用率小幅下降' },
  ];

  indicatorMetrics: IndicatorMetric[] = [
    {
      key: 'revenue',
      label: '营业收入',
      unit: '亿元',
      current: '28.46亿',
      samePeriod: '26.18亿',
      yoy: '+8.7%',
      direction: 'up',
      comparison: [
        { org: 'XXX集团', value: '28.46亿', samePeriod: '26.18亿', yoy: '+8.7%', trend: 'up', height: 92, sameHeight: 84, tone: 'blue' },
        { org: 'A分公司', value: '8.38亿', samePeriod: '7.62亿', yoy: '+10.0%', trend: 'up', height: 62, sameHeight: 55, tone: 'green' },
        { org: 'B分公司', value: '7.31亿', samePeriod: '7.84亿', yoy: '-6.8%', trend: 'down', height: 54, sameHeight: 58, tone: 'gold' },
        { org: 'C分公司', value: '6.44亿', samePeriod: '5.71亿', yoy: '+12.8%', trend: 'up', height: 48, sameHeight: 42, tone: 'red' },
      ],
      trendPoints: [
        { period: '09月', value: '23.8', samePeriod: '22.1', height: 60, sameHeight: 55 },
        { period: '10月', value: '25.1', samePeriod: '23.7', height: 64, sameHeight: 59 },
        { period: '11月', value: '24.7', samePeriod: '24.0', height: 63, sameHeight: 60 },
        { period: '12月', value: '27.2', samePeriod: '25.8', height: 76, sameHeight: 69 },
        { period: '01月', value: '26.5', samePeriod: '24.3', height: 70, sameHeight: 61 },
        { period: '02月', value: '28.5', samePeriod: '26.2', height: 82, sameHeight: 72 },
      ],
    },
    {
      key: 'profit',
      label: '净利润',
      unit: '亿元',
      current: '3.52亿',
      samePeriod: '3.67亿',
      yoy: '-4.1%',
      direction: 'down',
      comparison: [
        { org: 'XXX集团', value: '3.52亿', samePeriod: '3.67亿', yoy: '-4.1%', trend: 'down', height: 70, sameHeight: 74, tone: 'blue' },
        { org: 'A分公司', value: '1.08亿', samePeriod: '0.96亿', yoy: '+12.5%', trend: 'up', height: 58, sameHeight: 50, tone: 'green' },
        { org: 'B分公司', value: '0.83亿', samePeriod: '1.02亿', yoy: '-18.6%', trend: 'down', height: 45, sameHeight: 56, tone: 'gold' },
        { org: 'C分公司', value: '0.61亿', samePeriod: '0.55亿', yoy: '+10.9%', trend: 'up', height: 38, sameHeight: 34, tone: 'red' },
      ],
      trendPoints: [
        { period: '09月', value: '2.8', samePeriod: '2.6', height: 50, sameHeight: 47 },
        { period: '10月', value: '3.1', samePeriod: '2.9', height: 57, sameHeight: 53 },
        { period: '11月', value: '2.9', samePeriod: '3.0', height: 53, sameHeight: 55 },
        { period: '12月', value: '3.7', samePeriod: '3.4', height: 72, sameHeight: 66 },
        { period: '01月', value: '3.3', samePeriod: '3.5', height: 62, sameHeight: 66 },
        { period: '02月', value: '3.5', samePeriod: '3.7', height: 65, sameHeight: 69 },
      ],
    },
    {
      key: 'cash',
      label: '现金净流入',
      unit: '亿元',
      current: '2.18亿',
      samePeriod: '1.76亿',
      yoy: '+0.42亿',
      direction: 'up',
      comparison: [
        { org: 'XXX集团', value: '2.18亿', samePeriod: '1.76亿', yoy: '+23.9%', trend: 'up', height: 68, sameHeight: 55, tone: 'blue' },
        { org: 'A分公司', value: '0.72亿', samePeriod: '0.61亿', yoy: '+18.0%', trend: 'up', height: 52, sameHeight: 44, tone: 'green' },
        { org: 'B分公司', value: '0.44亿', samePeriod: '0.58亿', yoy: '-24.1%', trend: 'down', height: 36, sameHeight: 47, tone: 'gold' },
        { org: 'C分公司', value: '0.38亿', samePeriod: '0.31亿', yoy: '+22.6%', trend: 'up', height: 32, sameHeight: 26, tone: 'red' },
      ],
      trendPoints: [
        { period: '09月', value: '1.22', samePeriod: '1.08', height: 42, sameHeight: 37 },
        { period: '10月', value: '1.46', samePeriod: '1.19', height: 50, sameHeight: 41 },
        { period: '11月', value: '1.61', samePeriod: '1.34', height: 55, sameHeight: 46 },
        { period: '12月', value: '1.92', samePeriod: '1.57', height: 66, sameHeight: 54 },
        { period: '01月', value: '1.78', samePeriod: '1.60', height: 61, sameHeight: 55 },
        { period: '02月', value: '2.18', samePeriod: '1.76', height: 75, sameHeight: 60 },
      ],
    },
  ];

  profitBars: MiniBar[] = [
    { label: '营业收入', value: '28.46亿', width: 100, tone: 'blue' },
    { label: '营业成本', value: '17.92亿', width: 63, tone: 'red' },
    { label: '期间费用', value: '7.58亿', width: 27, tone: 'gold' },
    { label: '净利润', value: '3.52亿', width: 12, tone: 'green' },
  ];

  balanceGroups = [
    {
      title: '资产构成',
      total: '19.68亿',
      items: [
        { label: '流动资产', value: '5.63亿', width: 40, tone: 'green' as const },
        { label: '非流动资产', value: '14.05亿', width: 100, tone: 'blue' as const },
      ],
    },
    {
      title: '负债构成',
      total: '6.79亿',
      items: [
        { label: '流动负债', value: '6.22亿', width: 92, tone: 'red' as const },
        { label: '长期负债', value: '0.57亿', width: 18, tone: 'slate' as const },
      ],
    },
  ];

  trendPoints: TrendPoint[] = [
    { period: '09月', revenue: 54, profit: 38, cash: 25 },
    { period: '10月', revenue: 62, profit: 45, cash: 31 },
    { period: '11月', revenue: 58, profit: 39, cash: 34 },
    { period: '12月', revenue: 76, profit: 52, cash: 48 },
    { period: '01月', revenue: 69, profit: 44, cash: 37 },
    { period: '02月', revenue: 82, profit: 47, cash: 55 },
  ];

  statementRows: StatementRow[] = [
    { item: '应收账款', current: '1.12亿', previous: '0.98亿', delta: '+14.3%', trend: 'up' },
    { item: '应付账款', current: '1.32亿', previous: '1.41亿', delta: '-6.4%', trend: 'down' },
    { item: '存货额', current: '1.27亿', previous: '1.09亿', delta: '+16.5%', trend: 'up' },
    { item: '销售费用', current: '1.64亿', previous: '1.71亿', delta: '-4.1%', trend: 'down' },
    { item: '管理费用', current: '1.90亿', previous: '1.86亿', delta: '+2.2%', trend: 'up' },
  ];

  get selectedMetric(): IndicatorMetric {
    return this.indicatorMetrics.find(metric => metric.key === this.selectedMetricKey) ?? this.indicatorMetrics[0];
  }

  trendArrow(trend: Trend): string {
    return trend === 'up' ? '▲' : trend === 'down' ? '▼' : '■';
  }

  trendClass(trend: Trend): string {
    return `trend-${trend}`;
  }
}
