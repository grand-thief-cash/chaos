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

import {
  TBatchReplayResponse,
  TExecutionConfig,
  TReplayResponse,
  TSignalEvaluationConfig,
  TStrategyConfig,
  TStrategyName,
} from '../models/workbench.model';
import { WorkbenchApiService } from '../services/workbench-api.service';
import { TTradingChartComponent } from '../ui/t-trading-chart.component';

@Component({
  selector: 'app-t-trading-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzAlertModule, NzButtonModule, NzCardModule,
    NzCollapseModule, NzFormModule, NzInputModule, NzInputNumberModule,
    NzSelectModule, NzStatisticModule, NzTableModule, NzTabsModule, NzTagModule,
    TTradingChartComponent,
  ],
  styles: [`
    .page { padding: 16px; }
    .toolbar { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
    .field label { display: block; margin-bottom: 4px; color: #666; font-size: 12px; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; margin: 12px 0; }
    .meta { color: #888; font-size: 12px; }
    .positive { color: #cf1322; }
    .negative { color: #237804; }
    .strategy-select { min-width: 340px; max-width: 560px; }
  `],
  template: `
    <div class="page">
      <nz-alert
        nzType="info"
        nzShowIcon
        nzMessage="信号优先的纯内存 Review"
        nzDescription="分钟行情按需增量持久化；策略参数、信号和报告不落库。主评估观察买点之后上涨多少、卖点之后下跌多少，成交模拟默认关闭。"
        style="margin-bottom: 12px;"
      ></nz-alert>

      <nz-tabset>
        <nz-tab nzTitle="逐日回放">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field"><label>Security ID</label><nz-input-number [(ngModel)]="securityId" [nzMin]="1"></nz-input-number></div>
              <div class="field"><label>日期</label><input nz-input type="date" [(ngModel)]="tradeDate" style="width: 145px;" /></div>
              <div class="field"><label>周期</label>
                <nz-select [(ngModel)]="period" (ngModelChange)="onPeriodChange($event)" style="width: 100px;">
                  <nz-option nzValue="min1" nzLabel="1 分钟"></nz-option>
                  <nz-option nzValue="min5" nzLabel="5 分钟"></nz-option>
                </nz-select>
              </div>
              <div class="field"><label>买卖点策略（可多选）</label>
                <nz-select [(ngModel)]="selectedStrategies" nzMode="multiple" class="strategy-select" nzPlaceHolder="至少选择一个策略">
                  @for (option of strategyOptions; track option.value) {
                    <nz-option [nzValue]="option.value" [nzLabel]="option.label"></nz-option>
                  }
                </nz-select>
              </div>
              @if (needsBenchmark) {
                <div class="field"><label>宽基指数 Security ID</label><nz-input-number [(ngModel)]="benchmarkSecurityId" [nzMin]="1"></nz-input-number></div>
              }
              <div class="field"><label>方向</label>
                <nz-select [(ngModel)]="strategy.direction" style="width: 120px;">
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
            <nz-collapse-panel nzHeader="策略与事件研究参数" [nzActive]="false">
              <div class="toolbar">
                <div class="field"><label>窗口</label><nz-input-number [(ngModel)]="strategy.window" [nzMin]="5" [nzMax]="120"></nz-input-number></div>
                <div class="field"><label>入场 Z</label><nz-input-number [(ngModel)]="strategy.entry_z" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>离场 Z</label><nz-input-number [(ngModel)]="strategy.exit_z" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>买侧 RSI</label><nz-input-number [(ngModel)]="strategy.entry_rsi"></nz-input-number></div>
                <div class="field"><label>卖侧 RSI</label><nz-input-number [(ngModel)]="strategy.exit_rsi"></nz-input-number></div>
                <div class="field"><label>确认 bars</label><nz-input-number [(ngModel)]="strategy.confirmation_bars" [nzMin]="1"></nz-input-number></div>
                <div class="field"><label>冷却 bars</label><nz-input-number [(ngModel)]="strategy.cooldown_bars" [nzMin]="0"></nz-input-number></div>
                <div class="field"><label>最多往返</label><nz-input-number [(ngModel)]="strategy.max_round_trips" [nzMin]="1"></nz-input-number></div>
                <div class="field"><label>EMA 快 / 慢</label><nz-input-number [(ngModel)]="strategy.ema_fast" [nzMin]="2"></nz-input-number> / <nz-input-number [(ngModel)]="strategy.ema_slow" [nzMin]="3"></nz-input-number></div>
                <div class="field"><label>MACD signal</label><nz-input-number [(ngModel)]="strategy.macd_signal" [nzMin]="2"></nz-input-number></div>
                <div class="field"><label>最小量比</label><nz-input-number [(ngModel)]="strategy.min_volume_ratio" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>Bollinger Z</label><nz-input-number [(ngModel)]="strategy.bollinger_z" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>开盘区间 bars</label><nz-input-number [(ngModel)]="strategy.opening_range_bars" [nzMin]="2"></nz-input-number></div>
                <div class="field"><label>同分钟相对量阈值</label><nz-input-number [(ngModel)]="strategy.relative_volume_tod_threshold" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>同分钟历史日数</label><nz-input-number [(ngModel)]="strategy.min_time_of_day_history_days" [nzMin]="5"></nz-input-number></div>
                <div class="field"><label>市场 beta 窗口</label><nz-input-number [(ngModel)]="strategy.market_beta_window" [nzMin]="5"></nz-input-number></div>
                <div class="field"><label>残差 Z 阈值</label><nz-input-number [(ngModel)]="strategy.residual_z_threshold" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>30 分钟 EMA 快 / 慢</label><nz-input-number [(ngModel)]="strategy.higher_ema_fast" [nzMin]="2"></nz-input-number> / <nz-input-number [(ngModel)]="strategy.higher_ema_slow" [nzMin]="3"></nz-input-number></div>
                <div class="field"><label>日线趋势窗口</label><nz-input-number [(ngModel)]="strategy.daily_trend_window" [nzMin]="5"></nz-input-number></div>
                <div class="field"><label>回踩容差 ATR</label><nz-input-number [(ngModel)]="strategy.pullback_tolerance_atr" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>主评估 horizon</label><nz-input-number [(ngModel)]="evaluation.primary_horizon_bars" [nzMin]="1"></nz-input-number></div>
                <div class="field"><label>目标 / 风险阈值</label><nz-input-number [(ngModel)]="evaluation.target_return" [nzStep]="0.001"></nz-input-number> / <nz-input-number [(ngModel)]="evaluation.stop_return" [nzStep]="0.001"></nz-input-number></div>
              </div>
            </nz-collapse-panel>
          </nz-collapse>

          @if (result) {
            <div class="stats">
              <nz-card nzSize="small"><nz-statistic [nzTitle]="result.summary.horizon_bars + ' bars 方向正确率'" [nzValue]="toPercent(result.summary.directional_accuracy)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均方向收益" [nzValue]="toPercent(result.summary.mean_directional_return)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均 MFE" [nzValue]="toPercent(result.summary.mean_mfe)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="平均 MAE" [nzValue]="toPercent(result.summary.mean_mae)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="MFE / MAE" [nzValue]="result.summary.edge_ratio ?? '-'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="可评估信号" [nzValue]="result.summary.evaluable_signal_count" [nzSuffix]="' / ' + result.summary.signal_count"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="数据 bars" [nzValue]="result.data_quality.bar_count"></nz-statistic></nz-card>
            </div>
            <nz-card [nzTitle]="result.run_meta.symbol + ' · ' + result.run_meta.trade_date + ' · 买卖点 Review'" nzSize="small">
              <app-t-trading-chart [bars]="result.bars" [signals]="result.signals" [fills]="result.fills"></app-t-trading-chart>
              <div class="meta">图例按策略分色，“买”是向上图钉、“卖”是向下图钉。主评估观察其后 {{ result.summary.horizon_bars }} 根 K 线，不模拟成交；MFE/MAE 分别表示顺向最大空间与逆向最大波动。意外缺口 {{ result.data_quality.unexpected_gap_count }}，零成交量 bars {{ result.data_quality.zero_volume_bars }}。</div>
            </nz-card>
            @if (result.signal_evaluation.by_strategy.length) {
              <nz-card nzTitle="按策略的信号效果" nzSize="small" style="margin-top: 12px;">
                <nz-table #strategyTable [nzData]="result.signal_evaluation.by_strategy" [nzShowPagination]="false" nzSize="small">
                  <thead><tr><th>策略</th><th>信号</th><th>方向正确率</th><th>平均方向收益</th><th>平均 MFE</th><th>平均 MAE</th><th>MFE / MAE</th></tr></thead>
                  <tbody>
                    @for (row of strategyTable.data; track row.strategy) {
                      <tr>
                        <td><nz-tag [nzColor]="strategyColor(row.strategy)">{{ strategyLabel(row.strategy) }}</nz-tag></td>
                        <td>{{ row.evaluable_signal_count }} / {{ row.signal_count }}</td>
                        <td>{{ row.directional_accuracy | percent:'1.1-1' }}</td>
                        <td>{{ row.mean_directional_return | percent:'1.2-2' }}</td>
                        <td>{{ row.mean_mfe | percent:'1.2-2' }}</td>
                        <td>{{ row.mean_mae | percent:'1.2-2' }}</td>
                        <td>{{ row.edge_ratio ?? '-' }}</td>
                      </tr>
                    }
                  </tbody>
                </nz-table>
              </nz-card>
            }
            <nz-card nzTitle="信号审计" nzSize="small" style="margin-top: 12px;">
              <nz-table #signalTable [nzData]="result.signals" [nzPageSize]="10" nzSize="small">
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
    </div>
  `,
})
export class TTradingPageComponent {
  private api = inject(WorkbenchApiService);
  private message = inject(NzMessageService);

