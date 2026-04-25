import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzRadioModule } from 'ng-zorro-antd/radio';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzAutocompleteModule } from 'ng-zorro-antd/auto-complete';
import { WorkbenchApiService } from '../services/workbench-api.service';
import {
  IndustryCategory,
  IndustryConstituent,
  IndustryDailyBar,
} from '../models/workbench.model';

const RECENT_SEARCH_KEY = 'industry-recent-searches';
const MAX_RECENT = 8;

const POPULAR_KEYWORDS = [
  '农林牧渔', '采掘', '化工', '钢铁', '有色金属',
  '电子', '计算机', '通信', '医药生物', '食品饮料',
  '银行', '非银金融', '房地产', '汽车', '家用电器',
  '机械设备', '电气设备', '国防军工', '建筑材料', '交通运输',
];

@Component({
  selector: 'app-industry-explorer',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    NzCardModule, NzInputModule, NzButtonModule, NzTableModule,
    NzTabsModule, NzTagModule, NzSpinModule, NzEmptyModule,
    NzIconModule, NzRadioModule, NzDividerModule, NzBadgeModule,
    NzAutocompleteModule,
  ],
  template: `
    <div style="padding: 0; display: flex; flex-direction: column; gap: 12px;">
      <!-- Top: Search Bar -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap;">
          <div>
            <nz-radio-group [(ngModel)]="searchMode" nzSize="small" nzButtonStyle="solid"
              (ngModelChange)="onSearchModeChange()">
              <label nz-radio-button nzValue="industry">Industry → Stocks</label>
              <label nz-radio-button nzValue="stock">Stock → Industries</label>
            </nz-radio-group>
          </div>
          <div style="max-width: 320px; min-width: 180px;">
            @if (searchMode === 'industry') {
              <input nz-input [(ngModel)]="industrySearchText" placeholder="Search industry name..."
                nzSize="small" (keyup.enter)="searchIndustries()"
                [nzAutocomplete]="autoIndustry" />
              <nz-autocomplete #autoIndustry [nzDataSource]="industrySuggestions"></nz-autocomplete>
            } @else {
              <input nz-input [(ngModel)]="stockCode" placeholder="Stock code, e.g. 600000"
                nzSize="small" (keyup.enter)="searchByStock()"
                [nzAutocomplete]="autoStock" />
              <nz-autocomplete #autoStock [nzDataSource]="recentStockSearches"></nz-autocomplete>
            }
          </div>
          <button nz-button nzType="primary" nzSize="small" [nzLoading]="loadingSearch"
            (click)="searchMode === 'industry' ? searchIndustries() : searchByStock()">
            <span nz-icon nzType="search"></span> Search
          </button>
        </div>
      </nz-card>

      <!-- Main content: two panels -->
      <div style="display: flex; gap: 12px; min-height: 500px;">
        <!-- Left: Category / Search results -->
        <nz-card nzSize="small" [nzBordered]="false"
          style="flex: 0 0 420px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: auto;">
          <div style="margin-bottom: 8px;">
            @if (categoryPath.length > 0) {
              <div style="display: flex; gap: 4px; flex-wrap: wrap; align-items: center; margin-bottom: 8px;">
                <a style="font-size: 12px; color: #1890ff; cursor: pointer;" (click)="navigateToRoot()">All</a>
                @for (bc of categoryPath; track bc.code; let i = $index) {
                  <span style="font-size: 12px; color: #999;">›</span>
                  @if (i < categoryPath.length - 1) {
                    <a style="font-size: 12px; color: #1890ff; cursor: pointer;"
                      (click)="navigateTo(bc)">{{ bc.name }}</a>
                  } @else {
                    <span style="font-size: 12px; font-weight: 500;">{{ bc.name }}</span>
                  }
                }
              </div>
            }
          </div>

          @if (loadingSearch) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else if (searchMode === 'industry' && categories.length > 0) {
            <nz-table #catTable [nzData]="categories" nzSize="small" [nzShowPagination]="false"
              [nzScroll]="{ y: '420px' }" nzFrontPagination="false">
              <thead>
                <tr>
                  <th nzWidth="80px">Code</th>
                  <th>Name</th>
                  <th nzWidth="50px">Level</th>
                  <th nzWidth="60px"></th>
                </tr>
              </thead>
              <tbody>
                @for (cat of catTable.data; track cat.code) {
                  <tr [style.background]="selectedCategory?.code === cat.code ? '#e6f7ff' : ''"
                    style="cursor: pointer;" (click)="selectCategory(cat)">
                    <td style="font-size: 12px; font-family: monospace;">{{ cat.code }}</td>
                    <td>
                      <span style="font-size: 13px;">{{ cat.name }}</span>
                      @if (!cat.is_leaf) {
                        <nz-badge nzStatus="processing" style="margin-left: 4px;"></nz-badge>
                      }
                    </td>
                    <td style="font-size: 12px; text-align: center;">
                      <nz-tag [nzColor]="cat.level === 1 ? 'blue' : cat.level === 2 ? 'green' : 'orange'">
                        L{{ cat.level }}
                      </nz-tag>
                    </td>
                    <td>
                      @if (!cat.is_leaf) {
                        <button nz-button nzType="link" nzSize="small" (click)="drillDown(cat); $event.stopPropagation()">
                          <span nz-icon nzType="right"></span>
                        </button>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          } @else if (searchMode === 'stock' && stockIndustries.length > 0) {
            <div style="font-size: 13px; font-weight: 500; margin-bottom: 8px;">
              Industries for {{ stockCode }}
              <nz-tag>{{ stockIndustries.length }}</nz-tag>
            </div>
            <nz-table #siTable [nzData]="stockIndustries" nzSize="small" [nzShowPagination]="false"
              [nzScroll]="{ y: '420px' }" nzFrontPagination="false">
              <thead>
                <tr>
                  <th nzWidth="100px">Index Code</th>
                  <th>Index Name</th>
                  <th nzWidth="90px">In Date</th>
                </tr>
              </thead>
              <tbody>
                @for (si of siTable.data; track si.index_code) {
                  <tr style="cursor: pointer;" (click)="selectConstituent(si)"
                    [style.background]="selectedIndexCode === si.index_code ? '#e6f7ff' : ''">
                    <td style="font-size: 12px; font-family: monospace;">{{ si.index_code }}</td>
                    <td style="font-size: 13px;">{{ si.index_name }}</td>
                    <td style="font-size: 12px;">{{ si.in_date }}</td>
                  </tr>
                }
              </tbody>
            </nz-table>
          } @else if (!initialLoaded) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else {
            <div style="padding: 16px 0;">
              <div style="font-size: 13px; color: #666; margin-bottom: 12px;">
                @if (searchMode === 'industry') {
                  <span nz-icon nzType="bulb" nzTheme="outline" style="margin-right: 4px;"></span>
                  Try searching or click a keyword:
                } @else {
                  <span nz-icon nzType="search" nzTheme="outline" style="margin-right: 4px;"></span>
                  Enter a stock code to find its industry memberships
                }
              </div>
              @if (searchMode === 'industry') {
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                  @for (kw of popularKeywords; track kw) {
                    <nz-tag style="cursor: pointer;" (click)="quickSearch(kw)">{{ kw }}</nz-tag>
                  }
                </div>
                @if (recentIndustrySearches.length > 0) {
                  <nz-divider nzText="Recent Searches" nzOrientation="left"
                    style="margin: 12px 0 8px;"></nz-divider>
                  <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                    @for (r of recentIndustrySearches; track r) {
                      <nz-tag nzColor="blue" style="cursor: pointer;" (click)="quickSearch(r)">{{ r }}</nz-tag>
                    }
                  </div>
                }
              }
            </div>
          }
        </nz-card>

        <!-- Right: Details panel -->
        <nz-card nzSize="small" [nzBordered]="false"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: auto;">
          <nz-tabset nzSize="small" [nzAnimated]="false">
            <!-- Tab 1: Constituents -->
            <nz-tab nzTitle="Constituents">
              @if (selectedIndexCode) {
                <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 13px; font-weight: 500;">
                    {{ selectedIndexName || selectedIndexCode }}
                    @if (constituents.length > 0) {
                      <nz-tag nzColor="blue">{{ constituents.length }} stocks</nz-tag>
                    }
                  </span>
                </div>
                @if (loadingConstituents) {
                  <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
                } @else if (constituents.length > 0) {
                  <nz-table #conTable [nzData]="constituents" nzSize="small" [nzShowPagination]="false"
                    [nzScroll]="{ y: '400px' }" nzFrontPagination="false">
                    <thead>
                      <tr>
                        <th nzWidth="100px">Stock Code</th>
                        <th>Index Name</th>
                        <th nzWidth="90px">In Date</th>
                        <th nzWidth="90px">Out Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (con of conTable.data; track con.con_code) {
                        <tr>
                          <td style="font-size: 12px; font-family: monospace;">{{ con.con_code }}</td>
                          <td style="font-size: 13px;">{{ con.index_name }}</td>
                          <td style="font-size: 12px;">{{ con.in_date || '-' }}</td>
                          <td style="font-size: 12px;">{{ con.out_date || '-' }}</td>
                        </tr>
                      }
                    </tbody>
                  </nz-table>
                } @else {
                  <nz-empty nzNotFoundContent="No constituents found"></nz-empty>
                }
              } @else {
                <nz-empty nzNotFoundContent="Select an industry to view constituents"></nz-empty>
              }
            </nz-tab>

            <!-- Tab 2: Daily Bars -->
            <nz-tab nzTitle="Daily Bars">
              @if (selectedIndexCode) {
                <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
                  <input nz-input type="date" [(ngModel)]="dailyStartDate" nzSize="small" style="width: 140px;" />
                  <input nz-input type="date" [(ngModel)]="dailyEndDate" nzSize="small" style="width: 140px;" />
                  <button nz-button nzType="primary" nzSize="small" [nzLoading]="loadingDaily"
                    (click)="loadIndustryDaily()">Load</button>
                  <span style="font-size: 12px; color: #999;">{{ dailyBars.length }} bars</span>
                </div>
                @if (loadingDaily) {
                  <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
                } @else if (dailyBars.length > 0) {
                  <nz-table #dailyTable [nzData]="dailyBars" nzSize="small"
                    [nzScroll]="{ y: '380px', x: '900px' }" [nzShowPagination]="false" nzFrontPagination="false">
                    <thead>
                      <tr>
                        <th nzWidth="90px" nzLeft>Date</th>
                        <th nzWidth="75px">Open</th>
                        <th nzWidth="75px">High</th>
                        <th nzWidth="75px">Low</th>
                        <th nzWidth="75px">Close</th>
                        <th nzWidth="75px">PreClose</th>
                        <th nzWidth="100px">Volume</th>
                        <th nzWidth="100px">Amount</th>
                        <th nzWidth="70px">PE</th>
                        <th nzWidth="70px">PB</th>
                        <th nzWidth="110px">TotalCap(万)</th>
                        <th nzWidth="110px">FloatCap(万)</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (bar of dailyTable.data; track bar.trade_date) {
                        <tr>
                          <td nzLeft style="font-size: 12px; font-family: monospace;">{{ bar.trade_date }}</td>
                          <td style="font-size: 12px;">{{ bar.open | number:'1.2-2' }}</td>
                          <td style="font-size: 12px;">{{ bar.high | number:'1.2-2' }}</td>
                          <td style="font-size: 12px;">{{ bar.low | number:'1.2-2' }}</td>
                          <td style="font-size: 12px; font-weight: 500;"
                            [style.color]="bar.close >= bar.pre_close ? '#cf1322' : '#389e0d'">
                            {{ bar.close | number:'1.2-2' }}
                          </td>
                          <td style="font-size: 12px;">{{ bar.pre_close | number:'1.2-2' }}</td>
                          <td style="font-size: 12px;">{{ bar.volume | number:'1.0-0' }}</td>
                          <td style="font-size: 12px;">{{ bar.amount | number:'1.0-0' }}</td>
                          <td style="font-size: 12px;">{{ bar.pe | number:'1.2-2' }}</td>
                          <td style="font-size: 12px;">{{ bar.pb | number:'1.2-2' }}</td>
                          <td style="font-size: 12px;">{{ bar.total_cap | number:'1.0-0' }}</td>
                          <td style="font-size: 12px;">{{ bar.a_float_cap | number:'1.0-0' }}</td>
                        </tr>
                      }
                    </tbody>
                  </nz-table>
                } @else {
                  <nz-empty nzNotFoundContent="Click Load to fetch daily bars"></nz-empty>
                }
              } @else {
                <nz-empty nzNotFoundContent="Select an industry first"></nz-empty>
              }
            </nz-tab>
          </nz-tabset>
        </nz-card>
      </div>
    </div>
  `,
})
export class IndustryExplorerPageComponent implements OnInit {
  private api = inject(WorkbenchApiService);
  private msg = inject(NzMessageService);

