import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import dayjs from 'dayjs';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';

import {
  TBatchReplayResponse,
  TExecutionConfig,
  TReplayResponse,
  TIndicatorSet,
  TSignalMode,
  TSignalEvaluationConfig,
  TStrategyConfig,
  TStrategyName,
} from '../models/workbench.model';
import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import { WorkbenchApiService } from '../services/workbench-api.service';
import { TTradingChartComponent } from '../ui/t-trading-chart.component';

interface ParamField {
  key: keyof TStrategyConfig;
  label: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
}

@Component({
  selector: 'app-t-trading-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzAlertModule, NzButtonModule, NzCardModule,
    NzCollapseModule, NzFormModule, NzInputModule, NzInputNumberModule,
    NzSelectModule, NzStatisticModule, NzTableModule, NzTabsModule, NzTagModule,
    NzToolTipModule,
    SecuritySearchInputComponent, TTradingChartComponent,
  ],
  styles: [`
    .page { padding: 16px; }
    .toolbar { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
    .field label { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; color: #666; font-size: 12px; }
    .help-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 14px;
      height: 14px;
      border: 1px solid #bfbfbf;
      border-radius: 50%;
      color: #8c8c8c;
      font-size: 10px;
      line-height: 1;
      cursor: help;
    }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; margin: 12px 0; }
    .meta { color: #888; font-size: 12px; }
    .positive { color: #cf1322; }
    .negative { color: #237804; }
    .strategy-select { min-width: 340px; max-width: 560px; }
    .review-notice { display: block; margin-top: 12px; }
  `],
  template: `
    <div class="page">
      <nz-tabset>
        <nz-tab nzTitle="逐日回放">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field"><label>股票代码 / 名称</label><app-security-search-input placeholder="输入 600183 或生益科技" (securitySelected)="onSecuritySelected($event)"></app-security-search-input></div>
              <div class="field"><label>日期</label><input nz-input type="date" [(ngModel)]="tradeDate" (change)="onTradeDateChanged()" style="width: 145px;" /></div>
              <div class="field"><label>周期</label>
                <nz-select [(ngModel)]="period" (ngModelChange)="onPeriodChange($event)" style="width: 100px;">
                  <nz-option nzValue="min1" nzLabel="1 分钟"></nz-option>
                  <nz-option nzValue="min5" nzLabel="5 分钟"></nz-option>
                </nz-select>
              </div>
              <div class="field"><label>买卖点策略（可多选）</label>
                <nz-select [(ngModel)]="selectedStrategies" (ngModelChange)="onStrategiesChanged($event)" nzMode="multiple" class="strategy-select" nzPlaceHolder="至少选择一个策略">
                  @for (option of strategyOptions; track option.value) {
                    <nz-option [nzValue]="option.value" [nzLabel]="option.label"></nz-option>
                  }
                </nz-select>
              </div>
              @if (needsBenchmark) {
                <div class="field"><label>宽基指数 Security ID</label><nz-input-number [(ngModel)]="benchmarkSecurityId" [nzMin]="1"></nz-input-number></div>
              }
              <div class="field"><label>信号模式（应用于全部策略）</label>
                <nz-select [(ngModel)]="direction" style="width: 180px;">
                  <nz-option nzValue="independent" nzLabel="独立寻找买点和卖点"></nz-option>
                  <nz-option nzValue="buy_first" nzLabel="先买后卖"></nz-option>
                  <nz-option nzValue="sell_first" nzLabel="先卖后买"></nz-option>
                </nz-select>
              </div>
              <button nz-button (click)="moveDay(-1)" [disabled]="loading">上一天</button>
              <button nz-button nzType="primary" (click)="runReplay()" [nzLoading]="loading">运行 Review</button>
              <button nz-button (click)="moveDay(1)" [disabled]="loading">下一天</button>
              <nz-tag nzColor="blue">ephemeral · 不落库</nz-tag>
            </div>
          </nz-card>

          <nz-collapse style="margin-top: 10px;">
            @for (name of selectedStrategies; track name) {
              <nz-collapse-panel [nzHeader]="strategyLabel(name) + ' · 参数'">
                <div class="toolbar">
                  @for (field of fieldsFor(name); track field.key) {
                    <div class="field"><label>
                      {{ field.label }}
                      @if (field.description) {
                        <span
                          class="help-icon"
                          nz-tooltip
                          [nzTooltipTitle]="field.description"
                          [attr.aria-label]="field.description"
                          tabindex="0"
                        >?</span>
                      }
                    </label>
                      <nz-input-number
                        [(ngModel)]="strategyConfigs[name][field.key]"
                        [nzMin]="field.min ?? -1e9"
                        [nzMax]="field.max ?? 1e9"
                        [nzStep]="field.step ?? 1"
                      ></nz-input-number>
                    </div>
                  }
                </div>
              </nz-collapse-panel>
            }
            <nz-collapse-panel nzHeader="信号后路径评估（全局）" [nzActive]="false">
              <div class="toolbar">
                <div class="field"><label>
                  主评估观察长度
                  <span class="help-icon" nz-tooltip nzTooltipTitle="信号 bar 完成后，再观察未来 N 根完整 K 线。这里只能从当前已计算的 horizon 中选择，避免请求不一致。" aria-label="主评估观察长度说明" tabindex="0">?</span>
                </label>
                  <nz-select [(ngModel)]="evaluation.primary_horizon_bars" style="width: 180px;">
                    @for (horizon of evaluation.horizons_bars; track horizon) {
                      <nz-option [nzValue]="horizon" [nzLabel]="horizonOptionLabel(horizon)"></nz-option>
                    }
                  </nz-select>
                </div>
                <div class="field"><label>
                  目标阈值（0.005 = 0.5%）
                  <span class="help-icon" nz-tooltip nzTooltipTitle="BUY 后顺向上涨、SELL 后顺向下跌达到该幅度时，记为 target touched/target-first。只用于信号评估，不会自动止盈。" aria-label="目标阈值说明" tabindex="0">?</span>
                </label>
                  <nz-input-number [(ngModel)]="evaluation.target_return" [nzStep]="0.001" [nzMin]="0.001" [nzMax]="0.2"></nz-input-number>
                </div>
                <div class="field"><label>
                  风险阈值（0.003 = 0.3%）
                  <span class="help-icon" nz-tooltip nzTooltipTitle="信号后先向错误方向波动达到该幅度时，记为 stop touched/stop-first。只用于路径标签，不会自动止损或下单。" aria-label="风险阈值说明" tabindex="0">?</span>
                </label>
                  <nz-input-number [(ngModel)]="evaluation.stop_return" [nzStep]="0.001" [nzMin]="0.001" [nzMax]="0.2"></nz-input-number>
                </div>
              </div>
            </nz-collapse-panel>
          </nz-collapse>

          @if (result) {
            <div class="stats">
              <nz-card nzSize="small"><nz-statistic [nzTitle]="result.summary.horizon_bars + ' bars 方向正确率'" [nzValue]="toPercent(result.summary.directional_accuracy)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均方向收益" [nzValue]="toPercentPrecise(result.summary.mean_directional_return)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均 MFE" [nzValue]="toPercentPrecise(result.summary.mean_mfe)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均 MAE" [nzValue]="toPercentPrecise(result.summary.mean_mae)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="MFE / MAE" [nzValue]="result.summary.edge_ratio ?? '-'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="可评估信号" [nzValue]="result.summary.evaluable_signal_count" [nzSuffix]="' / ' + result.summary.signal_count"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="数据 bars" [nzValue]="result.data_quality.bar_count"></nz-statistic></nz-card>
            </div>
            <nz-card [nzTitle]="securityDisplay + ' · ' + result.run_meta.trade_date + ' · 买卖点 Review'" nzSize="small">
              <div class="toolbar" style="margin-bottom: 8px;">
                <div class="field"><label>图上指标参数来自</label>
                  <nz-select [(ngModel)]="indicatorStrategy" style="width: 250px;">
                    @for (name of selectedStrategies; track name) {
                      <nz-option [nzValue]="name" [nzLabel]="strategyLabel(name)"></nz-option>
                    }
                  </nz-select>
                </div>
                @if (selectedIndicatorSet) {
                  <span class="meta">EMA {{ selectedIndicatorSet.parameters.ema_fast }}/{{ selectedIndicatorSet.parameters.ema_slow }} · MACD signal {{ selectedIndicatorSet.parameters.macd_signal }} · Bollinger {{ selectedIndicatorSet.parameters.bollinger_z }}</span>
                }
              </div>
              <app-t-trading-chart [bars]="result.bars" [signals]="result.signals" [fills]="result.fills" [indicatorSet]="selectedIndicatorSet"></app-t-trading-chart>
              <div class="meta">所有指标和信号都只使用判断时刻及以前的数据；EMA/MACD/RSI/ATR 使用前序交易日分钟线预热，当日 VWAP 与开盘区间仍从当天重置。主评估观察其后 {{ result.summary.horizon_bars }} 根 K 线，不模拟成交；MFE/MAE 分别表示顺向最大空间与逆向最大波动。意外缺口 {{ result.data_quality.unexpected_gap_count }}，零成交量 bars {{ result.data_quality.zero_volume_bars }}。</div>
            </nz-card>
            @if (result.signal_evaluation.by_strategy.length) {
              <nz-card nzTitle="按策略的信号效果" nzSize="small" style="margin-top: 12px;">
                <nz-table #strategyTable [nzData]="result.signal_evaluation.by_strategy_side" [nzShowPagination]="false" nzSize="small">
                  <thead><tr><th>策略</th><th>方向</th><th>信号</th><th>方向正确率</th><th>平均方向收益</th><th>平均 MFE</th><th>平均 MAE</th><th>MFE / MAE</th></tr></thead>
                  <tbody>
                    @for (row of strategyTable.data; track row.strategy + '-' + row.side) {
                      <tr>
                        <td><nz-tag [nzColor]="strategyColor(row.strategy)">{{ strategyLabel(row.strategy) }}</nz-tag></td>
                        <td>{{ sideLabel(row.side) }}</td>
                        <td>{{ row.evaluable_signal_count }} / {{ row.signal_count }}</td>
                        <td>{{ row.directional_accuracy | percent:'1.1-1' }}</td>
                        <td>{{ row.mean_directional_return | percent:'1.2-3' }}</td>
                        <td>{{ row.mean_mfe | percent:'1.2-3' }}</td>
                        <td>{{ row.mean_mae | percent:'1.2-3' }}</td>
                        <td>{{ row.edge_ratio ?? '-' }}</td>
                      </tr>
                    }
                  </tbody>
                </nz-table>
              </nz-card>
            }
            <nz-card nzTitle="信号审计" nzSize="small" style="margin-top: 12px;">
              <nz-table #signalTable [nzData]="result.signals" [nzShowPagination]="false" nzSize="small">
                <thead><tr><th>判断时间</th><th>策略</th><th>方向</th><th>判断价</th><th>置信度</th><th>Z</th><th>RSI</th><th>原因</th></tr></thead>
                <tbody>
                  @for (signal of signalTable.data; track signal.signal_id) {
                    <tr>
                      <td>{{ formatTime(signal.decision_time) }}</td>
                      <td><nz-tag [nzColor]="strategyColor(signal.strategy)">{{ strategyLabel(signal.strategy) }}</nz-tag></td>
                      <td><nz-tag [nzColor]="signal.side === 'BUY' ? 'red' : 'green'">{{ signal.side }}</nz-tag></td>
                      <td>{{ signal.decision_price }}</td><td>{{ signal.confidence | percent:'1.1-1' }}</td>
                      <td>{{ signal.features['zscore'] | number:'1.2-2' }}</td><td>{{ signal.features['rsi'] | number:'1.1-1' }}</td>
                      <td>{{ signal.reason_codes.join(', ') }}</td>
                    </tr>
                  }
                </tbody>
              </nz-table>
            </nz-card>
          }
        </nz-tab>

        <nz-tab nzTitle="批量统计">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field"><label>Security IDs（逗号分隔）</label><input nz-input [(ngModel)]="batchSecurityIds" style="width: 260px;" placeholder="1,2,3" /></div>
              <div class="field"><label>开始日期</label><input nz-input type="date" [(ngModel)]="batchStartDate" /></div>
              <div class="field"><label>结束日期</label><input nz-input type="date" [(ngModel)]="batchEndDate" /></div>
              <button nz-button nzType="primary" (click)="runBatch()" [nzLoading]="batchLoading">生成临时报告</button>
              <nz-tag nzColor="blue">报告不落库</nz-tag>
            </div>
          </nz-card>
          @if (batchResult) {
            <div class="stats">
              <nz-card nzSize="small"><nz-statistic nzTitle="方向正确率" [nzValue]="toPercent(batchResult.summary.directional_accuracy)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均方向收益" [nzValue]="toPercent(batchResult.summary.mean_directional_return)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均 MFE / MAE" [nzValue]="toPercent(batchResult.summary.mean_mfe)" [nzSuffix]="'% / ' + toPercent(batchResult.summary.mean_mae) + '%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="有信号日期" [nzValue]="batchResult.summary.days_with_signals || 0"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="跳过 / 失败" [nzValue]="batchResult.skipped.length" [nzSuffix]="' / ' + batchResult.failures.length"></nz-statistic></nz-card>
            </div>
            @if (batchResult.by_strategy.length) {
              <nz-table #batchStrategyTable [nzData]="batchResult.by_strategy" [nzShowPagination]="false" nzSize="small" style="margin-bottom: 12px;">
                <thead><tr><th>策略</th><th>信号</th><th>方向正确率</th><th>平均方向收益</th><th>平均 MFE</th><th>平均 MAE</th></tr></thead>
                <tbody>
                  @for (row of batchStrategyTable.data; track row.strategy) {
                    <tr><td><nz-tag [nzColor]="strategyColor(row.strategy)">{{ strategyLabel(row.strategy) }}</nz-tag></td><td>{{ row.evaluable_signal_count }} / {{ row.signal_count }}</td><td>{{ row.directional_accuracy | percent:'1.1-1' }}</td><td>{{ row.mean_directional_return | percent:'1.2-2' }}</td><td>{{ row.mean_mfe | percent:'1.2-2' }}</td><td>{{ row.mean_mae | percent:'1.2-2' }}</td></tr>
                  }
                </tbody>
              </nz-table>
            }
            <nz-table #batchTable [nzData]="batchResult.by_security" nzSize="small">
              <thead><tr><th>Security ID</th><th>回放日</th><th>信号</th><th>方向正确率</th><th>平均方向收益</th><th>平均 MFE</th><th>平均 MAE</th></tr></thead>
              <tbody>
                @for (row of batchTable.data; track row.security_id) {
                  <tr><td>{{ row.security_id }}</td><td>{{ row.replay_days }}</td><td>{{ row.evaluable_signal_count }} / {{ row.signal_count }}</td><td>{{ row.directional_accuracy | percent:'1.1-1' }}</td><td>{{ row.mean_directional_return | percent:'1.2-2' }}</td><td>{{ row.mean_mfe | percent:'1.2-2' }}</td><td>{{ row.mean_mae | percent:'1.2-2' }}</td></tr>
                }
              </tbody>
            </nz-table>
          }
        </nz-tab>
      </nz-tabset>

      <nz-alert
        class="review-notice"
        nzType="info"
        nzShowIcon
        nzMessage="信号优先的纯内存 Review"
        nzDescription="分钟行情按需增量持久化；策略参数、信号和报告不落库。主评估观察买点之后上涨多少、卖点之后下跌多少，成交模拟默认关闭。"
      ></nz-alert>
    </div>
  `,
})
export class TTradingPageComponent {
  private api = inject(WorkbenchApiService);
  private message = inject(NzMessageService);