  securityId: number | null = null;
  tradeDate = dayjs().format('YYYY-MM-DD');
  period: 'min1' | 'min5' = 'min1';
  selectedStrategies: TStrategyName[] = ['causal_mean_reversion_v1'];
  benchmarkSecurityId: number | null = null;
  loading = false;
  result: TReplayResponse | null = null;
  batchLoading = false;
  batchSecurityIds = '';
  batchStartDate = dayjs().subtract(30, 'day').format('YYYY-MM-DD');
  batchEndDate = dayjs().format('YYYY-MM-DD');
  batchResult: TBatchReplayResponse | null = null;
  readonly strategyOptions: Array<{ value: TStrategyName; label: string; color: string }> = [
    { value: 'causal_mean_reversion_v1', label: 'Z-score + RSI + VWAP 反转', color: 'magenta' },
    { value: 'macd_volume_momentum_v1', label: 'MACD + 量能 + 分钟 EMA', color: 'blue' },
    { value: 'vwap_bollinger_reversion_v1', label: 'VWAP + Bollinger + 拒绝影线', color: 'purple' },
    { value: 'opening_range_breakout_v1', label: '开盘区间 + 量能突破', color: 'orange' },
    { value: 'time_of_day_volume_momentum_v1', label: '同分钟历史量比 + 价格确认', color: 'cyan' },
    { value: 'market_residual_reversal_v1', label: '宽基市场残差反转', color: 'geekblue' },
    { value: 'multi_timeframe_pullback_v1', label: '日线 / 30 分钟顺势回踩', color: 'green' },
  ];

