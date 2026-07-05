import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { ArtemisBiService } from '../services/artemis-bi.service';
import { BISecurityItem } from '../models/bi.models';

@Component({
  selector: 'app-bi-stock-list-page',
  standalone: true,
  imports: [CommonModule, FormsModule, NzCardModule, NzButtonModule, NzInputModule, NzTableModule, NzSpinModule, NzTagModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card nzTitle="股票列表" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: end; flex-wrap: wrap; margin-bottom: 16px;">
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">交易所</label>
            <input nz-input [(ngModel)]="exchangeFilter" placeholder="如 SZ / SH" style="width: 120px;" (keyup.enter)="onSearch()" />
          </div>
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">名称/代码搜索</label>
            <input nz-input [(ngModel)]="nameFilter" placeholder="输入名称或代码" style="width: 220px;" (keyup.enter)="onSearch()" />
          </div>
          <button nz-button nzType="primary" (click)="onSearch()">搜索</button>
          <button nz-button (click)="onReset()">重置</button>
        </div>

        @if (loading) {
          <nz-spin nzTip="加载中..."></nz-spin>
        } @else {
          <nz-table #tbl [nzData]="items" nzSize="small" [nzFrontPagination]="false"
                    [nzPageSize]="pageSize" [nzTotal]="total" [nzPageIndex]="pageIndex"
                    (nzPageIndexChange)="onPageChange($event)" [nzShowSizeChanger]="false">
            <thead>
              <tr>
                <th>证券代码</th>
                <th>证券名称</th>
                <th>交易所</th>
                <th>市场</th>
                <th>状态</th>
                <th>上市日期</th>
                <th style="width: 100px;">操作</th>
              </tr>
            </thead>
            <tbody>
              @for (item of tbl.data; track item.security_id) {
                <tr>
                  <td><code>{{ item.symbol }}</code></td>
                  <td>{{ item.name }}</td>
                  <td>{{ item.exchange }}</td>
                  <td>{{ item.market }}</td>
                  <td>
                    <nz-tag [nzColor]="item.status === 'active' ? 'green' : 'red'">
                      {{ item.status === 'active' ? '正常' : '停牌/退市' }}
                    </nz-tag>
                  </td>
                  <td>{{ item.list_date || '-' }}</td>
                  <td>
                    <button nz-button nzSize="small" nzType="primary" (click)="enterCompany(item)">进入</button>
                  </td>
                </tr>
              }
            </tbody>
          </nz-table>
          <div style="margin-top: 12px; color: #8c8c8c; font-size: 12px;">
            共 {{ total }} 条，第 {{ pageIndex }} 页 / {{ totalPages }} 页，每页 {{ pageSize }} 条
          </div>
        }
      </nz-card>
    </div>
  `,
})
export class StockListPageComponent implements OnInit {
  private readonly api = inject(ArtemisBiService);
  private readonly router = inject(Router);

  loading = false;
  items: BISecurityItem[] = [];
  total = 0;
  pageIndex = 1;
  pageSize = 20;

  exchangeFilter = '';
  nameFilter = '';

  market = 'zh_a';

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  }

  ngOnInit(): void {
    this.load();
  }

  onSearch(): void {
    this.pageIndex = 1;
    this.load();
  }

  onReset(): void {
    this.exchangeFilter = '';
    this.nameFilter = '';
    this.pageIndex = 1;
    this.load();
  }

  onPageChange(idx: number): void {
    this.pageIndex = idx;
    this.load();
  }

  enterCompany(item: BISecurityItem): void {
    this.router.navigate(['/bi/company', item.security_id], {
      queryParams: { market: item.market },
    });
  }

  private load(): void {
    this.loading = true;
    const offset = (this.pageIndex - 1) * this.pageSize;
    this.api.getSecurities(this.market, this.pageSize, offset, this.exchangeFilter || undefined, this.nameFilter || undefined).subscribe({
      next: (resp) => {
        this.items = resp.items;
        this.total = resp.total;
        this.loading = false;
      },
      error: () => {
        this.items = [];
        this.total = 0;
        this.loading = false;
      },
    });
  }
}