  securityId: number | null = null;
  selectedSecurity: SecuritySearchItem | null = null;
  tradeDate = dayjs().format('YYYY-MM-DD');
  period: 'min1' | 'min5' = 'min1';
  selectedStrategies: TStrategyName[] = ['macd_volume_momentum_v1'];
  benchmarkSecurityId: number | null = null;
  loading = false;
  result: TReplayResponse | null = null;
  indicatorStrategy: TStrategyName | null = 'macd_volume_momentum_v1';
  batchLoading = false;
  batchSecurityIds = '';
  batchStartDate = dayjs().subtract(30, 'day').format('YYYY-MM-DD');
  batchEndDate = dayjs().format('YYYY-MM-DD');
  batchResult: TBatchReplayResponse | null = null;
  readonly strategyOptions: Array<{ value: TStrategyName; label: string; color: string }> = [
    { value: 'causal_mean_reversion_v1', label: 'Z-score + RSI + VWAP 反转', color: 'magenta' },
    { value: 'macd_volume_momentum_v1', label: 'MACD + 量能 + EMA 偏离回归', color: 'blue' },
    { value: 'macd_volume_regime_reversal_v1', label: 'MACD + 量能 + EMA + 不对称单边门控', color: 'volcano' },
    { value: 'vwap_bollinger_reversion_v1', label: 'VWAP + Bollinger + 拒绝影线', color: 'purple' },
    { value: 'opening_range_breakout_v1', label: '开盘区间 + 量能突破', color: 'orange' },
    { value: 'time_of_day_volume_momentum_v1', label: '同分钟历史量比 + 价格确认', color: 'cyan' },
    { value: 'market_residual_reversal_v1', label: '宽基市场残差反转', color: 'geekblue' },
    { value: 'multi_timeframe_pullback_v1', label: '日线 / 30 分钟顺势回踩', color: 'green' },
  ];