  // Search
  searchMode: 'industry' | 'stock' = 'industry';
  industrySearchText = '';
  stockCode = '';
  loadingSearch = false;
  initialLoaded = false;

  // Suggestions
  industrySuggestions: string[] = [];
  recentIndustrySearches: string[] = [];
  recentStockSearches: string[] = [];
  popularKeywords = POPULAR_KEYWORDS;

  // Category hierarchy
  categories: IndustryCategory[] = [];
  categoryPath: IndustryCategory[] = [];
  selectedCategory: IndustryCategory | null = null;

  // Stock reverse lookup
  stockIndustries: IndustryConstituent[] = [];

  // Currently selected index
  selectedIndexCode = '';
  selectedIndexName = '';

  // Constituents
  constituents: IndustryConstituent[] = [];
  loadingConstituents = false;

  // Daily bars
  dailyBars: IndustryDailyBar[] = [];
  dailyStartDate = '2024-01-01';
  dailyEndDate = '2024-12-31';
  loadingDaily = false;

  private allCategoryNames: string[] = [];

  ngOnInit(): void {
    this.loadRecentSearches();
    this.loadTopLevelCategories();
  }

  private loadTopLevelCategories(): void {
    this.loadingSearch = true;
    this.api.getIndustryCategories({ level: 1, page_size: 500 }).subscribe({
      next: (resp) => {
        this.categories = resp.list || [];
        this.initialLoaded = true;
        this.loadingSearch = false;
        if (this.categories.length > 0) {
          this.allCategoryNames = this.categories.map(c => c.name);
          this.updateSuggestions();
        }
      },
      error: () => {
        this.initialLoaded = true;
        this.loadingSearch = false;
      },
    });
  }

