import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import dayjs from 'dayjs';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import {
  ValuationAnalyzeResponse,
  ValuationHistoryResponse,
  ValuationMethodCode,
  ValuationMethodResult,
  ValuationScenario,
} from '../models/workbench.model';
import { WorkbenchApiService } from '../services/workbench-api.service';


@Component({
  selector: 'app-valuation-matrix-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzAlertModule, NzButtonModule, NzCardModule,
    NzCollapseModule, NzDescriptionsModule, NzInputModule, NzInputNumberModule,
    NzSelectModule, NzStatisticModule, NzTableModule, NzTabsModule, NzTagModule,
    SecuritySearchInputComponent,
  ],
  styles: [`
    .page { padding: 16px; }
    .toolbar { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
    .field label { display: block; margin-bottom: 4px; color: #666; font-size: 12px; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 10px; margin: 12px 0; }
    .matrix-cell { min-width: 120px; }
    .matrix-price { display: block; font-size: 18px; font-weight: 600; }
    .matrix-note { display: block; color: #8c8c8c; font-size: 11px; }
    .bear { color: #237804; }
    .base { color: #d46b08; }
    .bull { color: #cf1322; }
    .combined-row td { background: #fafafa; font-weight: 600; }
    .diagnostic-row td { background: #fffbe6; }
    .reference-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 10px 0; }
    .reference-item { padding: 10px; border: 1px solid #f0f0f0; border-radius: 6px; background: #fafafa; }
    .reference-item strong { display: block; margin-bottom: 4px; }
    .usage-rules { margin: 8px 0 0; padding-left: 20px; }
    .diagnostic-status { margin-bottom: 8px; }
    .sensitivity-table { width: 100%; border-collapse: collapse; text-align: center; }
    .sensitivity-table th, .sensitivity-table td { border: 1px solid #f0f0f0; padding: 10px; }
    .sensitivity-table th { background: #fafafa; }
    .nearest-cell { background: #e6f4ff; box-shadow: inset 0 0 0 2px #1677ff; }
    .method-detail { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(280px, 2fr); gap: 16px; }
    .formula { padding: 10px; border-left: 3px solid #1677ff; background: #f0f5ff; }
    pre { margin: 6px 0 0; padding: 8px; overflow: auto; background: #fafafa; font-size: 11px; white-space: pre-wrap; }
    .audit { margin-top: 12px; }
    .muted { color: #8c8c8c; font-size: 12px; }
    .warning-list nz-alert { display: block; margin-top: 8px; }
    @media (max-width: 760px) {
      .page { padding: 8px; }
      .method-detail { grid-template-columns: 1fr; }
    }
  `],
  template: `
    <div class="page">
      <nz-tabset>
        <nz-tab nzTitle="估值矩阵">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field">
                <label>股票代码 / 名称</label>
                <app-security-search-input
                  placeholder="输入 600183 或生益科技"
                  (securitySelected)="onSecuritySelected($event)"
                ></app-security-search-input>
              </div>
              <div class="field">
                <label>估值日期</label>
                <input nz-input type="date" [(ngModel)]="valuationDate" style="width: 145px;" />
              </div>
              <div class="field">
                <label>目标期限</label>
                <nz-select [(ngModel)]="horizonYears" style="width: 110px;">
                  <nz-option [nzValue]="1" nzLabel="1 年"></nz-option>
                  <nz-option [nzValue]="2" nzLabel="2 年"></nz-option>
                  <nz-option [nzValue]="3" nzLabel="3 年"></nz-option>
                </nz-select>
              </div>
              <div class="field">
                <label>历史倍数窗口</label>
                <nz-select [(ngModel)]="historyYears" style="width: 120px;">
                  <nz-option [nzValue]="3" nzLabel="3 年"></nz-option>
                  <nz-option [nzValue]="5" nzLabel="5 年"></nz-option>
                  <nz-option [nzValue]="8" nzLabel="8 年"></nz-option>
                  <nz-option [nzValue]="10" nzLabel="10 年"></nz-option>
                </nz-select>
              </div>
              <div class="field">
                <label>估值方法</label>
                <nz-select [(ngModel)]="selectedMethods" nzMode="multiple" style="min-width: 330px;">
                  @for (option of methodOptions; track option.value) {
                    <nz-option [nzValue]="option.value" [nzLabel]="option.label"></nz-option>
                  }
                </nz-select>
              </div>
              <div class="field">
                <label>安全边际（相对中位锚）</label>
                <nz-input-number
                  [(ngModel)]="marginOfSafetyPercent"
                  [nzMin]="0"
                  [nzMax]="50"
                  [nzStep]="5"
                  style="width: 120px;"
                ></nz-input-number>
              </div>
              <button nz-button nzType="primary" (click)="runAnalysis()" [nzLoading]="loading" [disabled]="!securityId || !selectedMethods.length">
                计算估值矩阵
              </button>
            </div>
          </nz-card>

          @if (result) {
            <div class="summary">
              <nz-card nzSize="small"><nz-statistic nzTitle="市场价格" [nzValue]="result.market_price" nzPrefix="¥"></nz-statistic><span class="muted">最后交易日 {{ result.price_as_of }}</span></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="主区间 · 低一致预期" [nzValue]="result.range.bear ?? '-'" nzPrefix="¥"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="主区间 · 中位一致预期" [nzValue]="result.range.base ?? '-'" nzPrefix="¥"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="主区间 · 高一致预期" [nzValue]="result.range.bull ?? '-'" nzPrefix="¥"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="中位锚空间" [nzValue]="percentValue(result.range.upside_base)" nzSuffix="%"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="安全边际观察价" [nzValue]="observationPrice() ?? '-'" nzPrefix="¥"></nz-statistic><span class="muted">中位锚 × (1 − {{ marginOfSafetyPercent }}%)</span></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="结构 / 数据评分" [nzValue]="result.confidence.score" nzSuffix="/ 100"></nz-statistic><nz-tag [nzColor]="confidenceColor(result.confidence.label)">{{ result.confidence.usage_label }}</nz-tag></nz-card>
            </div>

            @if (result.forward_pe_sensitivity; as sensitivity) {
              <nz-alert
                nzType="info"
                nzShowIcon
                [nzMessage]="aggregationLabel()"
                [nzDescription]="marketImpliedMessage()"
                style="display:block; margin-bottom: 12px;"
              ></nz-alert>
            }

            @if (result.price_reference; as reference) {
              <nz-card nzTitle="这些价格应该怎么参考" nzSize="small" style="margin-bottom: 12px;">
                <div class="diagnostic-status">
                  <nz-tag nzColor="blue">{{ reference.state_label }}</nz-tag>
                  {{ reference.interpretation }}
                </div>
                <div class="reference-grid">
                  <div class="reference-item">
                    <strong>低一致预期 {{ formatPrice(reference.anchors.low_consensus) }}</strong>
                    <span class="muted">预测分布低位 × 历史倍数低位；不是极端压力价，也不是自动买入价。</span>
                  </div>
                  <div class="reference-item">
                    <strong>中位锚 {{ formatPrice(reference.anchors.base_consensus) }}</strong>
                    <span class="muted">用于检验你是否接受中位盈利与中位倍数，是核心比较锚，不是价格承诺。</span>
                  </div>
                  <div class="reference-item">
                    <strong>安全边际观察价 {{ formatPrice(observationPrice()) }}</strong>
                    <span class="muted">按你选择的 {{ marginOfSafetyPercent }}% 折扣计算，仅用于设置观察纪律。</span>
                  </div>
                  <div class="reference-item">
                    <strong>市场隐含假设</strong>
                    <span class="muted">{{ marketImpliedShort() }}</span>
                  </div>
                </div>
                <ol class="usage-rules">
                  @for (rule of reference.usage_rules; track rule) { <li>{{ rule }}</li> }
                </ol>
                <nz-alert nzType="warning" nzShowIcon [nzMessage]="reference.tail_stress_note" style="display:block; margin-top: 10px;"></nz-alert>
              </nz-card>
            }

            <nz-card [nzTitle]="securityDisplay + ' · ' + result.valuation_date + ' · 价格估计矩阵'" nzSize="small">
              <nz-table #matrixTable [nzData]="result.matrix.methods" [nzShowPagination]="false" nzSize="middle" nzBordered>
                <thead>
                  <tr><th>方法 / 权重</th><th>低一致预期</th><th>中位一致预期</th><th>高一致预期</th></tr>
                </thead>
                <tbody>
                  @for (method of matrixTable.data; track method.code) {
                    <tr>
                      <td>
                        <strong>{{ method.label }}</strong>
                        <nz-tag [nzColor]="methodRoleColor(method.role)">{{ methodRoleLabel(method.role) }}</nz-tag>
                        <nz-tag nzColor="orange">{{ methodAssumptionLabel(method) }}</nz-tag>
                        <br><span class="muted">诊断权重 {{ method.weight | percent:'1.0-0' }}{{ method.included_in_headline ? ' · 参与主区间' : ' · 不参与主区间' }}</span>
                      </td>
                      @for (scenario of scenarios; track scenario) {
                        <td class="matrix-cell">
                          <span class="matrix-price" [ngClass]="scenario">{{ formatPrice(method.prices[scenario]) }}</span>
                          <span class="matrix-note">{{ keyInput(method, scenario) }}</span>
                        </td>
                      }
                    </tr>
                  }
                  <tr class="combined-row diagnostic-row">
                    <td>{{ result.matrix.aggregation.mode === 'primary_with_cross_checks' ? '全方法加权参考（仅诊断）' : '加权综合区间' }}</td>
                    @for (scenario of scenarios; track scenario) {
                      <td><span class="matrix-price" [ngClass]="scenario">{{ formatPrice(result.matrix.combined[scenario]) }}</span></td>
                    }
                  </tr>
                </tbody>
              </nz-table>
              <div class="muted">聚合方式：{{ aggregationModeLabel() }}。{{ result.matrix.aggregation.rationale }}</div>
              <div class="muted">权重画像：{{ result.matrix.weight_profile }}。{{ result.matrix.weight_rationale }} 只有输入完整的方法才参与诊断加权。</div>
              @if (result.matrix.unavailable_methods.length) {
                <div style="margin-top: 8px;">
                  @for (method of result.matrix.unavailable_methods; track method.code) {
                    <nz-tag nzColor="orange">{{ methodLabel(method.code) }} 未参与：{{ method.reason }}</nz-tag>
                  }
                </div>
              }
            </nz-card>

            @if (result.forward_pe_sensitivity; as sensitivity) {
              <nz-card nzTitle="Forward PE · EPS × 倍数 3×3 敏感性" nzSize="small" style="margin-top: 12px;">
                <p class="muted">行是 {{ result.point_in_time.target_fiscal_year }}E EPS 情景，列是 PE 情景。主区间使用对角线；完整矩阵把“盈利兑现”和“估值压缩”拆开，避免只看双重悲观/乐观组合。</p>
                <table class="sensitivity-table">
                  <thead>
                    <tr>
                      <th>EPS \ PE</th>
                      @for (peScenario of scenarios; track peScenario) {
                        <th>{{ scenarioLabel(peScenario) }} · {{ valueAt(sensitivity.multiples, peScenario, 4) }}×</th>
                      }
                    </tr>
                  </thead>
                  <tbody>
                    @for (epsScenario of scenarios; track epsScenario) {
                      <tr>
                        <th>{{ scenarioLabel(epsScenario) }} · EPS {{ valueAt(sensitivity.eps, epsScenario, 4) }}</th>
                        @for (peScenario of scenarios; track peScenario) {
                          <td [class.nearest-cell]="isNearestCell(epsScenario, peScenario)">
                            <span class="matrix-price">{{ formatPrice(sensitivity.grid[epsScenario]?.[peScenario]) }}</span>
                            @if (isNearestCell(epsScenario, peScenario)) { <span class="matrix-note">最接近当前价</span> }
                          </td>
                        }
                      </tr>
                    }
                  </tbody>
                </table>
              </nz-card>
            }

            @if (result.diagnostics.pe_pb_coherence; as coherence) {
              <nz-card nzTitle="PE / PB 一致性诊断" nzSize="small" style="margin-top: 12px;">
                <div class="diagnostic-status">
                  <nz-tag [nzColor]="coherenceColor(coherence.status)">{{ coherenceStatusLabel(coherence.status) }}</nz-tag>
                  {{ coherence.interpretation }}
                </div>
                <p class="muted">恒等关系：{{ coherence.identity }}。若 PE 隐含的 PB 明显高于历史 PB 锚，说明增长型盈利定价和账面资产定价讲的是不同故事，不能直接把两者平均。</p>
                <table class="sensitivity-table">
                  <thead><tr><th>情景</th><th>EPS / BVPS</th><th>隐含 ROE</th><th>PE 对应 PB</th><th>历史 PB 锚</th><th>差异倍数</th></tr></thead>
                  <tbody>
                    @for (scenario of scenarios; track scenario) {
                      @if (coherence.rows[scenario]; as row) {
                        <tr>
                          <th>{{ scenarioLabel(scenario) }}</th>
                          <td>{{ numberText(row.eps, 4) }} / {{ numberText(row.bvps, 4) }}</td>
                          <td>{{ percent(row.implied_roe) }}</td>
                          <td>{{ numberText(row.coherent_pb) }}×</td>
                          <td>{{ numberText(row.observed_pb_anchor) }}×</td>
                          <td>{{ numberText(row.pb_gap_ratio) }}×</td>
                        </tr>
                      }
                    }
                  </tbody>
                </table>
              </nz-card>
            }

            <nz-collapse style="margin-top: 12px;">
              @for (method of result.matrix.methods; track method.code) {
                <nz-collapse-panel [nzHeader]="method.label + ' · 这格价格怎么算出来'">
                  <div class="method-detail">
                    <div>
                      <div class="formula">{{ method.formula }}</div>
                      <p class="muted">权重：{{ method.weight | percent:'1.0-0' }}</p>
                    </div>
                    <div>
                      <strong>计算输入</strong>
                      <pre>{{ pretty(method.inputs) }}</pre>
                      <strong>数据来源 / 假设来源</strong>
                      <pre>{{ pretty(method.provenance) }}</pre>
                      @if (method.calculation_trace) {
                        <strong>逐步计算（金额统一为元，页面换算为亿元）</strong>
                        <pre>{{ calculationTrace(method) }}</pre>
                      }
                    </div>
                  </div>
                </nz-collapse-panel>
              }
            </nz-collapse>

            <nz-card nzTitle="模型可信度拆解" nzSize="small" class="audit">
              <p><nz-tag [nzColor]="confidenceColor(result.confidence.label)">{{ result.confidence.usage_label }}</nz-tag>{{ result.confidence.score_semantics }}</p>
              <div style="margin-bottom: 8px;">
                @for (dimension of result.confidence.dimensions; track dimension.code) {
                  <nz-tag [nzColor]="dimensionColor(dimension.status)">{{ dimension.label }}：{{ dimensionStatusLabel(dimension.status) }}</nz-tag>
                }
              </div>
              <nz-table #confidenceTable [nzData]="result.confidence.components" [nzShowPagination]="false" nzSize="small" nzBordered>
                <thead><tr><th>维度</th><th>得分</th><th>解释</th></tr></thead>
                <tbody>
                  @for (component of confidenceTable.data; track component.code) {
                    <tr>
                      <td>{{ component.label }}</td>
                      <td><strong>{{ component.score }} / {{ component.max_score }}</strong></td>
                      <td>{{ component.reason }}</td>
                    </tr>
                  }
                </tbody>
              </nz-table>
              @for (gate of result.confidence.gates; track gate.code) {
                <nz-alert nzType="warning" nzShowIcon [nzMessage]="gate.code + ' · 评分上限 ' + gate.score_cap" [nzDescription]="gate.reason" style="display:block; margin-top: 8px;"></nz-alert>
              }
              <p class="muted">该分数评价输入质量、目标年度对齐、PIT 完整性与模型一致性，不代表收益概率、推荐强度或回测胜率。</p>
            </nz-card>

            <nz-card nzTitle="Point-in-time 审计线" nzSize="small" class="audit">
              <nz-descriptions nzSize="small" [nzColumn]="2" nzBordered>
                <nz-descriptions-item nzTitle="信息截止日">{{ result.point_in_time.information_as_of }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="价格截至">{{ result.point_in_time.price_as_of }} · {{ result.point_in_time.price_source }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="财报可得日">{{ result.point_in_time.financial_available_at || '无' }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="财报报告期">{{ result.point_in_time.financial_reporting_period || '无' }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="一致预期截至">{{ result.point_in_time.consensus_as_of || '无历史快照' }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="一致预期来源">{{ result.point_in_time.consensus_source || '无；Forward 方法不参与' }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="最新机构报告日">{{ result.point_in_time.consensus_latest_report_date || '来源未提供' }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="机构报告距截止日">{{ reportAgeLabel() }}</nz-descriptions-item>
                <nz-descriptions-item nzTitle="目标财年">{{ result.point_in_time.target_fiscal_year }}E</nz-descriptions-item>
                <nz-descriptions-item nzTitle="历史倍数起点">{{ result.point_in_time.history_start || '无' }}</nz-descriptions-item>
              </nz-descriptions>
              <p class="muted">{{ result.point_in_time.rule }}</p>
            </nz-card>

            @if (result.warnings.length) {
              <div class="warning-list">
                @for (warning of result.warnings; track warning.code) {
                  <nz-alert nzType="warning" nzShowIcon [nzMessage]="warning.code" [nzDescription]="warning.message"></nz-alert>
                }
              </div>
            }
          }
        </nz-tab>

        <nz-tab nzTitle="历史重放（Phase 2）">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field"><label>已选股票</label><strong>{{ selectedSecurity ? securityDisplay : '请先在估值矩阵页选择股票' }}</strong></div>
              <div class="field"><label>开始日期</label><input nz-input type="date" [(ngModel)]="historyStart" /></div>
              <div class="field"><label>结束日期</label><input nz-input type="date" [(ngModel)]="historyEnd" /></div>
              <div class="field"><label>重放间隔</label>
                <nz-select [(ngModel)]="historyInterval" style="width: 120px;">
                  <nz-option nzValue="month_end" nzLabel="月末"></nz-option>
                  <nz-option nzValue="quarter_end" nzLabel="季末"></nz-option>
                </nz-select>
              </div>
              <button nz-button nzType="primary" (click)="runHistory()" [nzLoading]="historyLoading" [disabled]="!securityId">运行 PIT 重放</button>
            </div>
          </nz-card>
          @if (historyResult) {
            <nz-alert style="margin-top: 12px;" nzType="info" nzShowIcon nzMessage="每一个历史点只使用信息截止日已经公告的财报、此前最后一个交易价格与已经抓取的预测快照；缺少目标年度预测时 Forward 方法直接禁用。"></nz-alert>
            <nz-table #historyTable [nzData]="historyResult.points" nzSize="small" style="margin-top: 12px;" [nzPageSize]="20">
              <thead><tr><th>估值日 / 价格日</th><th>市场价</th><th>低情景</th><th>中位情景</th><th>高情景</th><th>中位空间</th><th>结构/数据分</th><th>降级提示</th></tr></thead>
              <tbody>
                @for (point of historyTable.data; track point.valuation_date) {
                  <tr>
                    <td>{{ point.valuation_date }}<br><span class="muted">{{ point.price_as_of }}</span></td>
                    <td>{{ formatPrice(point.market_price) }}</td><td>{{ formatPrice(point.bear) }}</td><td>{{ formatPrice(point.base) }}</td><td>{{ formatPrice(point.bull) }}</td>
                    <td>{{ point.upside_base | percent:'1.1-1' }}</td>
                    <td>{{ point.confidence.score }}/100</td>
                    <td>@for (code of point.warning_codes; track code) { <nz-tag nzColor="orange">{{ code }}</nz-tag> }</td>
                  </tr>
                }
              </tbody>
            </nz-table>
            @if (historyResult.skipped.length) {
              <nz-alert nzType="warning" [nzMessage]="historyResult.skipped.length + ' 个历史点因价格或财报覆盖不足被跳过'" [nzDescription]="pretty(historyResult.skipped)"></nz-alert>
            }
          }
        </nz-tab>
      </nz-tabset>

      <nz-alert
        style="margin-top: 12px;"
        nzType="info"
        nzShowIcon
        nzMessage="估值是区间，不是目标价承诺"
        nzDescription="矩阵把盈利假设、估值倍数、资本结构和折现假设拆开显示；请结合行业周期、公司治理和重大事件复核。"
      ></nz-alert>
    </div>
  `,
})
export class ValuationMatrixPageComponent {
  private api = inject(WorkbenchApiService);
  private message = inject(NzMessageService);