  strategy: TStrategyConfig = {
    strategy: 'causal_mean_reversion_v1',
    direction: 'independent', window: 20, entry_z: 1.25, exit_z: 1,
    entry_rsi: 35, exit_rsi: 65, confirmation_bars: 3,
    cooldown_bars: 5, max_round_trips: 2,
    ema_fast: 5, ema_slow: 13, macd_signal: 4, min_volume_ratio: 0.8,
    ema_deviation_atr: 0.35, macd_turn_bars: 2,
    volume_confirmation_window: 3,
    panic_window_bars: 5, panic_return_threshold: 0.02,
    panic_volume_ratio: 3, macd_divergence_lookback: 20,
    rebound_confirmation_bars: 3, rebound_recovery_ratio: 0.5,
    deep_reversal_min_score: 3, regime_slope_bars: 5,
    medium_trend_fast_bars: 15, medium_trend_slow_bars: 30,
    rebound_ema_tolerance_atr: 0.5, minimum_recent_range: 0.005,
    bollinger_z: 1.5, reversal_wick_ratio: 0.25, max_trend_strength_atr: 0.8,
    atr_window: 14, opening_range_bars: 6, breakout_atr_buffer: 0.1,
    relative_volume_tod_threshold: 1.5, min_time_of_day_history_days: 20,
    market_beta_window: 20, residual_z_threshold: 1.5,
    higher_ema_fast: 5, higher_ema_slow: 10, daily_trend_window: 20,
    pullback_tolerance_atr: 0.5,
  };
  direction: TSignalMode = 'independent';

