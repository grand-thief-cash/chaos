import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ArtemisBiService } from '../services/artemis-bi.service';
import { BIDupontResponse, BIDupontMetricNode, DupontPeriodKind } from '../models/bi-simple.models';

type TrendDirection = 'up' | 'down' | 'flat';
type NodeTone = 'navy' | 'blue' | 'sky' | 'pale' | 'slate';

interface DupontMetricNode {
  label: string;
  current: string;
  prev?: string;
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
  prev: string;
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

interface NodeLayout {
  id: string;
  tone: NodeTone;
  x: number;
  y: number;
  width?: number;
  compact?: boolean;
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
          <span class="update-date">{{ securityName ? securityName + ' · ' : '' }}{{ updateDate }}</span>
        </div>
        <div class="filter-row" aria-label="杜邦分析筛选条件">
          <label>
            <span>口径</span>
            <select [(ngModel)]="selectedPeriodKind" (ngModelChange)="onPeriodKindChange()">
              @for (k of periodKindOptions; track k.value) {
                <option [value]="k.value">{{ k.label }}</option>
              }
            </select>
          </label>
          <label>
            <span>报告期</span>
            <select [(ngModel)]="selectedReportingPeriod" (ngModelChange)="onReportingPeriodChange()">
              <option value="">最新</option>
              @for (p of availablePeriodOptions; track p) {
                <option [value]="p">{{ p }}</option>
              }
            </select>
          </label>
          @if (canExtrapolate) {
            <label class="extrapolate-toggle">
              <input type="checkbox" [(ngModel)]="extrapolateQ4" (ngModelChange)="onExtrapolateToggle()" />
              <span>Q3 外推全年</span>
            </label>
          }
          @if (hasExtrapolated) {
            <button type="button" class="view-toggle" (click)="toggleView()">
              切换：{{ viewLabel }}
            </button>
          }
        </div>
      </header>

      @if (loadError) {
        <div class="load-error">{{ loadError }}</div>
      }

      <div class="summary-strip">
        @for (item of headlineDrivers; track item.label) {
          <article class="summary-item" [class]="trendClass(item.direction)">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            @if (item.prev && item.prev !== '--') {
              <small class="prev-line">上期 {{ item.prev }}</small>
            }
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

      <section class="calc-notes" aria-label="ROE 取数与计算说明">
        <header>
          <h2>ROE 取数与计算说明</h2>
          <span>当前口径：{{ periodKindLabel }}</span>
        </header>
        <div class="calc-grid">
          <article>
            <h3>TTM（滚动12个月，默认）</h3>
            <p>分子：当前累计净利润 + 上年全年净利润 − 上年同期累计净利润（=近4个单季之和）。</p>
            <p>分母：平均资产/权益 = (本期末 + 上年末) / 2。</p>
            <p class="muted">跨期可比，最稳健，适合看当前盈利能力与趋势。</p>
          </article>
          <article>
            <h3>年度</h3>
            <p>分子：年报全年累计净利润。</p>
            <p>分母：平均资产/权益 = (本年末 + 上年末) / 2。</p>
            <p class="muted">仅年报口径可比；季度传入时回退到最新年报。</p>
          </article>
          <article>
            <h3>单季度</h3>
            <p>分子：本期累计净利润 − 同年上一报告期累计（Q1 直接用累计，无上期）。</p>
            <p>分母：平均资产/权益 = (本期末 + 上季度末) / 2。</p>
            <p class="muted">看单季环比、经营拐点。</p>
          </article>
          <article>
            <h3>YTD（年初至今累计）</h3>
            <p>分子：年初至今累计净利润（不年化）。</p>
            <p>分母：平均资产/权益 = (本期末 + 上年末) / 2。</p>
            <p class="muted">看今年已赚多少；越往后累计越大，跨期不可比。</p>
          </article>
        </div>
        <div class="calc-extra">
          <strong>Q3 外推全年：</strong>
          当口径为 YTD 且报告期为三季报（Q3）时可勾选，按 Q3 YTD × 4/3 线性外推全年净利润/收入，资产/权益沿用 YTD 期初期末平均，估算全年 ROE。
          <span class="muted">（线性外推假设 Q4 与前三季均速一致，仅作预测参考。）</span>
        </div>
        <div class="calc-extra">
          <strong>杜邦恒等式：</strong> ROE = 销售净利率 × 总资产周转率 × 权益乘数；权益乘数 = 1 / (1 − 资产负债率)。所有口径下恒等式均成立。
        </div>
        @if (currentResp?.notes?.length) {
          <ul class="calc-source-notes">
            @for (note of currentResp!.notes; track note) {
              <li>{{ note }}</li>
            }
          </ul>
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

    .extrapolate-toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #fff;
      font-weight: 650;
      cursor: pointer;
    }

    .extrapolate-toggle input {
      width: 16px;
      height: 16px;
      min-width: 16px;
      accent-color: #0f55a5;
    }

    .view-toggle {
      height: 34px;
      padding: 0 14px;
      border: 1px solid rgba(255, 255, 255, 0.6);
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.2);
      color: #fff;
      font-weight: 680;
      font-size: 14px;
      cursor: pointer;
    }