  onSearchModeChange(): void {
    this.updateSuggestions();
  }

  private updateSuggestions(): void {
    if (this.searchMode === 'industry') {
      const recent = this.recentIndustrySearches;
      const popular = this.allCategoryNames.length > 0
        ? this.allCategoryNames.slice(0, 10)
        : POPULAR_KEYWORDS.slice(0, 10);
      this.industrySuggestions = [...new Set([...recent, ...popular])];
    }
  }

  quickSearch(keyword: string): void {
    this.industrySearchText = keyword;
    this.searchIndustries();
  }

  searchIndustries(): void {
    this.loadingSearch = true;
    const params: any = { page_size: 500 };
    if (this.industrySearchText.trim()) {
      params.name = this.industrySearchText.trim();
      this.addRecentSearch('industry', this.industrySearchText.trim());
    }
    this.api.getIndustryCategories(params).subscribe({
      next: (resp) => {
        this.categories = resp.list || [];
        this.categoryPath = [];
        this.loadingSearch = false;
        if (this.categories.length === 0 && this.industrySearchText.trim()) {
          this.msg.info('No industries found for "' + this.industrySearchText + '"');
        }
      },
      error: () => {
        this.msg.error('Failed to load industries');
        this.loadingSearch = false;
      },
    });
  }