  /** Per-strategy parameter state; each selected strategy is sent its own config. */
  strategyConfigs: Record<TStrategyName, TStrategyConfig> = this.buildStrategyConfigs();
  /** Strategy-specific fields; shared state-machine fields are appended per panel. */
  private readonly paramFields: Record<TStrategyName, ParamField[]> = {
    causal_mean_reversion_v1: [
      { key: 'window', label: '窗口', min: 5, max: 120 },
      { key: 'entry_z', label: '入场 Z', step: 0.1 },
      { key: 'exit_z', label: '离场 Z', step: 0.1 },
      { key: 'entry_rsi', label: '买侧 RSI' },
      { key: 'exit_rsi', label: '卖侧 RSI' },
    ],
    macd_volume_momentum_v1: [
      { key: 'ema_fast', label: 'EMA 快', min: 2 },
      { key: 'ema_slow', label: 'EMA 慢', min: 3 },
      { key: 'macd_signal', label: 'MACD signal', min: 2 },
      { key: 'min_volume_ratio', label: '最小量比', step: 0.1, description: '最近量能窗口内最大量比的下限。单根量比 = 当前成交量 / 截至当前的滚动窗口成交量中位数；只表示有没有量，不区分买压或卖压。' },
      { key: 'ema_deviation_atr', label: '慢均线最小偏离（ATR 倍数）', step: 0.05, description: '价格到慢 EMA 的距离除以 ATR。BUY 必须至少低于慢 EMA 该距离，SELL 必须至少高于；数值越大，候选越偏离均线。' },
      { key: 'macd_turn_bars', label: 'MACD 连续收敛 bars', min: 1, max: 6, description: 'BUY 要求 MACD 绿柱连续 N 根向零轴收敛，或刚由负转正；SELL 镜像，要求红柱连续 N 根收敛，或刚由正转负。N 越大，确认越慢也越严格。' },
      { key: 'volume_confirmation_window', label: '近期量能观察窗口（bars）', min: 1, max: 20, description: '向后查看最近 N 根完整 bar，取其中最大的量比与“最小量比”比较；不是累计成交量。' },
    ],
    macd_volume_regime_reversal_v1: [
      { key: 'ema_fast', label: 'EMA 快', min: 2 },
      { key: 'ema_slow', label: 'EMA 慢', min: 3 },
      { key: 'macd_signal', label: 'MACD signal', min: 2 },
      { key: 'min_volume_ratio', label: '基础最小量比', step: 0.1, description: '沿用基础策略的近期量能门槛；只用于确认候选点具备成交活跃度，不判断买卖盘方向。' },
      { key: 'ema_deviation_atr', label: '慢均线最小偏离（ATR）', step: 0.05, description: '候选反转前，价格必须曾经偏离慢 EMA 至少该 ATR 倍数；单边状态中按近期窗口的最深偏离判断。' },
      { key: 'macd_turn_bars', label: 'MACD 连续收敛 bars', min: 1, max: 6, description: 'BUY 要求绿柱连续收敛或由负转正；SELL 镜像。它是候选点条件，不等同于 MACD 背离证据。' },
      { key: 'volume_confirmation_window', label: '基础量能窗口（bars）', min: 1, max: 20, description: '基础量比向后观察的 bars 数；与“恐慌量倍数”的前 N 根均量基线是两套独立定义。' },
      { key: 'regime_slope_bars', label: '单边斜率窗口（bars）', min: 1, max: 30, description: '用 N 根 bar 前后的慢 EMA 与 VWAP 斜率识别单边状态。价格位于两者下方且二者均向下时，BUY 启用四维门控；SELL 对称。' },
      { key: 'panic_window_bars', label: '急跌 / 急涨窗口（bars）', min: 2, max: 30, description: '计算窗口首尾收益，并让急跌、恐慌量和极端偏离证据在短窗口内有效。1 分钟周期默认 5 即约 5 分钟。' },
      { key: 'panic_return_threshold', label: '急跌 / 急涨阈值', min: 0.001, max: 0.2, step: 0.001, description: '窗口收益的绝对阈值，0.02 表示 2%。BUY 检查急跌，SELL 检查急涨。' },
      { key: 'panic_volume_ratio', label: '恐慌量倍数', min: 0.1, max: 20, step: 0.1, description: '当前成交量 / 此前 N 根 bar 平均成交量；默认 3 表示至少放大到 3 倍。与滚动中位数量比不同。' },
      { key: 'macd_divergence_lookback', label: 'MACD 背离回看（bars）', min: 5, max: 120, description: '只比较当日、当前 bar 之前的极值。BUY 要求价格新低但 MACD 柱或 DIF 未同步新低；SELL 对称。' },
      { key: 'rebound_confirmation_bars', label: '反弹 / 回落连续 bars', min: 1, max: 10, description: 'BUY 要求连续 N 根阳线，SELL 要求连续 N 根阴线；与通用的价格方向确认窗口不同。' },
      { key: 'rebound_recovery_ratio', label: '吞没大实体比例', min: 0, max: 2, step: 0.05, description: '反弹需收复近期最大阴线实体的比例；0.5 表示收复一半。SELL 使用最大阳线的镜像定义。' },
      { key: 'deep_reversal_min_score', label: '单边反转最少证据（/4）', min: 1, max: 4, description: '单边状态下，急跌/急涨、恐慌量、MACD 背离、反弹/回落结构四项中至少满足几项。默认 3；不足时不发逆势信号。' },
      { key: 'medium_trend_fast_bars', label: '倒 T 快趋势窗口（bars）', min: 3, max: 60, description: 'SELL 独立规则要求当前价同时低于该窗口和慢窗口之前的价格；默认 15/30 根都下跌，避免把上涨中的普通回落当成倒 T 卖点。' },
      { key: 'medium_trend_slow_bars', label: '倒 T 慢趋势窗口（bars）', min: 5, max: 120, description: 'SELL 的第二个中期下行确认窗口，必须大于快窗口。1 分钟周期默认 30 即约 30 分钟。' },
      { key: 'rebound_ema_tolerance_atr', label: '反弹靠近 EMA 容差（ATR）', min: 0, max: 5, step: 0.05, description: '倒 T SELL 只在价格从下方反弹到慢 EMA 附近后寻找再次转弱；0.5 表示上下不超过半个 ATR，避免在已经深跌的位置追卖。' },
      { key: 'minimum_recent_range', label: '近期最小振幅', min: 0, max: 0.2, step: 0.001, description: '快趋势窗口内最高/最低价振幅的机会门槛。0.005 表示至少 0.5%；不足时允许不发 SELL，避免在低波动噪声中频繁择时。' },
    ],
    vwap_bollinger_reversion_v1: [
      { key: 'window', label: '窗口', min: 5, max: 120 },
      { key: 'bollinger_z', label: 'Bollinger Z', step: 0.1 },
      { key: 'entry_rsi', label: '买侧 RSI' },
      { key: 'reversal_wick_ratio', label: '拒绝影线比', step: 0.05 },
      { key: 'min_volume_ratio', label: '最小量比', step: 0.1, description: '当前 bar 成交量 / 截至当前的滚动窗口成交量中位数的下限；只确认量能异常，不代表买卖方向。' },
      { key: 'max_trend_strength_atr', label: '趋势强度上限 ATR', step: 0.1 },
      { key: 'atr_window', label: 'ATR 窗口', min: 2 },
    ],
    opening_range_breakout_v1: [
      { key: 'opening_range_bars', label: '开盘区间 bars', min: 2 },
      { key: 'breakout_atr_buffer', label: '突破缓冲 ATR', step: 0.05 },
      { key: 'min_volume_ratio', label: '最小量比', step: 0.1, description: '突破 bar 成交量 / 截至当前的滚动窗口成交量中位数的下限；需与价格突破方向一起判断。' },
      { key: 'ema_fast', label: 'EMA 快', min: 2 },
      { key: 'ema_slow', label: 'EMA 慢', min: 3 },
    ],
    time_of_day_volume_momentum_v1: [
      { key: 'relative_volume_tod_threshold', label: '同分钟相对量阈值', step: 0.1 },
      { key: 'min_time_of_day_history_days', label: '同分钟历史日数', min: 5 },
      { key: 'ema_fast', label: 'EMA 快', min: 2 },
      { key: 'macd_signal', label: 'MACD signal', min: 2 },
    ],
    market_residual_reversal_v1: [
      { key: 'residual_z_threshold', label: '残差 Z 阈值', step: 0.1 },
      { key: 'market_beta_window', label: '市场 beta 窗口', min: 5 },
    ],
    multi_timeframe_pullback_v1: [
      { key: 'higher_ema_fast', label: '30 分钟 EMA 快', min: 2 },
      { key: 'higher_ema_slow', label: '30 分钟 EMA 慢', min: 3 },
      { key: 'daily_trend_window', label: '日线趋势窗口', min: 5 },
      { key: 'pullback_tolerance_atr', label: '回踩容差 ATR', step: 0.1 },
    ],
  };
  private readonly sharedParamFields: ParamField[] = [
    { key: 'confirmation_bars', label: '确认 bars', min: 1, max: 12 },
    { key: 'cooldown_bars', label: '冷却 bars', min: 0, max: 30 },
    { key: 'max_round_trips', label: '每侧信号上限 / 最多往返', min: 1, max: 10 },
  ];
  evaluation: TSignalEvaluationConfig = {
    horizons_bars: [1, 3, 5, 15], primary_horizon_bars: 5,
    target_return: 0.005, stop_return: 0.003,
  };
  execution: TExecutionConfig = {
    quantity: 100, commission_rate: 0.0003, minimum_commission: 5,
    stamp_duty_rate_on_sell: 0.0005, transfer_fee_rate: 0.00001, slippage_bps: 1,
  };