    .view-toggle:hover {
      background: rgba(255, 255, 255, 0.35);
    }

    .calc-notes {
      background: #fff;
      border: 1px solid #e4ebf3;
      padding: 16px 20px;
    }

    .calc-notes header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 12px;
    }

    .calc-notes h2 {
      margin: 0;
      font-size: 18px;
      color: #17233c;
    }

    .calc-notes header span {
      color: #1d5fae;
      font-weight: 680;
      font-size: 13px;
    }

    .calc-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .calc-grid article {
      padding: 12px 14px;
      background: #f8fbff;
      border: 1px solid #e6edf6;
      border-left: 3px solid #1684f5;
    }

    .calc-grid h3 {
      margin: 0 0 6px;
      font-size: 15px;
      color: #152033;
    }

    .calc-grid p {
      margin: 3px 0;
      font-size: 13px;
      line-height: 1.5;
      color: #2c3a4d;
    }

    .calc-grid p.muted,
    .muted {
      color: #637186;
    }

    .calc-extra {
      margin-top: 12px;
      padding: 10px 12px;
      background: #f5f8fc;
      border: 1px dashed #cfdcec;
      font-size: 13px;
      line-height: 1.6;
      color: #2c3a4d;
    }

    .calc-source-notes {
      margin: 10px 0 0;
      padding-left: 18px;
      color: #637186;
      font-size: 12px;
      line-height: 1.6;
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

    .load-error {
      padding: 12px 16px;
      background: #fff1f0;
      border: 1px solid #ffccc7;
      color: #cf1322;
      font-weight: 650;
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

    .prev-line {
      color: #1d5fae;
      font-weight: 680;
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
export class DupontAnalysisPageComponent implements OnInit {
  private readonly bi = inject(ArtemisBiService);

  // Hard-coded for the first integration: only 000021 (深科技) has full
  // financial data from 2015. Parameters will be wired to the filter row later.
  private readonly symbol = '000021';
  private readonly source = 'amazing_data';

  organizations = ['上市公司合并口径'];
  selectedOrg = this.organizations[0];
  startMonth = '2024-01';
  endMonth = '2024-02';

  // Period-kind selector (默认 TTM). Each kind's calculation is documented
  // in the calc-notes panel at the bottom of the page.
  periodKindOptions: Array<{ value: DupontPeriodKind; label: string }> = [
    { value: 'ttm', label: 'TTM（滚动12个月）' },
    { value: 'annual', label: '年度' },
    { value: 'single_quarter', label: '单季度' },
    { value: 'ytd', label: 'YTD（年初至今累计）' },
  ];
  selectedPeriodKind: DupontPeriodKind = 'ttm';

  // Available reporting periods for 深科技 (2015–2026, 年报 + 季报).
  // Static for this first integration; later derived from coverage API.
  // annual口径只能用年报(12-31)；其余口径可用任意报告期。availablePeriodOptions
  // getter 按当前口径过滤，避免选了不可算的报告期。
  private allPeriodOptions: string[] = [
    '2026-03-31', '2025-12-31', '2025-09-30', '2025-06-30', '2025-03-31',
    '2024-12-31', '2024-09-30', '2024-06-30', '2024-03-31',
    '2023-12-31', '2023-09-30', '2023-06-30', '2023-03-31',
    '2022-12-31', '2021-12-31', '2020-12-31', '2019-12-31',
    '2018-12-31', '2017-12-31', '2016-12-31', '2015-12-31',
  ];
  selectedReportingPeriod = '';

  get availablePeriodOptions(): string[] {
    if (this.selectedPeriodKind === 'annual') {
      return this.allPeriodOptions.filter((p) => p.endsWith('-12-31'));
    }
    return this.allPeriodOptions;
  }

  // Q4 extrapolation only applies to YTD + Q3.
  extrapolateQ4 = false;
  // When extrapolated_full_year is present, toggle between actual YTD view
  // and predicted full-year view.
  hasExtrapolated = false;
  showExtrapolated = false;
  // Current response (kept so the toggle can swap views without re-fetching).
  currentResp: BIDupontResponse | null = null;

  // Update-date + period label reflect the latest loaded period.
  updateDate = '加载中…';
  securityName = '';

  // Canvas geometry (unchanged from the mockup). Node ids map to artemis
  // node codes: roe / roa / equity_multiplier / net_margin / asset_turnover /
  // debt_ratio / net_profit / revenue / turnover_revenue / total_assets /
  // total_liabilities / total_assets_right.
  private readonly nodeLayout: NodeLayout[] = [
    { id: 'roe', tone: 'navy', x: 650, y: 0, width: 220 },
    { id: 'roa', tone: 'blue', x: 350, y: 190, width: 220 },
    { id: 'equity_multiplier', tone: 'blue', x: 1010, y: 190, width: 220 },
    { id: 'net_margin', tone: 'sky', x: 150, y: 362, width: 220 },
    { id: 'asset_turnover', tone: 'sky', x: 560, y: 362, width: 220 },
    { id: 'debt_ratio', tone: 'sky', x: 1010, y: 362, width: 220 },
    { id: 'net_profit', tone: 'pale', x: 75, y: 518, width: 160, compact: true },
    { id: 'revenue', tone: 'pale', x: 325, y: 518, width: 160, compact: true },
    { id: 'turnover_revenue', tone: 'pale', x: 495, y: 518, width: 160, compact: true },
    { id: 'total_assets', tone: 'pale', x: 765, y: 518, width: 160, compact: true },
    { id: 'total_liabilities', tone: 'pale', x: 930, y: 518, width: 160, compact: true },
    { id: 'total_assets_right', tone: 'pale', x: 1280, y: 518, width: 160, compact: true },
  ];

  // Label overrides for nodes whose artemis label needs a canvas-specific name.
  private readonly nodeLabels: Record<string, string> = {
    turnover_revenue: '营业收入',
    total_assets: '资产总额',
    total_liabilities: '负债总额',
    total_assets_right: '资产总额',
  };

  nodes: Record<string, DupontMetricNode> = {};

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

  headlineDrivers: DriverItem[] = [];
  detailEquations: DetailEquation[] = [];
  detailStacks: DetailStack[] = [];
  loadError: string | null = null;

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loadError = null;
    this.updateDate = '加载中…';
    const opts: Parameters<ArtemisBiService['getDupont']>[1] = {
      source: this.source,
      period_kind: this.selectedPeriodKind,
    };
    if (this.selectedReportingPeriod) opts.target_reporting_period = this.selectedReportingPeriod;
    if (this.extrapolateQ4 && this.canExtrapolate) opts.extrapolate_q4 = true;
    this.bi.getDupont(this.symbol, opts).subscribe({
      next: (resp) => {
        this.currentResp = resp;
        this.hasExtrapolated = !!resp.extrapolated_full_year;
        this.showExtrapolated = this.hasExtrapolated && this.showExtrapolated;
        this.applyResponse(this.showExtrapolated && resp.extrapolated_full_year ? resp.extrapolated_full_year : resp);
      },
      error: (err) => {
        this.loadError = '杜邦数据加载失败';
        this.updateDate = '加载失败';
        console.error('dupont load failed', err);
      },
    });
  }

  /**
   * Whether the Q4 extrapolation checkbox is applicable: YTD + a Q3 period.
   * A Q3 period is either an explicitly selected 三季报 (reporting period ends
   * -09-30) or, when "最新" is selected, the latest loaded period resolving to
   * report_type 3 (三季报).
   */
  get canExtrapolate(): boolean {
    if (this.selectedPeriodKind !== 'ytd') return false;
    if (this.selectedReportingPeriod) {
      return this.selectedReportingPeriod.endsWith('-09-30');
    }
    // "最新": allow when the latest loaded period is itself a Q3 report.
    return this.currentResp?.report_type === '3';
  }

  onPeriodKindChange(): void {
    // annual 口径只能用年报(12-31)；若当前选的是季报，回退到"最新"。
    if (this.selectedPeriodKind === 'annual'
        && this.selectedReportingPeriod
        && !this.selectedReportingPeriod.endsWith('-12-31')) {
      this.selectedReportingPeriod = '';
    }
    // Reset extrapolation when leaving the YTD+Q3 case.
    if (!this.canExtrapolate) {
      this.extrapolateQ4 = false;
      this.showExtrapolated = false;
    }
    this.load();
  }

  onReportingPeriodChange(): void {
    if (!this.canExtrapolate) {
      this.extrapolateQ4 = false;
      this.showExtrapolated = false;
    }
    this.load();
  }

  onExtrapolateToggle(): void {
    this.showExtrapolated = this.extrapolateQ4;
    this.load();
  }

  toggleView(): void {
    if (!this.currentResp?.extrapolated_full_year) return;
    this.showExtrapolated = !this.showExtrapolated;
    this.applyResponse(this.showExtrapolated ? this.currentResp.extrapolated_full_year! : this.currentResp);
  }

  get viewLabel(): string {
    return this.showExtrapolated ? '预测全年（Q3 YTD × 4/3）' : '实际';
  }

  get periodKindLabel(): string {
    return this.periodKindOptions.find((k) => k.value === this.selectedPeriodKind)?.label ?? this.selectedPeriodKind;
  }

  private applyResponse(resp: BIDupontResponse): void {
    this.securityName = resp.security_name ?? '';
    if (!resp.period) {
      this.updateDate = '';
    } else if (this.showExtrapolated) {
      // Extrapolated full-year view: period is still the Q3 reporting date, so
      // label it as a forecast derived from that period, not an actual report.
      this.updateDate = `预测全年（基于报告期 ${resp.period} × 4/3）`;
    } else {
      this.updateDate = `报告期：${resp.period}`;
    }
    this.nodes = this.buildNodes(resp.nodes);
    this.headlineDrivers = (resp.headline_drivers ?? []).map((d) => ({
      label: d.label,
      value: this.formatValue(d.value, d.unit),
      prev: this.formatValue(d.prev_value, d.unit),
      note: d.note,
      direction: (d.direction ?? 'flat') as TrendDirection,
    }));
    this.detailEquations = (resp.detail_equations ?? []).map((e) => ({
      result: `${e.result_label} ${this.formatValue(e.result_value, e.unit)}`,
      expression: e.expression,
      note: e.note,
    }));
    this.detailStacks = (resp.detail_stacks ?? []).map((s) => ({
      title: s.title,
      total: this.formatAmount(s.total),
      accent: s.accent,
      rows: (s.rows ?? []).map((r) => ({ label: r.label, value: this.formatAmount(r.value) })),
    }));
  }

  private buildNodes(src: Record<string, BIDupontMetricNode>): Record<string, DupontMetricNode> {
    const out: Record<string, DupontMetricNode> = {};
    for (const layout of this.nodeLayout) {
      const raw = src[layout.id];
      out[layout.id] = {
        label: this.nodeLabels[layout.id] ?? raw?.label ?? layout.id,
        current: raw ? this.formatValue(raw.value, raw.unit) : '--',
        prev: raw && raw.prev_value != null ? this.formatValue(raw.prev_value, raw.unit) : undefined,
        delta: raw ? this.formatDelta(raw.delta, raw.unit) : undefined,
        direction: (raw?.direction ?? undefined) as TrendDirection | undefined,
        tone: layout.tone,
      };
    }
    return out;
  }

  get positionedNodes(): PositionedNode[] {
    return this.nodeLayout.map((layout) => ({
      id: layout.id,
      node: this.nodes[layout.id] ?? { label: layout.id, current: '--', tone: layout.tone },
      x: layout.x,
      y: layout.y,
      width: layout.width,
      compact: layout.compact,
    }));
  }

  // ─── Formatting: artemis returns yuan + 0-1 ratios; the page renders 亿 / % ───

  private formatValue(v: number | null, unit: string): string {
    if (v == null) return '--';
    return unit === 'amount_yuan' ? this.formatAmount(v) : this.formatRatio(v);
  }

  private formatAmount(v: number | null): string {
    if (v == null) return '--';
    return `${(v / 1e8).toFixed(2)}亿`;
  }

  private formatRatio(v: number | null): string {
    if (v == null) return '--';
    return `${(v * 100).toFixed(2)}%`;
  }

  private formatDelta(d: number | null, unit: string): string {
    if (d == null) return '';
    const scaled = unit === 'amount_yuan' ? d / 1e8 : d * 100;
    const sign = scaled > 0 ? '+' : '';
    return `${sign}${scaled.toFixed(2)}${unit === 'amount_yuan' ? '亿' : 'pct'}`;
  }

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