  searchByStock(): void {
    if (!this.stockCode.trim()) {
      this.msg.warning('Please enter a stock code');
      return;
    }
    this.loadingSearch = true;
    this.addRecentSearch('stock', this.stockCode.trim());
    this.api.getIndustriesByStock(this.stockCode.trim()).subscribe({
      next: (resp) => {
        this.stockIndustries = resp.list || [];
        this.loadingSearch = false;
        if (this.stockIndustries.length === 0) {
          this.msg.info('No industries found for stock ' + this.stockCode);
        }
      },
      error: () => {
        this.msg.error('Failed to look up industries');
        this.loadingSearch = false;
      },
    });
  }

  drillDown(cat: IndustryCategory): void {
    this.loadingSearch = true;
    this.categoryPath.push(cat);
    this.api.getIndustryCategories({ parent_code: cat.code, page_size: 500 }).subscribe({
      next: (resp) => {
        this.categories = resp.list || [];
        this.loadingSearch = false;
      },
      error: () => {
        this.msg.error('Failed to load sub-categories');
        this.loadingSearch = false;
      },
    });
  }

  navigateToRoot(): void {
    this.categoryPath = [];
    this.industrySearchText = '';
    this.loadTopLevelCategories();
  }

  navigateTo(cat: IndustryCategory): void {
    const idx = this.categoryPath.findIndex(c => c.code === cat.code);
    if (idx >= 0) {
      this.categoryPath = this.categoryPath.slice(0, idx + 1);
      this.loadingSearch = true;
      this.api.getIndustryCategories({ parent_code: cat.code, page_size: 500 }).subscribe({
        next: (resp) => {
          this.categories = resp.list || [];
          this.loadingSearch = false;
        },
        error: () => {
          this.msg.error('Failed to load categories');
          this.loadingSearch = false;
        },
      });
    }
  }