  get securityDisplay(): string {
    if (this.selectedSecurity) {
      return `${this.selectedSecurity.name || this.selectedSecurity.symbol} · ${this.selectedSecurity.symbol}`;
    }
    return this.result?.run_meta.symbol ?? '';
  }

  get selectedIndicatorSet(): TIndicatorSet | null {
    if (!this.result?.indicator_sets?.length) return null;
    return this.result.indicator_sets.find(
      (item) => item.strategy === this.indicatorStrategy,
    ) ?? this.result.indicator_sets[0] ?? null;
  }

  onSecuritySelected(item: SecuritySearchItem | null): void {
    this.selectedSecurity = item;
    this.securityId = item?.security_id ?? null;
    this.result = null;
  }

  onStrategiesChanged(names: TStrategyName[]): void {
    if (!names.includes(this.indicatorStrategy as TStrategyName)) {
      this.indicatorStrategy = names[0] ?? null;
    }
  }

  onTradeDateChanged(): void {
    const weekday = dayjs(this.tradeDate).day();
    if ((weekday === 0 || weekday === 6) && this.securityId) {
      this.resolveNearestDate(false);
    }
  }

  private resolveNearestDate(runAfterResolve: boolean): void {
    if (!this.securityId || !this.tradeDate) return;
    const requested = this.tradeDate;
    this.loading = true;
    this.api.nearestTradeDate(this.securityId, requested, 'prev').subscribe({
      next: (result) => {
        this.loading = false;
        this.tradeDate = result.trade_date;
        this.message.info(`${requested} 无分钟行情，已切换到最近交易日 ${result.trade_date}`);
        if (runAfterResolve) this.runReplay(false);
      },
      error: () => {
        this.loading = false;
        this.result = null;
        this.message.warning('所选日期没有分钟行情，且未找到更早的可用交易日');
      },
    });
  }