  readonly scenarios: ValuationScenario[] = ['bear', 'base', 'bull'];
  readonly methodOptions: Array<{ value: ValuationMethodCode; label: string }> = [
    { value: 'forward_pe', label: 'Forward PE' },
    { value: 'pb_roe', label: 'PB / ROE' },
    { value: 'ev_ebitda', label: 'EV / EBITDA' },
    { value: 'dcf', label: 'FCFF DCF' },
  ];
  securityId: number | null = null;
  selectedSecurity: SecuritySearchItem | null = null;
  valuationDate = dayjs().format('YYYY-MM-DD');
  horizonYears = 1;
  historyYears = 5;
  marginOfSafetyPercent = 20;
  selectedMethods: ValuationMethodCode[] = ['forward_pe', 'pb_roe', 'ev_ebitda', 'dcf'];
  loading = false;
  result: ValuationAnalyzeResponse | null = null;

  historyStart = dayjs().subtract(3, 'year').format('YYYY-MM-DD');
  historyEnd = dayjs().format('YYYY-MM-DD');
  historyInterval: 'month_end' | 'quarter_end' = 'month_end';
  historyLoading = false;
  historyResult: ValuationHistoryResponse | null = null;

  get securityDisplay(): string {
    const security = this.selectedSecurity;
    return security ? `${security.name || security.symbol} · ${security.symbol}` : '';
  }