  selectCategory(cat: IndustryCategory): void {
    this.selectedCategory = cat;
    const attrs = cat.attrs;
    const indexCode = attrs?.index_code || cat.code;
    this.selectedIndexCode = indexCode;
    this.selectedIndexName = cat.name;
    this.loadConstituents(indexCode);
  }

  selectConstituent(item: IndustryConstituent): void {
    this.selectedIndexCode = item.index_code;
    this.selectedIndexName = item.index_name;
    this.loadConstituents(item.index_code);
  }

  private loadConstituents(indexCode: string): void {
    this.loadingConstituents = true;
    this.constituents = [];
    this.dailyBars = [];
    this.api.getIndustryConstituents(indexCode).subscribe({
      next: (resp) => {
        this.constituents = resp.list || [];
        this.loadingConstituents = false;
      },
      error: () => {
        this.msg.error('Failed to load constituents');
        this.loadingConstituents = false;
      },
    });
  }

  loadIndustryDaily(): void {
    if (!this.selectedIndexCode) return;
    this.loadingDaily = true;
    this.api.getIndustryDaily(this.selectedIndexCode, this.dailyStartDate, this.dailyEndDate).subscribe({
      next: (resp) => {
        this.dailyBars = resp.bars || [];
        this.loadingDaily = false;
        if (this.dailyBars.length === 0) {
          this.msg.info('No daily bars found');
        }
      },
      error: () => {
        this.msg.error('Failed to load daily bars');
        this.loadingDaily = false;
      },
    });
  }

  // ── Recent searches (localStorage) ──

  private loadRecentSearches(): void {
    try {
      const raw = localStorage.getItem(RECENT_SEARCH_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        this.recentIndustrySearches = data.industry || [];
        this.recentStockSearches = data.stock || [];
      }
    } catch { /* ignore */ }
  }

  private addRecentSearch(type: 'industry' | 'stock', term: string): void {
    const list = type === 'industry' ? this.recentIndustrySearches : this.recentStockSearches;
    const idx = list.indexOf(term);
    if (idx >= 0) list.splice(idx, 1);
    list.unshift(term);
    if (list.length > MAX_RECENT) list.length = MAX_RECENT;
    this.saveRecentSearches();
    this.updateSuggestions();
  }

  private saveRecentSearches(): void {
    try {
      localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify({
        industry: this.recentIndustrySearches,
        stock: this.recentStockSearches,
      }));
    } catch { /* ignore */ }
  }
}