  /** Jump to the nearest day that actually has bars, skipping weekends,
   *  holidays and suspensions instead of surfacing a no-data error. */
  moveDay(delta: number): void {
    if (!this.securityId || !this.tradeDate) {
      this.tradeDate = dayjs(this.tradeDate).add(delta, 'day').format('YYYY-MM-DD');
      return;
    }
    const fallbackDate = dayjs(this.tradeDate).add(delta, 'day').format('YYYY-MM-DD');
    this.loading = true;
    this.api.nearestTradeDate(this.securityId, this.tradeDate, delta < 0 ? 'prev' : 'next')
      .subscribe({
        next: (result) => {
          this.loading = false;
          this.tradeDate = result.trade_date;
          this.runReplay();
        },
        error: () => {
          // Endpoint unavailable or no daily coverage: fall back to plain ±1 day.
          this.loading = false;
          this.tradeDate = fallbackDate;
          this.runReplay();
        },
      });
  }

  get needsBenchmark(): boolean {
    return this.selectedStrategies.includes('market_residual_reversal_v1');
  }

  onPeriodChange(period: 'min1' | 'min5'): void {
    this.period = period;
    this.evaluation = period === 'min1'
      ? { ...this.evaluation, horizons_bars: [1, 3, 5, 15], primary_horizon_bars: 5 }
      : { ...this.evaluation, horizons_bars: [1, 3, 6, 12], primary_horizon_bars: 6 };
  }