  onSecuritySelected(item: SecuritySearchItem | null): void {
    this.selectedSecurity = item;
    this.securityId = item?.security_id ?? null;
    this.result = null;
    this.historyResult = null;
  }

  runAnalysis(): void {
    if (!this.securityId || !this.selectedMethods.length) return;
    this.loading = true;
    this.api.analyzeValuation({
      security_id: this.securityId,
      valuation_date: this.valuationDate,
      horizon_years: this.horizonYears,
      history_years: this.historyYears,
      methods: this.selectedMethods,
      financial_source: 'amazing_data',
      statement_code: '1',
    }).subscribe({
      next: (result) => {
        this.loading = false;
        this.result = result;
      },
      error: (error: HttpErrorResponse) => {
        this.loading = false;
        this.result = null;
        this.message.error(this.errorMessage(error, '估值矩阵计算失败'));
      },
    });
  }

  runHistory(): void {
    if (!this.securityId) return;
    this.historyLoading = true;
    this.api.replayValuationHistory({
      security_id: this.securityId,
      start_date: this.historyStart,
      end_date: this.historyEnd,
      interval: this.historyInterval,
      history_years: this.historyYears,
    }).subscribe({
      next: (result) => {
        this.historyLoading = false;
        this.historyResult = result;
      },
      error: (error: HttpErrorResponse) => {
        this.historyLoading = false;
        this.historyResult = null;
        this.message.error(this.errorMessage(error, '历史估值重放失败'));
      },
    });
  }

