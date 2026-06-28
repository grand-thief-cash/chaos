import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type TrendDirection = 'up' | 'down' | 'flat';
type NodeTone = 'navy' | 'blue' | 'sky' | 'pale' | 'slate';

interface DupontMetricNode {
  label: string;
  current: string;
  delta?: string;
  direction?: TrendDirection;
  tone: NodeTone;
}

interface DetailStack {
  title: string;
  total: string;
  accent: string;
  rows: Array<{ label: string; value: string }>;
}

interface DetailEquation {
  result: string;
  expression: string;
  note: string;
}

interface DriverItem {
  label: string;
  value: string;
  note: string;
  direction: TrendDirection;
}

interface PositionedNode {
  id: string;
  node: DupontMetricNode;
  x: number;
  y: number;
  width?: number;
  compact?: boolean;
}

interface CanvasConnector {
  id: string;
  direction: 'vertical' | 'horizontal';
  x: number;
  y: number;
  length: number;
}

interface CanvasOperator {
  id: string;
  text: string;
  x: number;
  y: number;
  size?: number;
  dark?: boolean;
}

@Component({
  selector: 'app-bi-dupont-analysis-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="dupont-page">
      <header class="dashboard-header">
        <div class="title-block">
          <h1>杜邦分析</h1>
          <span class="update-date">更新日期：2024年4月8日</span>
        </div>
        <div class="filter-row" aria-label="杜邦分析筛选条件">
          <label>
            <span>组织</span>
            <select [(ngModel)]="selectedOrg">
              @for (org of organizations; track org) {
                <option [value]="org">{{ org }}</option>
              }
            </select>
          </label>
          <label>
            <span>年月</span>
            <input type="month" [(ngModel)]="startMonth" />
          </label>
          <span class="range-separator">-</span>
          <label class="month-only">
            <span>结束年月</span>
            <input type="month" [(ngModel)]="endMonth" />
          </label>
        </div>
      </header>

      <div class="summary-strip">
        @for (item of headlineDrivers; track item.label) {
          <article class="summary-item" [class]="trendClass(item.direction)">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.note }}</small>
          </article>
        }
      </div>

      <div class="canvas-scroll" aria-label="杜邦分析指标树">
        <div class="dupont-canvas">
          @for (line of connectors; track line.id) {
            <div
              class="connector"
              [class.vertical]="line.direction === 'vertical'"
              [class.horizontal]="line.direction === 'horizontal'"
              [style.left.px]="line.x"
              [style.top.px]="line.y"
              [style.width.px]="line.direction === 'horizontal' ? line.length : null"
              [style.height.px]="line.direction === 'vertical' ? line.length : null">
            </div>
          }

          @for (op of operators; track op.id) {
            <span
              class="operator"
              [class.dark]="op.dark"
              [style.left.px]="op.x"
              [style.top.px]="op.y"
              [style.font-size.px]="op.size">
              {{ op.text }}
            </span>
          }

          @for (item of positionedNodes; track item.id) {
            <article
              class="metric-node tone-{{ item.node.tone }}"
              [class.compact]="item.compact"
              [style.left.px]="item.x"
              [style.top.px]="item.y"
              [style.width.px]="item.width">
              <header>{{ item.node.label }}</header>
              <div class="metric-values single">
                <div>
                  <strong>{{ item.node.current }}</strong>
                  @if (nodeTrendDirection(item.node); as direction) {
                    @if (direction !== 'flat') {
                      <span class="trend" [class]="trendClass(direction)">{{ trendArrow(direction) }}</span>
                    }
                    @if (item.node.delta) {
                      <span class="metric-delta">{{ item.node.delta }}</span>
                    }
                  }
                </div>
              </div>
            </article>
          }
        </div>
      </div>

      <section class="relationship-grid" aria-label="杜邦分析明细关系">
        @for (item of detailEquations; track item.result) {
          <article class="relationship-card">
            <strong>{{ item.result }}</strong>
            <span>{{ item.expression }}</span>
            <small>{{ item.note }}</small>
          </article>
        }
      </section>

      <section class="breakdown-grid" aria-label="杜邦分析明细拆解">
        @for (stack of detailStacks; track stack.title) {
          <article class="detail-stack" [style.--stack-accent]="stack.accent">
            <header>
              <span>{{ stack.title }}</span>
              <strong>{{ stack.total }}</strong>
            </header>
            @for (row of stack.rows; track row.label) {
              <div class="detail-row">
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </div>
            }
          </article>
        }
      </section>
    </section>

  `,
  styles: [`
    :host {
      display: block;
      background: #f3f6fb;
      min-height: calc(100vh - 110px);
    }

    .dupont-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
      color: #152033;
    }

    .dashboard-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 24px;
      min-height: 86px;
      padding: 18px 28px;
      background: linear-gradient(100deg, #1f72e8 0%, #6fb7f2 48%, #b9e7e5 100%);
      color: #fff;
      box-shadow: 0 8px 22px rgba(24, 86, 150, 0.16);
    }

    .title-block {
      display: flex;
      align-items: baseline;
      gap: 26px;
      min-width: 0;
    }

    h1 {
      margin: 0;
      font-size: 32px;
      line-height: 1.15;
      font-weight: 760;
      letter-spacing: 0;
      white-space: nowrap;
    }

    .update-date {
      font-size: 16px;
      font-weight: 600;
      opacity: 0.95;
      white-space: nowrap;
    }

    .filter-row {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      flex-wrap: wrap;
    }

    .filter-row label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 650;
      color: #203047;
    }

    select,
    input {
      height: 34px;
      border: 1px solid rgba(34, 72, 112, 0.26);
      background: rgba(255, 255, 255, 0.45);
      color: #1b2a3c;
      padding: 0 10px;
      border-radius: 4px;
      font-weight: 620;
      min-width: 126px;
      outline: none;
    }

    input {
      min-width: 140px;
    }

    .range-separator {
      color: #203047;
      font-weight: 760;
    }

    .summary-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(180px, 1fr));
      gap: 12px;
    }

    .summary-item {
      min-height: 86px;
      padding: 14px 16px;
      background: #fff;
      border: 1px solid #e5ebf2;
      border-left: 4px solid #4b8ff0;
    }

    .summary-item span,
    .summary-item small {
      display: block;
      color: #637186;
      font-size: 12px;
      line-height: 1.5;
    }

    .summary-item strong {
      display: block;
      margin: 4px 0;
      font-size: 24px;
      line-height: 1.1;
      color: #17233c;
    }

    .canvas-scroll {
      overflow-x: auto;
      background: #fff;
      border: 1px solid #e4ebf3;
    }

    .dupont-canvas {
      position: relative;
      min-width: 1500px;
      height: 660px;
      background: #fff;
    }

    .metric-node {
      position: absolute;
      width: 190px;
      min-height: 76px;
      border: 1px solid #c7d2df;
      background: #fff;
      z-index: 2;
    }

    .metric-node header {
      height: 34px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 8px;
      color: #fff;
      font-weight: 760;
      font-size: 14px;
      text-align: center;
      background: #2b8ff0;
    }

    .metric-values {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      min-height: 42px;
    }

    .metric-values.single {
      grid-template-columns: 1fr;
    }

    .metric-values div {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-width: 0;
      border-left: 1px solid #e3e8ef;
      font-size: 14px;
    }

    .metric-values div:first-child {
      border-left: 0;
    }

    .metric-values strong {
      color: #0b1220;
      font-size: 15px;
      line-height: 1;
      white-space: nowrap;
    }

    .metric-delta {
      color: #667386;
      font-size: 12px;
      white-space: nowrap;
    }

    .trend {
      font-size: 18px;
      line-height: 1;
      font-weight: 800;
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

    .tone-navy header {
      background: #0f55a5;
    }

    .tone-blue header {
      background: #1684f5;
    }

    .tone-sky header {
      background: #4099f5;
    }

    .tone-pale header {
      background: #75b2f1;
    }

    .connector {
      position: absolute;
      background: #1684f5;
      border-radius: 2px;
      z-index: 1;
    }

    .vertical {
      width: 5px;
    }

    .horizontal {
      height: 5px;
    }

    .operator {
      position: absolute;
      color: #78b7f5;
      font-size: 48px;
      line-height: 1;
      font-weight: 300;
      z-index: 2;
      user-select: none;
    }

    .operator.dark {
      color: #0b1220;
      font-weight: 500;
    }

    .relationship-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(190px, 1fr));
      gap: 12px;
    }

    .relationship-card {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 12px 14px;
      background: #fff;
      border: 1px solid #dfe7f0;
    }

    .relationship-card strong {
      color: #17233c;
      font-size: 16px;
    }

    .relationship-card span {
      color: #1d5fae;
      font-weight: 650;
    }

    .relationship-card small {
      color: #667386;
    }

    .breakdown-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(170px, 1fr));
      gap: 12px;
    }

    .detail-stack {
      background: #fff;
      border: 1px solid #dfe7f0;
      border-top: 4px solid var(--stack-accent);
    }

    .detail-stack header {
      display: flex;
      flex-direction: column;
      gap: 3px;
      padding: 12px 14px;
      border-bottom: 1px solid #e6edf4;
      background: #f8fbff;
    }

    .detail-stack header span {
      color: #637186;
      font-size: 12px;
    }

    .detail-stack header strong {
      color: #152033;
      font-size: 20px;
      line-height: 1.1;
    }

    .detail-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 14px;
      border-bottom: 1px solid #edf2f7;
      min-height: 41px;
      font-size: 13px;
    }

    .detail-row:last-child {
      border-bottom: 0;
    }

    .detail-row span {
      color: #536273;
    }

    .detail-row strong {
      color: #0b1220;
      white-space: nowrap;
    }

    @media (max-width: 1200px) {
      .dashboard-header {
        align-items: flex-start;
        flex-direction: column;
      }

      .filter-row {
        justify-content: flex-start;
      }

      .summary-strip {
        grid-template-columns: repeat(2, minmax(180px, 1fr));
      }

      .breakdown-grid {
        grid-template-columns: repeat(3, minmax(170px, 1fr));
      }

      .relationship-grid {
        grid-template-columns: repeat(2, minmax(190px, 1fr));
      }
    }

    @media (max-width: 720px) {
      .dupont-page {
        gap: 12px;
      }

      .dashboard-header {
        padding: 16px;
      }

      .title-block {
        align-items: flex-start;
        flex-direction: column;
        gap: 8px;
      }

      h1 {
        font-size: 26px;
      }

      .summary-strip,
      .breakdown-grid,
      .relationship-grid {
        grid-template-columns: 1fr;
      }

      .filter-row label,
      select,
      input {
        width: 100%;
      }

      .range-separator {
        display: none;
      }
    }
  `],
})
export class DupontAnalysisPageComponent {
  organizations = ['XXX集团', '华东事业群', '上市公司合并口径'];
  selectedOrg = this.organizations[0];
  startMonth = '2024-01';
  endMonth = '2024-02';

  nodes = {
    roe: {
      label: '净资产收益率',
      current: '116.13%',
      delta: '-35.55pct',
      direction: 'down',
      tone: 'navy',
    },
    assetProfit: {
      label: '总资产利润率',
      current: '67.10%',
      delta: '-25.70pct',
      direction: 'down',
      tone: 'blue',
    },
    equityMultiplier: {
      label: '权益乘数',
      current: '1.73',
      delta: '+0.35',
      direction: 'up',
      tone: 'blue',
    },
    salesMargin: {
      label: '销售净利率',
      current: '419.80%',
      delta: '-78.30pct',
      direction: 'down',
      tone: 'sky',
    },
    assetTurnover: {
      label: '总资产周转率',
      current: '15.98%',
      delta: '-16.84pct',
      direction: 'down',
      tone: 'sky',
    },
    debtRatio: {
      label: '资产负债率',
      current: '42.22%',
      delta: '+14.52pct',
      direction: 'up',
      tone: 'sky',
    },
    netProfit: { label: '净利润', current: '3.52亿', tone: 'pale' },
    revenue: { label: '营业收入', current: '4.90亿', tone: 'pale' },
    turnoverRevenue: { label: '营业收入', current: '4.90亿', tone: 'pale' },
    totalAssets: { label: '资产总额', current: '19.68亿', tone: 'pale' },
    totalLiabilities: { label: '负债总额', current: '6.79亿', tone: 'pale' },
    totalAssetsRight: { label: '资产总额', current: '19.68亿', tone: 'pale' },
  } satisfies Record<string, DupontMetricNode>;

  connectors: CanvasConnector[] = [
    { id: 'roe-down', direction: 'vertical', x: 747, y: 78, length: 58 },
    { id: 'roe-branch', direction: 'horizontal', x: 455, y: 134, length: 665 },
    { id: 'profit-up', direction: 'vertical', x: 455, y: 134, length: 56 },
    { id: 'multiplier-up', direction: 'vertical', x: 1115, y: 134, length: 56 },
    { id: 'profit-down', direction: 'vertical', x: 455, y: 266, length: 56 },
    { id: 'profit-branch', direction: 'horizontal', x: 245, y: 320, length: 420 },
    { id: 'margin-up', direction: 'vertical', x: 245, y: 320, length: 42 },
    { id: 'turnover-up', direction: 'vertical', x: 665, y: 320, length: 42 },
    { id: 'multiplier-down', direction: 'vertical', x: 1120, y: 266, length: 96 },
    { id: 'margin-down', direction: 'vertical', x: 245, y: 438, length: 48 },
    { id: 'margin-branch', direction: 'horizontal', x: 155, y: 484, length: 250 },
    { id: 'net-profit-up', direction: 'vertical', x: 155, y: 484, length: 34 },
    { id: 'revenue-up', direction: 'vertical', x: 405, y: 484, length: 34 },
    { id: 'turnover-down', direction: 'vertical', x: 665, y: 438, length: 48 },
    { id: 'turnover-branch', direction: 'horizontal', x: 575, y: 484, length: 270 },
    { id: 'turnover-revenue-up', direction: 'vertical', x: 575, y: 484, length: 34 },
    { id: 'turnover-asset-up', direction: 'vertical', x: 845, y: 484, length: 34 },
    { id: 'debt-down', direction: 'vertical', x: 1120, y: 438, length: 48 },
    { id: 'debt-branch', direction: 'horizontal', x: 1010, y: 484, length: 350 },
    { id: 'liabilities-up', direction: 'vertical', x: 1010, y: 484, length: 34 },
    { id: 'right-assets-up', direction: 'vertical', x: 1360, y: 484, length: 34 },
  ];

  operators: CanvasOperator[] = [
    { id: 'profit', text: '×', x: 450, y: 377 },
    { id: 'margin', text: '÷', x: 265, y: 533 },
    { id: 'turnover', text: '÷', x: 695, y: 533 },
    { id: 'liability', text: '÷', x: 1170, y: 533 },
    { id: 'equity', text: '1 ÷ ( 1 -', x: 875, y: 386, size: 30, dark: true },
    { id: 'equity-close', text: ')', x: 1252, y: 384, size: 34, dark: true },
  ];

  positionedNodes: PositionedNode[] = [
    { id: 'roe', node: this.nodes.roe, x: 650, y: 0, width: 220 },
    { id: 'asset-profit', node: this.nodes.assetProfit, x: 350, y: 190, width: 220 },
    { id: 'equity-multiplier', node: this.nodes.equityMultiplier, x: 1010, y: 190, width: 220 },
    { id: 'sales-margin', node: this.nodes.salesMargin, x: 150, y: 362, width: 220 },
    { id: 'asset-turnover', node: this.nodes.assetTurnover, x: 560, y: 362, width: 220 },
    { id: 'debt-ratio', node: this.nodes.debtRatio, x: 1010, y: 362, width: 220 },
    { id: 'net-profit', node: this.nodes.netProfit, x: 75, y: 518, width: 160, compact: true },
    { id: 'revenue', node: this.nodes.revenue, x: 325, y: 518, width: 160, compact: true },
    { id: 'turnover-revenue', node: this.nodes.turnoverRevenue, x: 495, y: 518, width: 160, compact: true },
    { id: 'total-assets', node: this.nodes.totalAssets, x: 765, y: 518, width: 160, compact: true },
    { id: 'total-liabilities', node: this.nodes.totalLiabilities, x: 930, y: 518, width: 160, compact: true },
    { id: 'total-assets-right', node: this.nodes.totalAssetsRight, x: 1280, y: 518, width: 160, compact: true },
  ];

  headlineDrivers: DriverItem[] = [
    { label: 'ROE', value: '116.13%', note: '较上期提升 151.68pct', direction: 'up' },
    { label: '销售净利率', value: '419.80%', note: '投资收益拉动利润端', direction: 'up' },
    { label: '总资产周转率', value: '15.98%', note: '资产扩张快于收入', direction: 'down' },
    { label: '资产负债率', value: '42.22%', note: '杠杆贡献保持温和', direction: 'flat' },
  ];

  detailEquations: DetailEquation[] = [
    {
      result: '净利润 3.52亿',
      expression: '收入总额 25.28亿 - 成本总额 21.76亿',
      note: '销售净利率的利润端来源',
    },
    {
      result: '成本总额 21.76亿',
      expression: '主营成本 + 期间费用 + 税费及其他损益',
      note: '用于解释净利润被哪些成本项消耗',
    },
    {
      result: '资产总额 19.68亿',
      expression: '流动资产 5.63亿 + 非流动资产 14.05亿',
      note: '总资产周转率与资产负债率共用的分母',
    },
    {
      result: '资产负债率 42.22%',
      expression: '负债总额 6.79亿 / 资产总额 19.68亿',
      note: '权益乘数由 1 / (1 - 资产负债率) 推导',
    },
  ];

  detailStacks: DetailStack[] = [
    {
      title: '收入总额',
      total: '25.28亿',
      accent: '#1684f5',
      rows: [
        { label: '主营业务收入', value: '4.90亿' },
        { label: '其他业务收入', value: '2.94亿' },
        { label: '投资收益', value: '4.70亿' },
        { label: '公允价值变动收益', value: '6.13亿' },
        { label: '资产处置收益', value: '6.60亿' },
      ],
    },
    {
      title: '成本总额',
      total: '21.76亿',
      accent: '#e05260',
      rows: [
        { label: '主营业务成本', value: '2.27亿' },
        { label: '其他业务成本', value: '1.70亿' },
        { label: '税金及附加', value: '2.09亿' },
        { label: '期间费用', value: '2.15亿' },
        { label: '资产减值损失', value: '1.54亿' },
      ],
    },
    {
      title: '期间费用',
      total: '7.58亿',
      accent: '#f0a532',
      rows: [
        { label: '销售费用', value: '1.64亿' },
        { label: '管理费用', value: '1.90亿' },
        { label: '研发费用', value: '1.83亿' },
        { label: '财务费用', value: '2.23亿' },
      ],
    },
    {
      title: '流动资产',
      total: '5.63亿',
      accent: '#16a765',
      rows: [
        { label: '货币资金', value: '1.84亿' },
        { label: '应收账款', value: '1.12亿' },
        { label: '预付账款', value: '1.39亿' },
        { label: '存货', value: '1.27亿' },
      ],
    },
    {
      title: '非流动资产',
      total: '14.05亿',
      accent: '#7c5cc4',
      rows: [
        { label: '长期股权投资', value: '0.03亿' },
        { label: '固定资产', value: '3.18亿' },
        { label: '无形资产', value: '0.99亿' },
        { label: '商誉', value: '1.44亿' },
        { label: '递延所得税资产', value: '2.07亿' },
      ],
    },
    {
      title: '负债构成',
      total: '6.79亿',
      accent: '#5b6f86',
      rows: [
        { label: '短期借款', value: '1.99亿' },
        { label: '应付账款', value: '1.32亿' },
        { label: '预收账款', value: '1.39亿' },
        { label: '长期借款', value: '1.24亿' },
        { label: '租赁负债', value: '1.67亿' },
      ],
    },
  ];

  nodeTrendDirection(node: DupontMetricNode): TrendDirection | null {
    return node.direction || null;
  }

  trendArrow(direction: TrendDirection): string {
    return direction === 'up' ? '▲' : direction === 'down' ? '▼' : '';
  }

  trendClass(direction: TrendDirection): string {
    return `trend-${direction}`;
  }
}
