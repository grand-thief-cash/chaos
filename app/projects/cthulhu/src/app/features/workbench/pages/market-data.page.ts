import { Component, computed, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzMessageService } from 'ng-zorro-antd/message';
import { ChartPanelComponent } from '../../../shared/ui/chart-panel';
import { WorkbenchApiService } from '../services/workbench-api.service';
import { WorkbenchStore } from '../state/workbench.store';
import {
  Bar,
  IndicatorInfo,
  IndicatorSeriesMeta,
} from '../models/workbench.model';

interface IndicatorInstance {
  id: number;
  name: string;
  params: Record<string, any>;
  color: string;
}

const COLOR_PALETTE = [
  '#1890ff', '#fa8c16', '#52c41a', '#eb2f96',
  '#722ed1', '#13c2c2', '#f5222d', '#faad14',
  '#2f54eb', '#fa541c', '#73d13d', '#f759ab',
  '#9254de', '#36cfc9', '#ff4d4f', '#ffd666',
];

@Component({
  selector: 'app-market-data',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzCardModule,
    NzFormModule,
    NzInputModule,
    NzButtonModule,
    NzSelectModule,
    NzSpinModule,
    NzTagModule,
    NzCollapseModule,
    NzSwitchModule,
    NzDividerModule,
    NzIconModule,
    ChartPanelComponent,
  ],
  template: `
    <div style="display: flex; flex-direction: column;">
      <!-- 搜索栏：可折叠 -->
      <nz-collapse style="flex-shrink: 0; border-bottom: 1px solid #f0f0f0; background: #fff;">
        <nz-collapse-panel
          [nzHeader]="collapseHeader"
          [nzActive]="searchExpanded"
          (nzActiveChange)="searchExpanded = $event"
        >
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <!-- Source -->
            @if (store.sourceSelectorVisible()) {
              <div>
                <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Source</label>
                <nz-select
                  [(ngModel)]="selectedSource"
                  (ngModelChange)="onSourceChange($event)"
                  nzSize="small"
                  style="width: 130px;"
                >
                  @for (s of store.sources(); track s) {
                    <nz-option [nzLabel]="sourceLabel(s)" [nzValue]="s"></nz-option>
                  }
                </nz-select>
              </div>
            }
            <!-- Asset Type -->
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Asset</label>
              <nz-select
                [(ngModel)]="selectedAssetType"
                (ngModelChange)="onAssetTypeChange($event)"
                nzSize="small"
                style="width: 100px;"
              >
                @for (a of store.assetTypes(); track a.value) {
                  <nz-option [nzLabel]="a.label" [nzValue]="a.value"></nz-option>
                }
              </nz-select>
            </div>
            <!-- Market -->
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Market</label>
              <nz-select
                [(ngModel)]="selectedMarket"
                nzSize="small"
                style="width: 100px;"
              >
                @for (m of store.markets(); track m.value) {
                  <nz-option [nzLabel]="m.label" [nzValue]="m.value"></nz-option>
                }
              </nz-select>
            </div>
            <!-- Period -->
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Period</label>
              <nz-select
                [(ngModel)]="selectedPeriod"
                nzSize="small"
                style="width: 100px;"
              >
                @for (p of store.periods(); track p.value) {
                  <nz-option [nzLabel]="p.label" [nzValue]="p.value"></nz-option>
                }
              </nz-select>
            </div>
            <!-- Adjust (联动) -->
            @if (currentAdjustOptions().length > 0) {
              <div>
                <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Adjust</label>
                <nz-select
                  [(ngModel)]="selectedAdjust"
                  nzSize="small"
                  style="width: 100px;"
                >
                  @for (a of currentAdjustOptions(); track a.value) {
                    <nz-option [nzLabel]="a.label" [nzValue]="a.value"></nz-option>
                  }
                </nz-select>
              </div>
            }
            <!-- Symbol -->
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Symbol</label>
              <input nz-input [(ngModel)]="symbol" placeholder="e.g. 000001" style="width: 140px;" />
            </div>
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Start</label>
              <input nz-input type="date" [(ngModel)]="startDate" style="width: 150px;" />
            </div>
            <div>
              <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">End</label>
              <input nz-input type="date" [(ngModel)]="endDate" style="width: 150px;" />
            </div>
            <button nz-button nzType="primary" (click)="loadChart()" [nzLoading]="loading" style="margin-top: 16px;">
              Load
            </button>
          </div>

          <!-- 指标添加区域 -->
          @if (availableIndicators.length > 0) {
            <div style="margin-top: 10px; display: flex; align-items: flex-end; gap: 8px; flex-wrap: wrap;">
              <div>
                <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">Indicator</label>
                <nz-select [(ngModel)]="selectedIndicatorType" (ngModelChange)="onIndicatorTypeSelected()"
                  nzPlaceHolder="Select..." nzSize="small" style="width: 130px;">
                  @for (ind of availableIndicators; track ind.name) {
                    <nz-option [nzLabel]="ind.display_name" [nzValue]="ind.name"></nz-option>
                  }
                </nz-select>
              </div>

              @for (pk of selectedParamKeys; track pk) {
                <div>
                  <label style="display:block; margin-bottom:2px; font-size:12px; color:#666;">{{ pk }}</label>
                  <input nz-input type="number" [(ngModel)]="indicatorParams[pk]"
                    style="width: 80px; font-size: 12px;" />
                </div>
              }

              <button nz-button nzType="primary" nzSize="small" (click)="addIndicator()"
                [disabled]="!selectedIndicatorType" style="margin-bottom: 1px;">
                + Add
              </button>
            </div>

            @if (addedIndicators.length > 0) {
              <div style="margin-top: 8px; display: flex; gap: 4px; flex-wrap: wrap;">
                @for (inst of addedIndicators; track inst.id) {
                  <nz-tag nzMode="closeable" (nzOnClose)="removeIndicator(inst.id)" [nzColor]="inst.color">
                    {{ instanceLabel(inst) }}
                  </nz-tag>
                }
              </div>
            }
          }
        </nz-collapse-panel>
      </nz-collapse>
      <ng-template #collapseHeader>
        <span style="font-weight: 500;">Search</span>
        @if (selectedSource !== 'relx') {
          <span style="margin-left: 8px; color: #f5222d; font-size: 12px; font-weight: normal;">
            &bull; {{ sourceLabel(selectedSource) }}
          </span>
        }
        @if (bars.length > 0) {
          <span style="margin-left: 12px; font-size: 12px; color: #999; font-weight: normal;">
            {{ bars.length }} bars · {{ symbol }}
          </span>
        }
      </ng-template>

      <!-- 图表区：填满剩余空间 -->
      @if (bars.length > 0) {
        <div style="position: relative;">
          <app-chart-panel
            [bars]="bars"
            [indicators]="indicatorSeries"
            [indicatorMeta]="indicatorMeta"
            [lockYAxis]="lockYAxis"
            [showVolume]="showVolume"
            [mainHeight]="mainHeight"
            [volumeHeight]="volumeHeight"
            [subChartHeight]="subChartHeight"
          ></app-chart-panel>

          <!-- 浮动配置按钮 -->
          <div
            style="position: absolute; top: 32px; right: 16px; z-index: 10;"
          >
            <button nz-button nzShape="circle" nzSize="small"
              (click)="configPanelOpen = !configPanelOpen"
              style="box-shadow: 0 2px 8px rgba(0,0,0,0.15);"
            >
              <span nz-icon nzType="setting" nzTheme="outline"></span>
            </button>

            @if (configPanelOpen) {
              <div style="
                position: absolute; top: 40px; right: 0;
                background: #fff; border-radius: 6px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                padding: 12px 16px; width: 260px;
              ">
                <div style="font-weight: 500; margin-bottom: 10px; font-size: 13px;">Chart Settings</div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                  <span style="font-size: 13px;">Lock Y-Axis</span>
                  <nz-switch [(ngModel)]="lockYAxis" nzSize="small"></nz-switch>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                  <span style="font-size: 13px;">Show Volume</span>
                  <nz-switch [(ngModel)]="showVolume" nzSize="small"></nz-switch>
                </div>
                <nz-divider style="margin: 8px 0;"></nz-divider>
                <div style="font-weight: 500; margin-bottom: 8px; font-size: 12px; color: #666;">Height</div>
                <div style="margin-bottom: 8px;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="font-size: 12px;">Main</span>
                    <span style="font-size: 11px; color: #999;">{{mainHeight}}px</span>
                  </div>
                  <input type="range" [(ngModel)]="mainHeight" min="200" max="800" step="10"
                    style="width: 100%; accent-color: #1890ff;" />
                </div>
                <div style="margin-bottom: 8px;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="font-size: 12px;">Volume</span>
                    <span style="font-size: 11px; color: #999;">{{volumeHeight}}px</span>
                  </div>
                  <input type="range" [(ngModel)]="volumeHeight" min="40" max="300" step="10"
                    style="width: 100%; accent-color: #1890ff;" />
                </div>
                <div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="font-size: 12px;">Sub-chart</span>
                    <span style="font-size: 11px; color: #999;">{{subChartHeight}}px</span>
                  </div>
                  <input type="range" [(ngModel)]="subChartHeight" min="60" max="400" step="10"
                    style="width: 100%; accent-color: #1890ff;" />
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
})
export class MarketDataPageComponent implements OnInit {
  private api = inject(WorkbenchApiService);
  private msg = inject(NzMessageService);
  store = inject(WorkbenchStore);

  symbol = '000001';
  startDate = '2024-01-01';
  endDate = '2024-12-31';
  loading = false;
  searchExpanded = true;
  configPanelOpen = false;
  lockYAxis = false;
  showVolume = true;
  mainHeight = 450;
  volumeHeight = 120;
  subChartHeight = 150;

  selectedSource = 'relx';
  selectedAssetType = '';
  selectedMarket = '';
  selectedPeriod = '';
  selectedAdjust = '';

  bars: Bar[] = [];
  availableIndicators: IndicatorInfo[] = [];

  addedIndicators: IndicatorInstance[] = [];
  private nextId = 0;
  selectedIndicatorType: string | null = null;
  indicatorParams: Record<string, any> = {};
  selectedParamKeys: string[] = [];

  indicatorSeries: Record<string, (number | null)[]> = {};
  indicatorMeta: Record<string, IndicatorSeriesMeta> = {};

  currentAdjustOptions = computed(() =>
    this.store.getAdjustOptionsForAsset(this.selectedAssetType),
  );

  ngOnInit(): void {
    this.store.loadSources(() => {
      this.selectedSource = this.store.selectedSource();
    });
    this.store.loadDataOptions(() => {
      this.initializeDimensionSelections();
    });

    this.api.getAvailableIndicators().subscribe({
      next: (resp) => (this.availableIndicators = resp.indicators),
      error: () => this.msg.error('Failed to load indicators'),
    });
  }

  private initializeDimensionSelections(): void {
    const assetTypes = this.store.assetTypes();
    const markets = this.store.markets();
    const periods = this.store.periods();

    if (!assetTypes.some((item) => item.value === this.selectedAssetType)) {
      this.selectedAssetType = assetTypes[0]?.value ?? '';
    }
    if (!markets.some((item) => item.value === this.selectedMarket)) {
      this.selectedMarket = markets[0]?.value ?? '';
    }
    if (!periods.some((item) => item.value === this.selectedPeriod)) {
      this.selectedPeriod = periods[0]?.value ?? '';
    }

    const adjustOptions = this.store.getAdjustOptionsForAsset(this.selectedAssetType);
    if (!adjustOptions.some((item) => item.value === this.selectedAdjust)) {
      this.selectedAdjust = adjustOptions[0]?.value ?? '';
    }
  }

  sourceLabel(name: string): string {
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  onSourceChange(source: string): void {
    this.store.selectSource(source);
    this.clearData();
  }

  onAssetTypeChange(assetType: string): void {
    // 切换 asset_type 时重置 adjust 到该类型的第一个选项
    const options = this.store.getAdjustOptionsForAsset(assetType);
    if (options.length > 0) {
      this.selectedAdjust = options[0].value;
    } else {
      this.selectedAdjust = '';
    }
    this.clearData();
  }

  private clearData(): void {
    if (this.bars.length > 0) {
      this.bars = [];
      this.indicatorSeries = {};
      this.indicatorMeta = {};
      this.msg.info('Data cleared — click Load to fetch with new parameters');
    }
  }

  onIndicatorTypeSelected(): void {
    const info = this.availableIndicators.find((i) => i.name === this.selectedIndicatorType);
    if (info) {
      this.indicatorParams = { ...info.default_params };
      this.selectedParamKeys = Object.keys(info.default_params);
    }
  }

  addIndicator(): void {
    if (!this.selectedIndicatorType) return;
    // ensure numeric params
    const params: Record<string, any> = {};
    for (const k of this.selectedParamKeys) {
      const v = this.indicatorParams[k];
      params[k] = typeof v === 'number' ? v : Number(v);
    }

    this.addedIndicators.push({
      id: ++this.nextId,
      name: this.selectedIndicatorType,
      params,
      color: COLOR_PALETTE[this.nextId % COLOR_PALETTE.length],
    });

    if (this.bars.length > 0) {
      this.fetchIndicators();
    }
  }

  removeIndicator(id: number): void {
    this.addedIndicators = this.addedIndicators.filter((i) => i.id !== id);
    if (this.bars.length > 0 && this.addedIndicators.length > 0) {
      this.fetchIndicators();
    } else {
      this.indicatorSeries = {};
      this.indicatorMeta = {};
    }
  }

  instanceLabel(inst: IndicatorInstance): string {
    const info = this.availableIndicators.find((i) => i.name === inst.name);
    const values = Object.values(inst.params).join(',');
    return `${info?.display_name ?? inst.name}(${values})`;
  }

  loadChart(): void {
    if (!this.symbol || !this.startDate || !this.endDate) {
      this.msg.warning('Please fill in all fields');
      return;
    }
    if (!this.selectedAssetType || !this.selectedMarket || !this.selectedPeriod) {
      this.msg.warning('Data options are not ready yet');
      return;
    }

    const source = this.store.sourceSelectorVisible() ? this.selectedSource : undefined;
    this.loading = true;
    this.api.getMarketData(
      this.symbol, this.startDate, this.endDate,
      this.selectedPeriod, this.selectedAdjust,
      this.selectedAssetType, this.selectedMarket,
      source,
    ).subscribe({
      next: (resp) => {
        this.bars = resp.bars;
        this.loading = false;
        if (resp.bars.length === 0) {
          this.msg.warning('No data found for the selected parameters');
          return;
        }
        if (this.addedIndicators.length > 0) {
          this.fetchIndicators();
        }
        this.msg.success(`Loaded ${resp.bars.length} bars`);
      },
      error: (err) => {
        this.msg.error(err.error?.detail ?? 'Failed to load market data');
        this.loading = false;
      },
    });
  }

  private fetchIndicators(): void {
    if (!this.bars.length || this.addedIndicators.length === 0) return;

    const indicators = this.addedIndicators.map((inst) => ({
      name: inst.name,
      params: inst.params,
    }));

    const source = this.store.sourceSelectorVisible() ? this.selectedSource : undefined;

    this.api
      .calculateIndicators({
        symbol: this.symbol,
        start_date: this.startDate,
        end_date: this.endDate,
        period: this.selectedPeriod,
        adjust: this.selectedAdjust,
        asset_type: this.selectedAssetType,
        market: this.selectedMarket,
        indicators,
        source,
      })
      .subscribe({
        next: (resp) => {
          this.indicatorSeries = resp.indicators;
          this.indicatorMeta = resp.indicator_meta;
          this.applyInstanceColors();
        },
        error: (err) => this.msg.error(err.error?.detail ?? 'Failed to calculate indicators'),
      });
  }

  /** 将各实例分配的颜色覆盖到 overlay 系列的 meta 中 */
  private applyInstanceColors(): void {
    for (const [key, meta] of Object.entries(this.indicatorMeta)) {
      if (!meta.overlay) continue;
      const inst = this.findInstanceForSeriesKey(key);
      if (inst) {
        meta.color = inst.color;
      }
    }
  }

  /** 根据后端生成的 series key（如 sma_5, macd_12_26_9）匹配到对应的 IndicatorInstance */
  private findInstanceForSeriesKey(key: string): IndicatorInstance | undefined {
    const candidates = this.addedIndicators.filter(
      (inst) => key.startsWith(inst.name + '_') || key === inst.name,
    );
    if (candidates.length === 0) return undefined;
    if (candidates.length === 1) return candidates[0];

    // 多个同类型实例时，按参数值匹配
    for (const inst of candidates) {
      const paramValues = Object.values(inst.params).map(String);
      if (paramValues.every((v) => key.includes(v))) {
        return inst;
      }
    }
    return candidates[0];
  }
}