  formatPrice(value: number | null | undefined): string {
    return value == null ? '—' : `¥${Number(value).toFixed(2)}`;
  }

  percentValue(value: number | null | undefined): number | string {
    return value == null ? '-' : Number((value * 100).toFixed(1));
  }

  pretty(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  aggregationLabel(): string {
    return this.result?.matrix.aggregation.mode === 'primary_with_cross_checks'
      ? '主估值 + 交叉验证'
      : '多方法综合估值';
  }

  aggregationModeLabel(): string {
    const mode = this.result?.matrix.aggregation.mode;
    if (mode === 'primary_with_cross_checks') return '主估值 + 交叉验证';
    if (mode === 'single_method') return '单一可用方法';
    return '多方法加权';
  }

  marketImpliedMessage(): string {
    const sensitivity = this.result?.forward_pe_sensitivity;
    const implied = sensitivity?.market_implied;
    const nearest = implied?.nearest_grid_cell;
    if (!sensitivity || !implied || !nearest) return '';
    const year = this.result?.point_in_time.target_fiscal_year;
    return [
      `当前价 ${this.formatPrice(implied.market_price)}`,
      `按中位 EPS ${this.valueAt(sensitivity.eps, 'base', 4)} 隐含 ${year}E PE ${this.numberText(implied.forward_pe_at_base_eps)}×`,
      `按中位 PE ${this.valueAt(sensitivity.multiples, 'base', 4)}× 反推 EPS ${this.numberText(implied.eps_at_base_multiple, 4)}`,
      `最近组合为 ${this.scenarioLabel(nearest.eps_scenario)} EPS × ${this.scenarioLabel(nearest.multiple_scenario)} PE = ${this.formatPrice(nearest.price)}（偏差 ${this.percent(nearest.gap_percent)}）`,
    ].join('；');
  }

  scenarioLabel(scenario: ValuationScenario): string {
    return this.result?.matrix.scenario_definitions?.[scenario]?.label
      ?? (scenario === 'bear' ? '低一致预期' : scenario === 'base' ? '中位一致预期' : '高一致预期');
  }

  observationPrice(): number | null {
    const anchor = Number(this.result?.range.base);
    if (!Number.isFinite(anchor)) return null;
    return Number((anchor * (1 - this.marginOfSafetyPercent / 100)).toFixed(2));
  }

  marketImpliedShort(): string {
    const implied = this.result?.forward_pe_sensitivity?.market_implied;
    if (!implied) return '当前数据无法反推。';
    return `按中位 EPS 隐含 PE ${this.numberText(implied.forward_pe_at_base_eps)}×；按中位 PE 反推 EPS ${this.numberText(implied.eps_at_base_multiple, 4)}。`;
  }

  reportAgeLabel(): string {
    const age = this.result?.point_in_time.consensus_latest_report_age_days;
    return age == null ? '来源未提供' : `${age} 天${age > 60 ? ' · 已降级提示' : ''}`;
  }

  isNearestCell(epsScenario: ValuationScenario, multipleScenario: ValuationScenario): boolean {
    const nearest = this.result?.forward_pe_sensitivity?.market_implied.nearest_grid_cell;
    return nearest?.eps_scenario === epsScenario && nearest?.multiple_scenario === multipleScenario;
  }

  methodRoleLabel(role: string): string {
    if (role === 'primary') return '主模型';
    if (role === 'cross_check') return '交叉验证';
    if (role === 'guardrail') return '资产护栏';
    return '综合模型';
  }

  methodRoleColor(role: string): string {
    if (role === 'primary') return 'blue';
    if (role === 'cross_check') return 'purple';
    if (role === 'guardrail') return 'gold';
    return 'default';
  }

  methodAssumptionLabel(method: ValuationMethodResult): string {
    if (method.code === 'forward_pe') return 'TTM PE → Forward PE 代理';
    if (method.code === 'pb_roe') return '历史 PB 锚';
    if (method.code === 'ev_ebitda') return '8 / 12 / 16× 配置假设';
    return 'EPS 增长 → FCFF 代理';
  }

  calculationTrace(method: ValuationMethodResult): string {
    const traces = method.calculation_trace || {};
    return this.scenarios
      .filter((scenario) => !!traces[scenario])
      .map((scenario) => {
        const trace: any = traces[scenario];
        const heading = this.scenarioLabel(scenario);
        if (method.code === 'ev_ebitda') {
          return [
            `${heading}:`,
            `TTM EBITDA ${this.compact(trace.starting_ttm_ebitda)} × (1 + ${this.percent(trace.growth_rate)})^${trace.horizon_years} = 前瞻 EBITDA ${this.compact(trace.forward_ebitda)}`,
            `前瞻 EBITDA × ${this.numberText(trace.multiple)} = 企业价值 ${this.compact(trace.enterprise_value)}`,
            `企业价值 − 净债务 ${this.compact(trace.net_debt)} = 权益价值 ${this.compact(trace.equity_value)}`,
            `权益价值 ÷ ${this.compact(trace.shares)} 股 = ${this.formatPrice(trace.price)}`,
          ].join('\n');
        }
        const years = Array.isArray(trace.years) ? trace.years : [];
        const path = years.map((year: any) =>
          `Y${year.year}: 增长 ${this.percent(year.growth_rate)} → FCFF ${this.compact(year.projected_fcff)} → 现值 ${this.compact(year.present_value_fcff)}`,
        );
        return [
          `${heading}: WACC ${this.percent(trace.wacc)}，永续增长 ${this.percent(trace.terminal_growth)}，近端增长在目标期限后线性收敛`,
          ...path,
          `显式期现值 ${this.compact(trace.explicit_present_value)} + 终值现值 ${this.compact(trace.terminal_present_value)} = 企业价值 ${this.compact(trace.enterprise_value)}`,
          `企业价值 − 净债务 ${this.compact(trace.net_debt)} = 权益价值 ${this.compact(trace.equity_value)}`,
          `权益价值 ÷ ${this.compact(trace.shares)} 股 = ${this.formatPrice(trace.price)}`,
        ].join('\n');
      })
      .join('\n\n');
  }

  keyInput(method: ValuationMethodResult, scenario: ValuationScenario): string {
    if (method.code === 'forward_pe') {
      return `EPS ${this.valueAt(method.inputs['eps'], scenario, 4)} × PE ${this.valueAt(method.inputs['pe'], scenario, 4)}`;
    }
    if (method.code === 'pb_roe') {
      return `BVPS ${this.valueAt(method.inputs['forward_book_value_per_share'], scenario, 4)} × PB ${this.valueAt(method.inputs['pb'], scenario, 4)}`;
    }
    if (method.code === 'ev_ebitda') {
      const trace: any = method.calculation_trace?.[scenario];
      return `增长 ${this.percent(trace?.growth_rate)} · EV/EBITDA ${this.valueAt(method.inputs['ev_ebitda'], scenario, 2)}×`;
    }
    const trace: any = method.calculation_trace?.[scenario];
    return `Y1 增长 ${this.percent(trace?.years?.[0]?.growth_rate)} · WACC ${this.percent(trace?.wacc)}`;
  }

  valueAt(value: any, key: string, digits = 2): string {
    const item = value && typeof value === 'object' ? value[key] : null;
    return item == null ? '—' : Number(item).toFixed(digits);
  }

  private compact(value: unknown): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '—';
    if (Math.abs(parsed) >= 1e8) return `${(parsed / 1e8).toFixed(2)} 亿`;
    if (Math.abs(parsed) >= 1e4) return `${(parsed / 1e4).toFixed(2)} 万`;
    return parsed.toFixed(2);
  }