  horizonOptionLabel(horizon: number): string {
    const minutes = horizon * (this.period === 'min1' ? 1 : 5);
    return `${horizon} 根（约 ${minutes} 分钟）`;
  }

  strategyLabel(strategy: TStrategyName): string {
    return this.strategyOptions.find((option) => option.value === strategy)?.label ?? strategy;
  }

  strategyColor(strategy: TStrategyName): string {
    return this.strategyOptions.find((option) => option.value === strategy)?.color ?? 'default';
  }

  private buildStrategyConfigs(): Record<TStrategyName, TStrategyConfig> {
    const entries = this.strategyOptions.map((option) => [
      option.value,
      { ...this.strategy, strategy: option.value },
    ] as const);
    return Object.fromEntries(entries) as Record<TStrategyName, TStrategyConfig>;
  }

  fieldsFor(name: TStrategyName): ParamField[] {
    return [...(this.paramFields[name] ?? []), ...this.sharedParamFields];
  }

  sideLabel(side: string): string {
    return side === 'BUY' ? '买' : side === 'SELL' ? '卖' : '全部';
  }

  private selectedStrategyConfigs(): TStrategyConfig[] {
    return this.selectedStrategies.map(
      (name) => ({ ...this.strategyConfigs[name], strategy: name, direction: this.direction }),
    );
  }