  strategy: TStrategyConfig = {
    strategy: 'causal_mean_reversion_v1',
    direction: 'buy_first', window: 20, entry_z: 1.25, exit_z: 1,
    entry_rsi: 35, exit_rsi: 65, confirmation_bars: 3,
    cooldown_bars: 2, max_round_trips: 2,
    ema_fast: 5, ema_slow: 13, macd_signal: 4, min_volume_ratio: 1.2,
    bollinger_z: 1.5, reversal_wick_ratio: 0.25, max_trend_strength_atr: 0.8,
    atr_window: 14, opening_range_bars: 6, breakout_atr_buffer: 0.1,
    relative_volume_tod_threshold: 1.5, min_time_of_day_history_days: 20,
    market_beta_window: 20, residual_z_threshold: 1.5,
    higher_ema_fast: 5, higher_ema_slow: 10, daily_trend_window: 20,
    pullback_tolerance_atr: 0.5,
  };
  evaluation: TSignalEvaluationConfig = {
    horizons_bars: [1, 3, 5, 15], primary_horizon_bars: 5,
    target_return: 0.005, stop_return: 0.003,
  };
  execution: TExecutionConfig = {
    quantity: 100, commission_rate: 0.0003, minimum_commission: 5,
    stamp_duty_rate_on_sell: 0.0005, transfer_fee_rate: 0.00001, slippage_bps: 1,
  };

  moveDay(delta: number): void {
    this.tradeDate = dayjs(this.tradeDate).add(delta, 'day').format('YYYY-MM-DD');
    this.runReplay();
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

  strategyLabel(strategy: TStrategyName): string {
    return this.strategyOptions.find((option) => option.value === strategy)?.label ?? strategy;
  }

  strategyColor(strategy: TStrategyName): string {
    return this.strategyOptions.find((option) => option.value === strategy)?.color ?? 'default';
  }

  private selectedStrategyConfigs(): TStrategyConfig[] {
    return this.selectedStrategies.map((name) => ({ ...this.strategy, strategy: name }));
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

  runReplay(): void {
    if (!this.securityId || !this.tradeDate) {
      this.message.warning('请填写有效的 Security ID 和日期');
      return;
    }
    if (!this.validateStrategies()) return;
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
        this.message.error(error.error?.detail ?? '回放失败');
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
  pnlClass(value: number): string { return value > 0 ? 'positive' : value < 0 ? 'negative' : ''; }
}
