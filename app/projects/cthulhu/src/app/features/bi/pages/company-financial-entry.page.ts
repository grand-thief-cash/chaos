import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzAutocompleteModule } from 'ng-zorro-antd/auto-complete';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { BiApiService } from '../services/bi-api.service';
import { BISecuritySearchItem } from '../models/bi.models';

@Component({
  selector: 'app-company-financial-entry-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzCardModule, NzInputModule, NzAutocompleteModule, NzButtonModule, NzTagModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card nzTitle="公司财务入口" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: end; flex-wrap: wrap;">
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">证券代码</label>
            <input nz-input [(ngModel)]="symbol" (ngModelChange)="onSearchChange($event)" [nzAutocomplete]="auto" placeholder="输入证券代码或公司名称" style="width: 260px;" (keyup.enter)="open('overview')" />
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
          <button nz-button nzType="primary" (click)="open('overview')">打开总览</button>
          <button nz-button (click)="open('dupont')">打开杜邦</button>
          <button nz-button (click)="open('quality')">打开质量页</button>
        </div>
        <div style="margin-top: 12px; color: #8c8c8c; font-size: 12px;">当前实现使用固定证券代码输入，不做 Atlas/文本搜索联动。</div>
      </nz-card>

      <nz-card nzTitle="常用入口" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          @for (item of quickSymbols; track item) {
            <button nz-button nzSize="small" (click)="jump(item)">{{ item }}</button>
          }
        </div>
        <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
          <nz-tag nzColor="blue">PhoenixA-backed</nz-tag>
          <nz-tag nzColor="geekblue">PIT as_of_date</nz-tag>
          <nz-tag nzColor="purple">BI Only</nz-tag>
        </div>
      </nz-card>
    </div>
  `,
})
export class CompanyFinancialEntryPageComponent {
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  symbol = '000001';
  asOfDate = new Date().toISOString().slice(0, 10);
  quickSymbols = ['000001', '600000', '600519', '000858'];
  searchResults: BISecuritySearchItem[] = [];

  open(tab: 'overview' | 'dupont' | 'quality'): void {
    const symbol = (this.symbol || '').trim();
    if (!symbol) return;
    this.remember(symbol);
    this.router.navigate(['/bi/financial/company', symbol, tab], {
      queryParams: { as_of_date: this.asOfDate },
    });
  }

  jump(symbol: string): void {
    this.symbol = symbol;
    this.open('overview');
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

  private remember(symbol: string): void {
    const recent = (() => {
      try {
        return JSON.parse(localStorage.getItem('bi-recent-symbols') || '[]') as string[];
      } catch {
        return [] as string[];
      }
    })();
    localStorage.setItem('bi-recent-symbols', JSON.stringify([symbol, ...recent.filter(item => item !== symbol)].slice(0, 8)));
  }
}