  private validateStrategies(): boolean {
    if (!this.selectedStrategies.length) {
      this.message.warning('请至少选择一个买卖点策略');
      return false;
    }
    if (this.needsBenchmark && !this.benchmarkSecurityId) {
      this.message.warning('市场残差反转需要填写已注册的宽基指数 Security ID');
      return false;
    }
    return true;
  }

  runReplay(autoResolveNoData = true): void {
    if (!this.securityId || !this.tradeDate) {
      this.message.warning('请先按股票代码或名称选择标的，并填写日期');
      return;
    }
    if (!this.validateStrategies()) return;
    if (!this.evaluation.horizons_bars.includes(this.evaluation.primary_horizon_bars)) {
      this.evaluation.primary_horizon_bars = this.evaluation.horizons_bars[0] ?? 1;
    }
    const strategies = this.selectedStrategyConfigs();
    this.loading = true;
    this.api.replayTTrading({
      security_id: this.securityId, trade_date: this.tradeDate, period: this.period,
      adjust: 'nf', persistence_mode: 'ephemeral',
      strategy: strategies[0]!, strategies,
      benchmark_security_id: this.benchmarkSecurityId ?? undefined,
      evaluation: { ...this.evaluation },
      include_execution_simulation: false, execution: { ...this.execution },
    }).subscribe({
      next: (result) => { this.result = result; this.loading = false; },
      error: (error) => {
        this.loading = false;
        this.result = null;
        const detail = error.error?.detail;
        if (error.status === 404 && detail?.code === 'NO_MINUTE_BARS') {
          if (autoResolveNoData) {
            this.resolveNearestDate(true);
          } else {
            this.message.warning(detail.message ?? '所选日期没有分钟行情');
          }
          return;
        }
        this.message.error(typeof detail === 'string' ? detail : detail?.message ?? '回放失败');
      },
    });
  }

  runBatch(): void {
    const ids = this.batchSecurityIds.split(',').map((value) => Number(value.trim())).filter((value) => Number.isInteger(value) && value > 0);
    if (!ids.length || !this.batchStartDate || !this.batchEndDate) {
      this.message.warning('请填写 Security IDs 和日期范围');
      return;
    }
    if (!this.validateStrategies()) return;
    const strategies = this.selectedStrategyConfigs();
    this.batchLoading = true;
    this.api.batchReplayTTrading({
      security_ids: [...new Set(ids)], start_date: this.batchStartDate, end_date: this.batchEndDate,
      period: this.period, adjust: 'nf', persistence_mode: 'ephemeral',
      strategy: strategies[0]!, strategies,
      benchmark_security_id: this.benchmarkSecurityId ?? undefined,
      evaluation: { ...this.evaluation },
      include_execution_simulation: false, execution: { ...this.execution },
      include_details: false,
    }).subscribe({
      next: (result) => { this.batchResult = result; this.batchLoading = false; },
      error: (error) => {
        this.batchLoading = false;
        this.batchResult = null;
        this.message.error(error.error?.detail ?? '批量回放失败');
      },
    });
  }

  formatTime(value: string): string { return dayjs(value).format('YYYY-MM-DD HH:mm'); }
  toPercent(value: number | null): number { return Number(((value ?? 0) * 100).toFixed(2)); }
  /** 3-decimal precision for per-signal returns that are typically <0.5%. */
  toPercentPrecise(value: number | null): number { return Number(((value ?? 0) * 100).toFixed(3)); }
  pnlClass(value: number): string { return value > 0 ? 'positive' : value < 0 ? 'negative' : ''; }
}
