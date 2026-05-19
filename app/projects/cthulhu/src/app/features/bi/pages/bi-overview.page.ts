import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzAutocompleteModule } from 'ng-zorro-antd/auto-complete';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzListModule } from 'ng-zorro-antd/list';
import { BiApiService } from '../services/bi-api.service';
import { BISecuritySearchItem } from '../models/bi.models';

@Component({
  selector: 'app-bi-overview-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzCardModule, NzButtonModule, NzInputModule, NzAutocompleteModule, NzTagModule, NzListModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card nzTitle="BI Overview" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div>
            <div style="font-size: 20px; font-weight: 600;">财务 BI MVP</div>
            <div style="color: #8c8c8c; margin-top: 4px;">
              当前只关注 BI 结构化财务看板，数据链路为 PhoenixA → Artemis BI → Cthulhu BI，不包含 Atlas / LLM / narrative 集成。
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: end;">
            <div>
              <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">证券代码</label>
              <input nz-input [(ngModel)]="symbol" (ngModelChange)="onSearchChange($event)" [nzAutocomplete]="auto" placeholder="例如 000001 / 平安 / 茅台" style="width: 220px;" (keyup.enter)="goToOverview()" />
              <nz-autocomplete #auto>
                @for (item of searchResults; track item.symbol) {
                  <nz-auto-option [nzValue]="item.symbol">{{ item.symbol }} · {{ item.name }}</nz-auto-option>
                }
              </nz-autocomplete>
            </div>
            <div>
              <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">As Of Date</label>
              <input nz-input type="date" [(ngModel)]="asOfDate" style="width: 180px;" />
            </div>
            <button nz-button nzType="primary" (click)="goToOverview()">进入公司总览</button>
            <button nz-button (click)="goToDupont()">进入杜邦分析</button>
            <button nz-button (click)="goToQuality()">进入质量页</button>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <nz-tag nzColor="blue">Phase 1</nz-tag>
            <nz-tag nzColor="purple">Dashboard</nz-tag>
            <nz-tag nzColor="geekblue">Dupont</nz-tag>
            <nz-tag nzColor="cyan">Quality</nz-tag>
            <nz-tag nzColor="orange">No Atlas Scope</nz-tag>
          </div>
        </div>
      </nz-card>

      <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px;">
        <nz-card nzTitle="MVP 能力入口" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <button nz-button nzBlock (click)="goToOverview()">公司财务总览</button>
            <button nz-button nzBlock (click)="goToDupont()">杜邦分析</button>
            <button nz-button nzBlock (click)="goToQuality()">经营质量 / 现金流 / 周转 / 偿债</button>
            <button nz-button nzBlock (click)="goToMetrics()">指标字典</button>
          </div>
        </nz-card>

        <nz-card nzTitle="最近访问" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          @if (recentSymbols.length > 0) {
            <nz-list nzBordered="false" [nzDataSource]="recentSymbols" [nzRenderItem]="itemTpl"></nz-list>
            <ng-template #itemTpl let-item>
              <nz-list-item>
                <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                  <span>{{ item }}</span>
                  <div style="display: flex; gap: 6px;">
                    <button nz-button nzSize="small" (click)="openRecent(item, 'overview')">总览</button>
                    <button nz-button nzSize="small" (click)="openRecent(item, 'dupont')">杜邦</button>
                    <button nz-button nzSize="small" (click)="openRecent(item, 'quality')">质量</button>
                  </div>
                </div>
              </nz-list-item>
            </ng-template>
          } @else {
            <div style="color: #8c8c8c;">暂无最近访问记录</div>
          }
        </nz-card>
      </div>

      <nz-card nzTitle="边界说明" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <ul style="margin: 0; padding-left: 18px; color: #595959; line-height: 1.8;">
          <li>当前仅展示结构化财务指标与规则预警</li>
          <li>同比展示优先使用当前值 / 去年同期值 / 同比变动额 / 同比增长</li>
          <li>非金融公司优先适配；金融行业当前仅部分字段可展示</li>
          <li>本轮不引入 Atlas、LLM、财报原文或 narrative 页面</li>
        </ul>
      </nz-card>
    </div>
  `,
})
export class BiOverviewPageComponent {
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  symbol = '000001';
  asOfDate = new Date().toISOString().slice(0, 10);
  searchResults: BISecuritySearchItem[] = [];

  get recentSymbols(): string[] {
    try {
      return JSON.parse(localStorage.getItem('bi-recent-symbols') || '[]');
    } catch {
      return [];
    }
  }

  goToOverview(): void {
    this.navigate('overview');
  }

  goToDupont(): void {
    this.navigate('dupont');
  }

  goToQuality(): void {
    this.navigate('quality');
  }

  goToMetrics(): void {
    this.router.navigate(['/bi/metrics']);
  }

  onSearchChange(value: string): void {
    const query = (value || '').trim();
    if (query.length < 2) {
      this.searchResults = [];
      return;
    }
    this.api.searchSecurities(query).subscribe({
      next: (resp) => {
        this.searchResults = resp.items;
      },
      error: () => {
        this.searchResults = [];
      },
    });
  }

  openRecent(symbol: string, tab: 'overview' | 'dupont' | 'quality'): void {
    this.symbol = symbol;
    this.navigate(tab);
  }

  private navigate(tab: 'overview' | 'dupont' | 'quality'): void {
    const symbol = (this.symbol || '').trim();
    if (!symbol) return;
    this.remember(symbol);
    this.router.navigate(['/bi/financial/company', symbol, tab], {
      queryParams: { as_of_date: this.asOfDate },
    });
  }

  private remember(symbol: string): void {
    const merged = [symbol, ...this.recentSymbols.filter(item => item !== symbol)].slice(0, 8);
    localStorage.setItem('bi-recent-symbols', JSON.stringify(merged));
  }
}