  percent(value: unknown): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(1)}%` : '—';
  }

  numberText(value: unknown, digits = 2): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—';
  }

  coherenceColor(status: string): string {
    if (status === 'aligned') return 'green';
    if (status === 'divergent') return 'gold';
    if (status === 'severely_divergent') return 'red';
    return 'default';
  }

  coherenceStatusLabel(status: string): string {
    if (status === 'aligned') return '基本一致';
    if (status === 'divergent') return '存在分歧';
    if (status === 'severely_divergent') return '严重分歧';
    return '不可计算';
  }

  dimensionColor(status: string): string {
    if (status === 'high') return 'green';
    if (status === 'medium' || status === 'provisional') return 'gold';
    if (status === 'low' || status === 'limited') return 'red';
    return 'default';
  }

  dimensionStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      high: '高', medium: '中', low: '低', provisional: '暂定', limited: '受限', unavailable: '不可用',
    };
    return labels[status] ?? status;
  }

  confidenceColor(label: string): string {
    return label === 'high' ? 'green' : label === 'medium' ? 'gold' : 'red';
  }

  confidenceLabel(label: string): string {
    return label === 'high' ? '高' : label === 'medium' ? '中' : '低';
  }

  methodLabel(code: ValuationMethodCode): string {
    return this.methodOptions.find((option) => option.value === code)?.label ?? code;
  }

  private errorMessage(error: HttpErrorResponse, fallback: string): string {
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    return fallback;
  }
}
