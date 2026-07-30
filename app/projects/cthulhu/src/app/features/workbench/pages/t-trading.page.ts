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
  TStrategyConfig,
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
  `],
  template: `
    <div class="page">
      <nz-alert
        nzType="info"
        nzShowIcon
        nzMessage="纯内存 Review 模式"
        nzDescription="分钟行情会持久化；回测参数、信号、成交与报告不会落库。判断发生在当前 K 线收盘，成交模拟在下一根 K 线开盘。"
        style="margin-bottom: 12px;"
      ></nz-alert>

      <nz-tabset>
        <nz-tab nzTitle="逐日回放">
          <nz-card nzSize="small">
            <div class="toolbar">
              <div class="field"><label>Security ID</label><nz-input-number [(ngModel)]="securityId" [nzMin]="1"></nz-input-number></div>
              <div class="field"><label>日期</label><input nz-input type="date" [(ngModel)]="tradeDate" style="width: 145px;" /></div>
              <div class="field"><label>周期</label>
                <nz-select [(ngModel)]="period" style="width: 100px;"><nz-option nzValue="min5" nzLabel="min5"></nz-option></nz-select>
              </div>
              <div class="field"><label>方向</label>
                <nz-select [(ngModel)]="strategy.direction" style="width: 120px;">
                  <nz-option nzValue="buy_first" nzLabel="先买后卖"></nz-option>
                  <nz-option nzValue="sell_first" nzLabel="先卖后买"></nz-option>
                </nz-select>
              </div>
              <div class="field"><label>数量（股）</label><nz-input-number [(ngModel)]="execution.quantity" [nzMin]="100" [nzStep]="100"></nz-input-number></div>
              <button nz-button (click)="moveDay(-1)" [disabled]="loading">上一天</button>
              <button nz-button nzType="primary" (click)="runReplay()" [nzLoading]="loading">运行 Review</button>
              <button nz-button (click)="moveDay(1)" [disabled]="loading">下一天</button>
              <nz-tag nzColor="blue">ephemeral · 不落库</nz-tag>
            </div>
          </nz-card>

          <nz-collapse style="margin-top: 10px;">
            <nz-collapse-panel nzHeader="策略与交易成本参数" [nzActive]="false">
              <div class="toolbar">
                <div class="field"><label>窗口</label><nz-input-number [(ngModel)]="strategy.window" [nzMin]="5" [nzMax]="120"></nz-input-number></div>
                <div class="field"><label>入场 Z</label><nz-input-number [(ngModel)]="strategy.entry_z" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>离场 Z</label><nz-input-number [(ngModel)]="strategy.exit_z" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>买侧 RSI</label><nz-input-number [(ngModel)]="strategy.entry_rsi"></nz-input-number></div>
                <div class="field"><label>卖侧 RSI</label><nz-input-number [(ngModel)]="strategy.exit_rsi"></nz-input-number></div>
                <div class="field"><label>确认 bars</label><nz-input-number [(ngModel)]="strategy.confirmation_bars" [nzMin]="1"></nz-input-number></div>
                <div class="field"><label>冷却 bars</label><nz-input-number [(ngModel)]="strategy.cooldown_bars" [nzMin]="0"></nz-input-number></div>
                <div class="field"><label>最多往返</label><nz-input-number [(ngModel)]="strategy.max_round_trips" [nzMin]="1"></nz-input-number></div>
                <div class="field"><label>滑点(bps)</label><nz-input-number [(ngModel)]="execution.slippage_bps" [nzStep]="0.1"></nz-input-number></div>
                <div class="field"><label>佣金率</label><nz-input-number [(ngModel)]="execution.commission_rate" [nzStep]="0.0001"></nz-input-number></div>
                <div class="field"><label>最低佣金</label><nz-input-number [(ngModel)]="execution.minimum_commission"></nz-input-number></div>
              </div>
            </nz-collapse-panel>
          </nz-collapse>

          @if (result) {
            <div class="stats">
              <nz-card nzSize="small"><nz-statistic nzTitle="净收益" [nzValue]="result.summary.net_pnl" [nzSuffix]="' 元'" [ngClass]="pnlClass(result.summary.net_pnl)"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="胜率" [nzValue]="toPercent(result.summary.win_rate)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="完整往返" [nzValue]="result.summary.round_trips"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="Profit Factor" [nzValue]="result.summary.profit_factor ?? '-'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="信号 / 成交" [nzValue]="result.signals.length" [nzSuffix]="' / ' + result.fills.length"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="数据 bars" [nzValue]="result.data_quality.bar_count"></nz-statistic></nz-card>
            </div>
            <nz-card [nzTitle]="result.run_meta.symbol + ' · ' + result.run_meta.trade_date + ' · 买卖点 Review'" nzSize="small">
              <app-t-trading-chart [bars]="result.bars" [signals]="result.signals" [fills]="result.fills"></app-t-trading-chart>
              <div class="meta">红色“买”/绿色“卖”是判断点；菱形是下一根 K 线开盘成交点。意外缺口 {{ result.data_quality.unexpected_gap_count }}，零成交量 bars {{ result.data_quality.zero_volume_bars }}。</div>
            </nz-card>
            <nz-card nzTitle="信号审计" nzSize="small" style="margin-top: 12px;">
              <nz-table #signalTable [nzData]="result.signals" [nzPageSize]="10" nzSize="small">
                <thead><tr><th>判断时间</th><th>方向</th><th>判断价</th><th>置信度</th><th>Z</th><th>RSI</th><th>原因</th></tr></thead>
                <tbody>
                  @for (signal of signalTable.data; track signal.signal_id) {
                    <tr>
                      <td>{{ formatTime(signal.decision_time) }}</td>
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
              <nz-card nzSize="small"><nz-statistic nzTitle="净收益" [nzValue]="batchResult.summary.net_pnl" [nzSuffix]="' 元'" [ngClass]="pnlClass(batchResult.summary.net_pnl)"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="胜率" [nzValue]="toPercent(batchResult.summary.win_rate)" [nzSuffix]="'%'"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="有效交易日" [nzValue]="batchResult.summary.days_with_trades || 0"></nz-statistic></nz-card>
              <nz-card nzSize="small"><nz-statistic nzTitle="跳过 / 失败" [nzValue]="batchResult.skipped.length" [nzSuffix]="' / ' + batchResult.failures.length"></nz-statistic></nz-card>
            </div>
            <nz-table #batchTable [nzData]="batchResult.by_security" nzSize="small">
              <thead><tr><th>Security ID</th><th>回放日</th><th>往返</th><th>胜率</th><th>净收益</th><th>费用</th><th>平均收益率</th></tr></thead>
              <tbody>
                @for (row of batchTable.data; track row.security_id) {
                  <tr><td>{{ row.security_id }}</td><td>{{ row.replay_days }}</td><td>{{ row.round_trips }}</td><td>{{ row.win_rate | percent:'1.1-1' }}</td><td [ngClass]="pnlClass(row.net_pnl)">{{ row.net_pnl }}</td><td>{{ row.total_fee }}</td><td>{{ row.average_return_pct | number:'1.3-3' }}%</td></tr>
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
  period: 'min5' = 'min5';
  loading = false;
  result: TReplayResponse | null = null;
  batchLoading = false;
  batchSecurityIds = '';
  batchStartDate = dayjs().subtract(30, 'day').format('YYYY-MM-DD');
  batchEndDate = dayjs().format('YYYY-MM-DD');
  batchResult: TBatchReplayResponse | null = null;

  strategy: TStrategyConfig = {
    direction: 'buy_first', window: 20, entry_z: 1.25, exit_z: 1,
    entry_rsi: 35, exit_rsi: 65, confirmation_bars: 3,
    cooldown_bars: 2, max_round_trips: 2,
  };
  execution: TExecutionConfig = {
    quantity: 100, commission_rate: 0.0003, minimum_commission: 5,
    stamp_duty_rate_on_sell: 0.0005, transfer_fee_rate: 0.00001, slippage_bps: 1,
  };

  moveDay(delta: number): void {
    this.tradeDate = dayjs(this.tradeDate).add(delta, 'day').format('YYYY-MM-DD');
    this.runReplay();
  }

  runReplay(): void {
    if (!this.securityId || !this.tradeDate) {
      this.message.warning('请填写有效的 Security ID 和日期');
      return;
    }
    this.loading = true;
    this.api.replayTTrading({
      security_id: this.securityId, trade_date: this.tradeDate, period: this.period,
      adjust: 'nf', persistence_mode: 'ephemeral',
      strategy: { ...this.strategy }, execution: { ...this.execution },
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
    this.batchLoading = true;
    this.api.batchReplayTTrading({
      security_ids: [...new Set(ids)], start_date: this.batchStartDate, end_date: this.batchEndDate,
      period: this.period, adjust: 'nf', persistence_mode: 'ephemeral',
      strategy: { ...this.strategy }, execution: { ...this.execution },
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
  toPercent(value: number): number { return Number((value * 100).toFixed(1)); }
  pnlClass(value: number): string { return value > 0 ? 'positive' : value < 0 ? 'negative' : ''; }
}
