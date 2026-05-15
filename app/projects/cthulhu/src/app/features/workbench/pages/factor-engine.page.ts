import {Component, effect, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzDatePickerModule} from 'ng-zorro-antd/date-picker';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {NzTabsModule} from 'ng-zorro-antd/tabs';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzSpinModule} from 'ng-zorro-antd/spin';
import {NzDividerModule} from 'ng-zorro-antd/divider';
import {NzEmptyModule} from 'ng-zorro-antd/empty';
import {NzToolTipModule} from 'ng-zorro-antd/tooltip';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzDescriptionsModule} from 'ng-zorro-antd/descriptions';
import {NzInputNumberModule} from 'ng-zorro-antd/input-number';
import {NzMessageService} from 'ng-zorro-antd/message';
import {NzGridModule} from 'ng-zorro-antd/grid';

import {FactorService} from '../services/factor.service';
import {FactorAvailabilityItem, FactorAvailabilityResponse, FactorMeta, FactorRankItem, FactorSnapshot} from '../models/factor.models';
import {WorkbenchStore} from '../state/workbench.store';
import {
  FACTOR_ENGINE_CAPABILITY_SOURCE_MESSAGES,
  FACTOR_ENGINE_COPY,
  FACTOR_ENGINE_HELP_TEXTS,
  FACTOR_ENGINE_STATUS_LEGENDS,
  FactorEngineHelpKey,
  FactorEngineLegendItem,
} from '../ui/factor-engine.copy';

@Component({
  selector: 'app-factor-engine',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    NzCardModule, NzTableModule, NzButtonModule, NzInputModule,
    NzDatePickerModule, NzSelectModule, NzTabsModule, NzTagModule,
    NzSpinModule, NzDividerModule, NzEmptyModule, NzToolTipModule,
    NzIconModule, NzDescriptionsModule, NzInputNumberModule, NzGridModule
  ],
  template: `
    <nz-tabset [(nzSelectedIndex)]="selectedTabIndex">
      <!-- ==================== Tab 1: Factor Meta ==================== -->
      <nz-tab nzTitle="Factor Registry">
        <nz-card [nzBordered]="false">
          <div class="action-bar">
            <button nz-button nzType="default" (click)="loadMeta()" [nzLoading]="loadingMeta">
              <span nz-icon nzType="reload"></span> Refresh
            </button>
            <input nz-input placeholder="Search factor in registry" [(ngModel)]="registrySearch" style="width: 240px; margin-left: 12px;" />
          </div>
          <nz-table #metaTable [nzData]="filteredFactorMetas" [nzLoading]="loadingMeta"
                    nzSize="small" [nzPageSize]="50"
                    [nzShowSizeChanger]="true">
            <thead>
              <tr>
                <th nzWidth="140px">Name</th>
                <th nzWidth="120px">中文名</th>
                <th nzWidth="100px">Category</th>
                <th nzWidth="220px">Management</th>
                <th nzWidth="220px">Availability</th>
                <th nzWidth="260px">PhoenixA Lineage</th>
                <th>Formula</th>
                <th nzWidth="60px">Unit</th>
                <th nzWidth="120px">
                  {{ copy.registryHigherIsBetterLabel }}
                  <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('higher_is_better')"></span>
                </th>
                <th nzWidth="130px">
                  {{ copy.registryMarketDataLabel }}
                  <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('market_data')"></span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let f of metaTable.data" [style.background]="registrySearch && f.name === registrySearch ? '#fffbe6' : null">
                <td>
                  <strong>{{ f.name }}</strong>
                  <div *ngIf="f.description" class="subtle-text">{{ f.description }}</div>
                  <div *ngIf="f.management_tags?.length" style="margin-top: 4px;">
                    <nz-tag *ngFor="let tag of f.management_tags" nzColor="default">{{ tag }}</nz-tag>
                  </div>
                </td>
                <td>{{ f.cn_name }}</td>
                <td>
                  <nz-tag [nzColor]="categoryColor(f.category)">{{ f.category }}</nz-tag>
                </td>
                <td>
                  <nz-tag [nzColor]="financialPolicyColor(f)">{{ financialPolicyLabel(f) }}</nz-tag>
                  <div *ngIf="f.financial_policy?.reason" class="subtle-text">{{ f.financial_policy?.reason }}</div>
                  <div *ngIf="f.catalog_seeded" class="subtle-text">catalog {{ f.catalog_version }} · {{ f.management_phase }}</div>
                </td>
                <td>
                  <nz-tag [nzColor]="availabilityColor(f.availability?.expected)">{{ f.availability?.expected || 'unknown' }}</nz-tag>
                  <div class="subtle-text">{{ availabilityPreview(f) }}</div>
                </td>
                <td>
                  <div><code>{{ primaryPhoenixPath(f) }}</code></div>
                  <div class="subtle-text">{{ sourceFieldPreview(f) }}</div>
                </td>
                <td style="font-family: monospace; font-size: 12px;">{{ f.formula }}</td>
                <td>{{ f.unit }}</td>
                <td>
                  <span *ngIf="f.higher_is_better" style="color:#52c41a;">✓</span>
                  <span *ngIf="!f.higher_is_better" style="color:#ff4d4f;">✗</span>
                </td>
                <td>
                  <nz-tag *ngIf="f.requires_market_data" nzColor="blue">Yes</nz-tag>
                  <nz-tag *ngIf="!f.requires_market_data">No</nz-tag>
                </td>
              </tr>
            </tbody>
          </nz-table>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 2: Compute ==================== -->
      <nz-tab nzTitle="Compute">
        <nz-card nzTitle="Full Computation" [nzBordered]="false" style="margin-bottom: 16px;">
          <div class="subtle-text" style="margin-bottom: 12px; display:flex; align-items:center; gap: 6px;">
            Running against source <strong>{{ sourceLabel(selectedSource) }}</strong>
            <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
          </div>
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="computeDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <label class="field-label">Market</label>
              <nz-select [(ngModel)]="computeMarket" style="width: 100px;">
                <nz-option nzValue="zh_a" nzLabel="A股"></nz-option>
              </nz-select>
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="computeFull()" [nzLoading]="computing">
                <span nz-icon nzType="thunderbolt"></span> Run Full
              </button>
            </div>
          </div>
          <div *ngIf="computeResult" class="result-msg">
            ✅ Computed {{ computeResult.symbols_count }} symbols for {{ computeResult.as_of_date }}
          </div>
        </nz-card>

        <nz-card nzTitle="Incremental Computation" [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Symbols (comma-separated)</label>
              <input nz-input placeholder="e.g. 000001,000002" [(ngModel)]="incrSymbols" style="width: 260px;" />
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="incrDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="computeIncremental()" [nzLoading]="computingIncr"
                      [disabled]="!incrSymbols">
                <span nz-icon nzType="thunderbolt"></span> Run Incremental
              </button>
            </div>
          </div>
          <div *ngIf="incrResult" class="result-msg">
            ✅ Computed {{ incrResult.symbols_count }} symbols
          </div>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 3: Snapshot ==================== -->
      <nz-tab nzTitle="Snapshot">
        <nz-card [nzBordered]="false">
          <div class="subtle-text" style="margin-bottom: 12px; display:flex; align-items:center; gap: 6px;">
            Querying source <strong>{{ sourceLabel(selectedSource) }}</strong>
            <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
          </div>
          <div nz-row [nzGutter]="16" nzAlign="middle" style="margin-bottom: 16px;">
            <div nz-col>
              <label class="field-label">Symbol</label>
              <input nz-input placeholder="e.g. 000001" [(ngModel)]="snapSymbol" style="width: 120px;" />
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="snapDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="loadSnapshot()" [nzLoading]="loadingSnap"
                      [disabled]="!snapSymbol || !snapDate">
                <span nz-icon nzType="search"></span> Query
              </button>
            </div>
          </div>

          <div *ngIf="snapshot">
            <div *ngIf="snapshotFocusFactor" class="subtle-text" style="margin-bottom: 8px;">
              Focus factor: <strong>{{ snapshotFocusFactor }}</strong>
            </div>
            <nz-divider nzText="Snapshot Meta" nzOrientation="left"></nz-divider>
            <nz-descriptions nzSize="small" nzBordered [nzColumn]="2">
              <nz-descriptions-item nzTitle="Reporting Period">{{ snapshot.meta.reporting_period || '-' }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Latest Ann Date">{{ snapshot.meta.latest_ann_date || '-' }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Industry">{{ snapshot.meta.industry_code || '-' }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Company Kind">{{ snapshot.meta.company_kind || '-' }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Freshness">
                <nz-tag [nzColor]="freshnessColor(snapshot.meta.freshness?.freshness_label)">{{ snapshot.meta.freshness?.freshness_label || 'unknown' }}</nz-tag>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Staleness Days">{{ snapshot.meta.freshness?.staleness_days ?? '-' }}</nz-descriptions-item>
            </nz-descriptions>

            <nz-divider nzText="Raw Factors" nzOrientation="left"></nz-divider>
            <nz-table #rawTable [nzData]="snapshotRawEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th nzWidth="200px">Factor</th><th>Value</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of rawTable.data" [attr.id]="snapshotRowId('raw', e[0])" [style.background]="snapshotFocusFactor === e[0] ? '#fffbe6' : null">
                  <td style="font-weight: 500;">{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] | number:'1.4-4' }}</td>
                </tr>
              </tbody>
            </nz-table>

            <nz-divider nzText="Normalized Factors" nzOrientation="left"></nz-divider>
            <nz-table #normTable [nzData]="snapshotNormEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th nzWidth="200px">Factor</th><th>Value</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of normTable.data" [attr.id]="snapshotRowId('norm', e[0])" [style.background]="snapshotFocusFactor === e[0] ? '#fffbe6' : null">
                  <td style="font-weight: 500;">{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] | number:'1.4-4' }}</td>
                </tr>
              </tbody>
            </nz-table>

            <nz-divider nzText="Missing Reasons" nzOrientation="left"></nz-divider>
            <nz-table #missingTable [nzData]="snapshotMissingEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th nzWidth="200px">Factor</th><th>Reason</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of missingTable.data" [attr.id]="snapshotRowId('missing', e[0])" [style.background]="snapshotFocusFactor === e[0] ? '#fffbe6' : null">
                  <td style="font-weight: 500;">{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] }}</td>
                </tr>
              </tbody>
            </nz-table>
          </div>
          <nz-empty *ngIf="!snapshot && !loadingSnap" nzNotFoundContent="Enter symbol and date to query snapshot"></nz-empty>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 4: Ranking ==================== -->
      <nz-tab nzTitle="Ranking">
        <nz-card [nzBordered]="false">
          <div class="subtle-text" style="margin-bottom: 12px; display:flex; align-items:center; gap: 6px;">
            Ranking source <strong>{{ sourceLabel(selectedSource) }}</strong>
            <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
          </div>
          <div nz-row [nzGutter]="16" nzAlign="middle" style="margin-bottom: 16px;">
            <div nz-col>
              <label class="field-label">Factor</label>
              <nz-select [(ngModel)]="rankFactor" style="width: 200px;" nzShowSearch nzPlaceHolder="Select factor">
                <nz-option *ngFor="let f of factorMetas" [nzValue]="f.name" [nzLabel]="f.name + ' (' + f.cn_name + ')'"></nz-option>
              </nz-select>
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="rankDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <label class="field-label">Top N</label>
              <nz-input-number [(ngModel)]="rankTopN" [nzMin]="1" [nzMax]="500" [nzStep]="10" style="width: 80px;"></nz-input-number>
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="loadRanking()" [nzLoading]="loadingRank"
                      [disabled]="!rankFactor || !rankDate">
                <span nz-icon nzType="ordered-list"></span> Query
              </button>
            </div>
          </div>

          <nz-table #rankTable [nzData]="rankItems" [nzLoading]="loadingRank" nzSize="small" [nzPageSize]="50">
            <thead><tr><th nzWidth="60px">#</th><th nzWidth="120px">Symbol</th><th>{{ rankFactor || 'Value' }}</th></tr></thead>
            <tbody>
              <tr *ngFor="let item of rankTable.data; let i = index">
                <td>{{ i + 1 }}</td>
                <td><strong>{{ item.symbol }}</strong></td>
                <td style="font-family: monospace;">{{ getRankValue(item) | number:'1.4-4' }}</td>
              </tr>
            </tbody>
          </nz-table>
          <nz-empty *ngIf="rankItems.length === 0 && !loadingRank" nzNotFoundContent="Select factor and date to view ranking"></nz-empty>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 5: Availability ==================== -->
      <nz-tab nzTitle="Availability">
        <nz-card [nzBordered]="false">
          <div class="action-bar" style="display:flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <button nz-button nzType="default" (click)="loadAvailability(true)" [nzLoading]="loadingAvailability">
              <span nz-icon nzType="reload"></span> Refresh
            </button>
            <div *ngIf="workbenchStore.sourceSelectorVisible()" style="display:flex; align-items:center; gap: 6px;">
              <span class="subtle-text" style="margin-top: 0;">Source</span>
              <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
              <nz-select [(ngModel)]="selectedSource" (ngModelChange)="onSourceChange($event)" style="width: 140px;">
                <nz-option *ngFor="let source of workbenchStore.sources()" [nzValue]="source" [nzLabel]="sourceLabel(source)"></nz-option>
              </nz-select>
            </div>
            <input nz-input placeholder="Search factor / field / source / note" [(ngModel)]="availabilitySearch" style="width: 260px;" />
            <nz-select [(ngModel)]="availabilityCategoryFilter" style="width: 180px;" nzPlaceHolder="Category filter">
              <nz-option nzValue="all" nzLabel="All Categories"></nz-option>
              <nz-option *ngFor="let category of availabilityCategoryOptions" [nzValue]="category" [nzLabel]="category"></nz-option>
            </nz-select>
            <nz-select [(ngModel)]="availabilityStatusFilter" style="width: 180px;" nzPlaceHolder="Status filter">
              <nz-option nzValue="all" nzLabel="All Statuses"></nz-option>
              <nz-option nzValue="available" nzLabel="Available"></nz-option>
              <nz-option nzValue="partial" nzLabel="Partial"></nz-option>
              <nz-option nzValue="missing" nzLabel="Missing"></nz-option>
              <nz-option nzValue="unknown" nzLabel="Unknown"></nz-option>
            </nz-select>
            <nz-select [(ngModel)]="availabilityMissingSourceFilter" style="width: 220px;" nzPlaceHolder="Missing source filter">
              <nz-option nzValue="all" nzLabel="All Missing Sources"></nz-option>
              <nz-option nzValue="none" nzLabel="No Missing Sources"></nz-option>
              <nz-option *ngFor="let source of availabilityMissingSourceOptions" [nzValue]="source" [nzLabel]="source"></nz-option>
            </nz-select>
            <nz-select [(ngModel)]="availabilitySortField" style="width: 200px;" nzPlaceHolder="Sort by">
              <nz-option nzValue="availability_status" nzLabel="Sort: Status"></nz-option>
              <nz-option nzValue="required_field_count" nzLabel="Sort: Required Fields"></nz-option>
              <nz-option nzValue="category" nzLabel="Sort: Category"></nz-option>
              <nz-option nzValue="name" nzLabel="Sort: Name"></nz-option>
            </nz-select>
            <nz-select [(ngModel)]="availabilitySortDirection" style="width: 140px;" nzPlaceHolder="Direction">
              <nz-option nzValue="asc" nzLabel="Ascending"></nz-option>
              <nz-option nzValue="desc" nzLabel="Descending"></nz-option>
            </nz-select>
            <button nz-button nzType="default" (click)="expandAllAvailabilityDetails()">Expand All</button>
            <button nz-button nzType="default" (click)="collapseAllAvailabilityDetails()">Collapse All</button>
            <span class="subtle-text" style="display:flex; align-items:center; gap: 4px;">
              Capability source:
              <nz-tag [nzColor]="capabilitySourceColor(availabilityResponse?.capability_source)">{{ availabilityResponse?.capability_source || '-' }}</nz-tag>
              <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('capability_source')"></span>
            </span>
            <span class="subtle-text" style="display:flex; align-items:center; gap: 4px;">
              Selected source:
              <nz-tag nzColor="blue">{{ sourceLabel(availabilityResponse?.selected_source || selectedSource) }}</nz-tag>
              <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
            </span>
          </div>
          <div class="subtle-text" style="margin-bottom: 8px; display:flex; align-items:center; gap: 6px;">
            {{ copy.availabilityGuideLabel }}
            <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('availability_guide')"></span>
            <span>{{ copy.availabilityGuideSummary }}</span>
          </div>
          <div class="subtle-text" style="margin-bottom: 8px; display:flex; align-items:center; gap: 6px; flex-wrap: wrap;">
            <span>{{ copy.runtimeScopeSummary }}</span>
            <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('selected_source')"></span>
          </div>
          <div class="legend-row" style="margin-bottom: 8px;">
            <span class="subtle-text" style="margin-top: 0;">Live</span>
            <ng-container *ngFor="let legend of liveStatusLegend">
              <nz-tag [nzColor]="legend.color" nz-tooltip [nzTooltipTitle]="legend.description">{{ legend.label }}</nz-tag>
            </ng-container>
            <span class="subtle-text" style="margin-top: 0;">Expected</span>
            <ng-container *ngFor="let legend of expectedStatusLegend">
              <nz-tag [nzColor]="legend.color" nz-tooltip [nzTooltipTitle]="legend.description">{{ legend.label }}</nz-tag>
            </ng-container>
            <span class="subtle-text" style="margin-top: 0;">Source Readiness</span>
            <ng-container *ngFor="let legend of sourceReadinessLegend">
              <nz-tag [nzColor]="legend.color" nz-tooltip [nzTooltipTitle]="legend.description">{{ legend.label }}</nz-tag>
            </ng-container>
          </div>
          <div *ngIf="availabilityLinkedSourceFilter" class="subtle-text" style="margin-bottom: 8px;">
            Linked source filter: <strong>{{ availabilityLinkedSourceFilter }}</strong>
            <button nz-button nzType="link" (click)="clearLinkedSourceFilter()">Clear</button>
          </div>
          <div *ngIf="availabilityResponse?.capability_source" class="subtle-text" [style.color]="availabilityResponse?.capability_source === 'phoenixA_catalog' ? '#8c8c8c' : '#d48806'" style="margin-bottom: 8px;">
            {{ capabilitySourceMessage(availabilityResponse?.capability_source) }}
          </div>
          <div *ngIf="availabilityResponse?.capability_error" class="subtle-text" style="margin-bottom: 8px; color: #cf1322;">
            Capability error: {{ availabilityResponse?.capability_error }}
            <span *ngIf="availabilityResponse?.capability_http_status">(HTTP {{ availabilityResponse?.capability_http_status }})</span>
          </div>

          <div *ngIf="availabilityResponse as availability">
            <nz-descriptions nzSize="small" nzBordered [nzColumn]="4" style="margin-bottom: 16px;">
              <nz-descriptions-item nzTitle="Available">{{ availability.summary.available || 0 }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Partial">{{ availability.summary.partial || 0 }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Missing">{{ availability.summary.missing || 0 }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="Unknown">{{ availability.summary.unknown || 0 }}</nz-descriptions-item>
            </nz-descriptions>

            <nz-divider nzText="Source Readiness" nzOrientation="left"></nz-divider>
            <nz-table #sourceTable [nzData]="availabilitySourceEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead>
                <tr>
                  <th nzWidth="160px">Source</th>
                  <th nzWidth="120px">Status <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('source_readiness')"></span></th>
                  <th nzWidth="220px">Providers <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('providers')"></span></th>
                  <th nzWidth="220px">Coverage <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('coverage')"></span></th>
                  <th>Known Fields <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('known_fields')"></span></th>
                  <th nzWidth="180px">Link <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('linked_filter')"></span></th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let entry of sourceTable.data">
                  <td><strong>{{ entry[0] }}</strong></td>
                  <td><nz-tag [nzColor]="sourceReadinessColor(entry[1])">{{ sourceReadinessLabel(entry[1]) }}</nz-tag></td>
                  <td class="subtle-text">{{ providerSummary(entry[1]?.sources) }}</td>
                  <td class="subtle-text">
                    <div>Rows: {{ formatRowCount(entry[1]?.row_count) }}</div>
                    <div>Range: {{ timeRangeLabel(entry[1]?.time_range) }}</div>
                    <div>Types: {{ dataTypeSummary(entry[1]?.data_types) }}</div>
                  </td>
                  <td class="subtle-text">{{ knownFieldsSummary(entry[1]?.fields_known) }}</td>
                  <td>
                    <button nz-button nzType="link" (click)="toggleLinkedSourceFilter(entry[0])">{{ availabilityLinkedSourceFilter === entry[0] ? copy.linkedFilterActiveLabel : copy.linkedFilterIdleLabel }}</button>
                  </td>
                </tr>
              </tbody>
            </nz-table>

            <nz-divider nzText="Factor Availability" nzOrientation="left"></nz-divider>
            <nz-table #availabilityTable [nzData]="filteredAvailabilityItems" [nzLoading]="loadingAvailability" nzSize="small" [nzPageSize]="50">
              <thead>
                <tr>
                  <th nzWidth="160px">Actions</th>
                  <th nzWidth="140px">Factor</th>
                  <th nzWidth="100px">Live <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('live_status')"></span></th>
                  <th nzWidth="100px">Expected <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('expected_status')"></span></th>
                  <th nzWidth="180px">Required Sources <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('required_sources')"></span></th>
                  <th nzWidth="180px">Missing Sources <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('missing_sources')"></span></th>
                  <th nzWidth="240px">Required Fields <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('required_fields')"></span></th>
                  <th>Provenance <span nz-icon nzType="question-circle" class="help-icon" nz-tooltip [nzTooltipTitle]="helpText('provenance')"></span></th>
                </tr>
              </thead>
              <tbody>
                <ng-container *ngFor="let item of availabilityTable.data">
                <tr [style.background]="expandedAvailabilityRows[item.name] ? '#fafafa' : null">
                  <td>
                    <button nz-button nzType="link" (click)="toggleAvailabilityDetails(item.name)">{{ expandedAvailabilityRows[item.name] ? 'Hide' : 'Details' }}</button>
                    <button nz-button nzType="link" (click)="jumpToRegistry(item)">Registry</button>
                    <button nz-button nzType="link" (click)="jumpToRanking(item)">Ranking</button>
                    <button nz-button nzType="link" (click)="jumpToSnapshot(item)">Snapshot</button>
                  </td>
                  <td>
                    <strong>{{ item.name }}</strong>
                    <div class="subtle-text">{{ item.cn_name }}</div>
                  </td>
                  <td><nz-tag [nzColor]="availabilityRuntimeColor(item.availability_status)">{{ item.availability_status }}</nz-tag></td>
                  <td><nz-tag [nzColor]="availabilityColor(item.availability_expected)">{{ item.availability_expected }}</nz-tag></td>
                  <td>
                    <nz-tag *ngFor="let source of item.required_data_sources" nzColor="blue">{{ source }}</nz-tag>
                  </td>
                  <td>
                    <nz-tag *ngFor="let source of item.missing_sources" nzColor="red">{{ source }}</nz-tag>
                    <span *ngIf="!item.missing_sources.length" class="subtle-text">-</span>
                  </td>
                  <td>
                    <div class="subtle-text"><strong>{{ item.required_field_count }}</strong> field(s)</div>
                     <div *ngIf="item.missing_fields?.length" class="subtle-text" style="color:#cf1322;">{{ copy.fieldMissingPrefix }}: {{ previewList(item.missing_fields, 2) }}</div>
                     <div *ngIf="item.unknown_fields?.length" class="subtle-text" style="color:#d48806;">{{ copy.fieldUnknownPrefix }}: {{ previewList(item.unknown_fields, 2) }}</div>
                     <div *ngFor="let field of item.required_fields.slice(0, 4)" class="subtle-text" style="word-break: break-all;">{{ field }}</div>
                     <div *ngIf="item.required_fields.length > 4" class="subtle-text">+{{ item.required_fields.length - 4 }} {{ copy.fieldMoreSuffix }}</div>
                     <div *ngIf="!item.required_fields.length" class="subtle-text">-</div>
                  </td>
                  <td>
                    <div *ngIf="item.provenance?.source_fields?.length" class="subtle-text">
                      <strong>Source Fields</strong>
                      <div *ngFor="let field of item.provenance?.source_fields" style="word-break: break-all;">{{ field }}</div>
                    </div>
                    <div *ngIf="item.provenance?.phoenix_queries?.length" class="subtle-text" style="margin-top: 6px;">
                      <strong>PhoenixA Queries</strong>
                      <div *ngFor="let q of item.provenance?.phoenix_queries">
                        <code>{{ q.endpoint }}</code>
                        <span *ngIf="q.fields?.length"> · {{ q.fields?.join(', ') }}</span>
                      </div>
                    </div>
                    <div *ngIf="!item.provenance?.source_fields?.length && !item.provenance?.phoenix_queries?.length" class="subtle-text">No provenance yet</div>
                    <div *ngIf="item.notes?.length" class="subtle-text">{{ (item.notes || []).slice(0, 2).join(' · ') }}</div>
                  </td>
                </tr>
                <tr *ngIf="expandedAvailabilityRows[item.name]">
                  <td colspan="8" style="padding: 16px; background: #fcfcfc;">
                    <nz-descriptions nzSize="small" nzBordered [nzColumn]="2">
                      <nz-descriptions-item nzTitle="Category">{{ item.category }}</nz-descriptions-item>
                      <nz-descriptions-item nzTitle="Status / Expected">{{ item.availability_status }} / {{ item.availability_expected }}</nz-descriptions-item>
                      <nz-descriptions-item nzTitle="Required Sources">{{ item.required_data_sources.join(' · ') || '-' }}</nz-descriptions-item>
                      <nz-descriptions-item nzTitle="Missing Sources">{{ item.missing_sources.join(' · ') || '-' }}</nz-descriptions-item>
                       <nz-descriptions-item nzTitle="Missing Fields">{{ item.missing_fields?.join(' · ') || '-' }}</nz-descriptions-item>
                       <nz-descriptions-item nzTitle="Unverified Fields">{{ item.unknown_fields?.join(' · ') || '-' }}</nz-descriptions-item>
                    </nz-descriptions>

                    <div style="margin-top: 12px;">
                      <strong>Full Required Fields</strong>
                      <div *ngIf="item.required_fields.length; else noFieldsBlock" class="subtle-text" style="margin-top: 6px;">
                         <div *ngFor="let field of item.required_fields" style="word-break: break-all; display:flex; align-items:center; gap: 6px; flex-wrap: wrap;">
                           <span>{{ field }}</span>
                           <nz-tag *ngIf="isMissingField(item, field)" nzColor="red">missing</nz-tag>
                           <nz-tag *ngIf="isUnknownField(item, field)" nzColor="orange">unverified</nz-tag>
                         </div>
                      </div>
                      <ng-template #noFieldsBlock><div class="subtle-text">-</div></ng-template>
                    </div>

                    <div style="margin-top: 12px;">
                      <strong>Notes</strong>
                      <div *ngIf="item.notes?.length; else noNotesBlock" class="subtle-text" style="margin-top: 6px;">
                        <div *ngFor="let note of item.notes">{{ note }}</div>
                      </div>
                      <ng-template #noNotesBlock><div class="subtle-text">-</div></ng-template>
                    </div>

                    <div style="margin-top: 12px;">
                      <strong>Source Status Details</strong>
                      <div *ngIf="sourceStatusEntries(item).length; else noSourceStatusBlock" class="subtle-text" style="margin-top: 6px;">
                        <div *ngFor="let sourceEntry of sourceStatusEntries(item)" style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #f0f0f0;">
                          <div><strong>{{ sourceEntry[0] }}</strong> · {{ sourceReadinessLabel(sourceEntry[1]) }}</div>
                          <div>Providers: {{ providerSummary(sourceEntry[1].sources) }}</div>
                          <div>Time Range: {{ timeRangeLabel(sourceEntry[1].time_range) }}</div>
                          <div>Known Fields: {{ (sourceEntry[1].fields_known || []).join(' · ') || '-' }}</div>
                          <div *ngIf="sourceEntry[1].notes?.length">Notes: {{ sourceEntry[1].notes?.join(' · ') }}</div>
                        </div>
                      </div>
                      <ng-template #noSourceStatusBlock><div class="subtle-text">-</div></ng-template>
                    </div>

                    <div style="margin-top: 12px;">
                      <strong>Full Provenance</strong>
                      <div class="subtle-text" style="margin-top: 6px;">
                        <div><strong>Required Data Sources:</strong> {{ item.provenance?.required_data_sources?.join(' · ') || '-' }}</div>
                        <div style="margin-top: 6px;"><strong>Source Fields</strong></div>
                        <div *ngIf="item.provenance?.source_fields?.length; else noProvFieldsBlock">
                          <div *ngFor="let field of item.provenance?.source_fields" style="word-break: break-all;">{{ field }}</div>
                        </div>
                        <ng-template #noProvFieldsBlock><div>-</div></ng-template>
                        <div style="margin-top: 6px;"><strong>PhoenixA Queries</strong></div>
                        <div *ngIf="item.provenance?.phoenix_queries?.length; else noProvQueriesBlock">
                          <div *ngFor="let query of item.provenance?.phoenix_queries" style="margin-bottom: 6px;">
                            <code>{{ query.endpoint }}</code>
                            <div *ngIf="query.fields?.length">Fields: {{ query.fields?.join(', ') }}</div>
                            <div *ngIf="query.params?.length">Params: {{ query.params?.join(', ') }}</div>
                            <div *ngIf="query.notes">Notes: {{ query.notes }}</div>
                          </div>
                        </div>
                        <ng-template #noProvQueriesBlock><div>-</div></ng-template>
                      </div>
                    </div>
                  </td>
                </tr>
                </ng-container>
              </tbody>
            </nz-table>
            <nz-empty *ngIf="filteredAvailabilityItems.length === 0 && !loadingAvailability" nzNotFoundContent="No factors match current availability filter"></nz-empty>
          </div>

          <nz-empty *ngIf="!availabilityResponse && !loadingAvailability" nzNotFoundContent="Click Refresh to load factor availability"></nz-empty>
        </nz-card>
      </nz-tab>
    </nz-tabset>
  `,
  styles: [`
    .action-bar { margin-bottom: 12px; }
    .field-label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
    .result-msg { margin-top: 12px; padding: 8px 12px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; color: #389e0d; }
    .subtle-text { margin-top: 4px; font-size: 12px; color: #8c8c8c; line-height: 1.4; }
    .help-icon { color: #8c8c8c; cursor: help; font-size: 12px; }
    .legend-row { display:flex; gap: 8px; align-items:center; flex-wrap: wrap; }
    :host ::ng-deep .ant-card { margin-bottom: 0; }
  `]
})
export class FactorEngineComponent implements OnInit {
  private svc = inject(FactorService);
  private msg = inject(NzMessageService);
  readonly workbenchStore = inject(WorkbenchStore);

  // -- Meta --
  factorMetas: FactorMeta[] = [];
  loadingMeta = false;
  registrySearch = '';

  // -- Compute Full --
  computeDate = '';
  computeMarket = 'zh_a';
  computing = false;
  computeResult: any = null;

  // -- Compute Incremental --
  incrSymbols = '';
  incrDate = '';
  computingIncr = false;
  incrResult: any = null;

  // -- Snapshot --
  snapSymbol = '';
  snapDate = '';
  loadingSnap = false;
  snapshot: FactorSnapshot | null = null;
  snapshotRawEntries: [string, number][] = [];
  snapshotNormEntries: [string, number][] = [];
  snapshotMissingEntries: [string, string][] = [];

  // -- Ranking --
  rankFactor = '';
  rankDate = '';
  rankTopN = 50;
  loadingRank = false;
  rankItems: FactorRankItem[] = [];

  // -- Availability --
  loadingAvailability = false;
  availabilityResponse: FactorAvailabilityResponse | null = null;
  availabilityItems: FactorAvailabilityItem[] = [];
  availabilitySourceEntries: [string, any][] = [];
  availabilitySearch = '';
  availabilityCategoryFilter = 'all';
  availabilityStatusFilter = 'all';
  availabilityMissingSourceFilter = 'all';
  availabilitySortField: 'availability_status' | 'required_field_count' | 'category' | 'name' = 'availability_status';
  availabilitySortDirection: 'asc' | 'desc' = 'asc';
  availabilityLinkedSourceFilter = '';
  expandedAvailabilityRows: Record<string, boolean> = {};
  selectedTabIndex = 0;
  snapshotFocusFactor = '';
  selectedSource = 'relx';
  private availabilityReadyForAutoReload = false;
  private lastObservedSource = '';

  readonly helpTexts = FACTOR_ENGINE_HELP_TEXTS;
  readonly copy = FACTOR_ENGINE_COPY;
  readonly liveStatusLegend: FactorEngineLegendItem[] = FACTOR_ENGINE_STATUS_LEGENDS.live;
  readonly expectedStatusLegend: FactorEngineLegendItem[] = FACTOR_ENGINE_STATUS_LEGENDS.expected;
  readonly sourceReadinessLegend: FactorEngineLegendItem[] = FACTOR_ENGINE_STATUS_LEGENDS.sourceReadiness;

  constructor() {
    effect(() => {
      const source = this.workbenchStore.selectedSource();
      const previousSource = this.lastObservedSource;
      this.selectedSource = source;
      this.lastObservedSource = source;
      if (!this.availabilityReadyForAutoReload || !previousSource || previousSource === source) {
        return;
      }
      this.resetSourceBoundState();
      this.loadAvailability();
      this.msg.info(`Factor Engine source switched to ${this.sourceLabel(source)}. Availability refreshed; rerun compute/snapshot/ranking if needed.`);
    });
  }

  ngOnInit() {
    this.workbenchStore.loadSources(() => {
      this.selectedSource = this.workbenchStore.selectedSource();
      this.availabilityReadyForAutoReload = true;
      this.loadAvailability();
    });
    this.loadMeta();
  }

  loadMeta() {
    this.loadingMeta = true;
    this.svc.getMeta().subscribe({
      next: data => { this.factorMetas = data; this.loadingMeta = false; },
      error: () => { this.msg.error('Failed to load factor meta'); this.loadingMeta = false; }
    });
  }

  computeFull() {
    if (!this.computeDate) {
      this.computeDate = this.todayStr();
    }
    this.computing = true;
    this.computeResult = null;
    this.selectedSource = this.workbenchStore.selectedSource();
    this.svc.computeFull(this.computeDate, this.computeMarket, this.selectedSource).subscribe({
      next: res => { this.computeResult = res; this.computing = false; this.msg.success('Full computation completed'); },
      error: err => { this.msg.error('Computation failed: ' + (err.error?.detail || err.message)); this.computing = false; }
    });
  }

  computeIncremental() {
    if (!this.incrDate) this.incrDate = this.todayStr();
    const symbols = this.incrSymbols.split(',').map(s => s.trim()).filter(s => s);
    if (!symbols.length) { this.msg.warning('Please enter at least one symbol'); return; }
    this.computingIncr = true;
    this.incrResult = null;
    this.selectedSource = this.workbenchStore.selectedSource();
    this.svc.computeIncremental(symbols, this.incrDate, 'zh_a', this.selectedSource).subscribe({
      next: res => { this.incrResult = res; this.computingIncr = false; this.msg.success('Incremental computation completed'); },
      error: err => { this.msg.error('Computation failed: ' + (err.error?.detail || err.message)); this.computingIncr = false; }
    });
  }

  loadSnapshot() {
    this.loadingSnap = true;
    this.snapshot = null;
    this.selectedSource = this.workbenchStore.selectedSource();
    this.svc.getSnapshot(this.snapSymbol, this.snapDate, 'zh_a', this.selectedSource).subscribe({
      next: data => {
        this.snapshot = data;
        this.snapshotRawEntries = Object.entries(data.raw_factors || {}).sort() as [string, number][];
        this.snapshotNormEntries = Object.entries(data.norm_factors || {}).sort() as [string, number][];
        this.snapshotMissingEntries = Object.entries(data.meta?.missing_reasons || {}).sort() as [string, string][];
        this.scrollToSnapshotFocus();
        this.loadingSnap = false;
      },
      error: err => {
        this.msg.error(err.status === 404 ? 'Snapshot not found' : 'Failed to load snapshot');
        this.loadingSnap = false;
      }
    });
  }

  loadRanking() {
    this.loadingRank = true;
    this.rankItems = [];
    this.selectedSource = this.workbenchStore.selectedSource();
    this.svc.getRanking(this.rankFactor, this.rankDate, 'zh_a', this.rankTopN, this.selectedSource).subscribe({
      next: data => { this.rankItems = data; this.loadingRank = false; },
      error: () => { this.msg.error('Failed to load ranking'); this.loadingRank = false; }
    });
  }

  loadAvailability(refresh = false) {
    this.loadingAvailability = true;
    this.availabilityResponse = null;
    this.availabilityItems = [];
    this.availabilitySourceEntries = [];
    this.expandedAvailabilityRows = {};
    this.selectedSource = this.workbenchStore.selectedSource();
    this.svc.getAvailability(refresh, this.selectedSource).subscribe({
      next: data => {
        this.availabilityResponse = data;
        this.availabilityItems = data.factors || [];
        this.availabilitySourceEntries = Object.entries(data.source_status || {}).sort() as [string, any][];
        this.expandedAvailabilityRows = {};
        this.availabilityLinkedSourceFilter = '';
        this.loadingAvailability = false;
      },
      error: err => {
        this.msg.error('Failed to load factor availability: ' + (err.error?.detail || err.message || 'unknown error'));
        this.loadingAvailability = false;
      }
    });
  }

  onSourceChange(source: string): void {
    this.workbenchStore.selectSource(source);
  }

  get filteredFactorMetas(): FactorMeta[] {
    const query = this.registrySearch.trim().toLowerCase();
    if (!query) {
      return this.factorMetas;
    }
    return this.factorMetas.filter(item => [item.name, item.cn_name, item.category, item.description || ''].join(' ').toLowerCase().includes(query));
  }

  get filteredAvailabilityItems(): FactorAvailabilityItem[] {
    const query = this.availabilitySearch.trim().toLowerCase();
    const filtered = this.availabilityItems.filter(item => {
      if (this.availabilityStatusFilter !== 'all' && item.availability_status !== this.availabilityStatusFilter) {
        return false;
      }
      if (this.availabilityCategoryFilter !== 'all' && item.category !== this.availabilityCategoryFilter) {
        return false;
      }
      if (this.availabilityMissingSourceFilter === 'none' && item.missing_sources.length > 0) {
        return false;
      }
      if (this.availabilityMissingSourceFilter !== 'all' && this.availabilityMissingSourceFilter !== 'none' && !item.missing_sources.includes(this.availabilityMissingSourceFilter)) {
        return false;
      }
      if (this.availabilityLinkedSourceFilter && !item.required_data_sources.includes(this.availabilityLinkedSourceFilter) && !item.missing_sources.includes(this.availabilityLinkedSourceFilter)) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = [
        item.name,
        item.cn_name,
        item.category,
        item.availability_status,
        item.availability_expected,
        ...item.required_data_sources,
        ...item.required_fields,
        ...item.missing_sources,
        ...(item.missing_fields || []),
        ...(item.unknown_fields || []),
        ...(item.notes || []),
        ...(item.provenance?.source_fields || []),
        ...((item.provenance?.phoenix_queries || []).map(q => q.endpoint || '')),
      ].join(' ').toLowerCase();
      return haystack.includes(query);
    });
    const direction = this.availabilitySortDirection === 'asc' ? 1 : -1;
    const statusRank: Record<string, number> = {available: 0, partial: 1, missing: 2, unknown: 3};
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (this.availabilitySortField) {
        case 'required_field_count':
          cmp = a.required_field_count - b.required_field_count;
          break;
        case 'category':
          cmp = a.category.localeCompare(b.category);
          break;
        case 'name':
          cmp = a.name.localeCompare(b.name);
          break;
        case 'availability_status':
        default:
          cmp = (statusRank[a.availability_status] ?? 99) - (statusRank[b.availability_status] ?? 99);
          if (cmp === 0) {
            cmp = a.name.localeCompare(b.name);
          }
          break;
      }
      return cmp * direction;
    });
  }

  get availabilityCategoryOptions(): string[] {
    return Array.from(new Set(this.availabilityItems.map(item => item.category).filter(Boolean))).sort();
  }

  get availabilityMissingSourceOptions(): string[] {
    return Array.from(new Set(this.availabilityItems.flatMap(item => item.missing_sources || []).filter(Boolean))).sort();
  }

  toggleAvailabilityDetails(name: string): void {
    this.expandedAvailabilityRows[name] = !this.expandedAvailabilityRows[name];
  }

  expandAllAvailabilityDetails(): void {
    this.expandedAvailabilityRows = Object.fromEntries(this.filteredAvailabilityItems.map(item => [item.name, true]));
  }

  collapseAllAvailabilityDetails(): void {
    this.expandedAvailabilityRows = {};
  }

  toggleLinkedSourceFilter(source: string): void {
    this.availabilityLinkedSourceFilter = this.availabilityLinkedSourceFilter === source ? '' : source;
  }

  clearLinkedSourceFilter(): void {
    this.availabilityLinkedSourceFilter = '';
  }

  sourceStatusEntries(item: FactorAvailabilityItem): [string, any][] {
    return Object.entries(item.source_status || {}).sort() as [string, any][];
  }

  timeRangeLabel(timeRange?: Record<string, string> | null): string {
    if (!timeRange) {
      return '-';
    }
    const minDate = timeRange['min_date'] || '';
    const maxDate = timeRange['max_date'] || '';
    if (!minDate && !maxDate) {
      return '-';
    }
    return `${minDate || '?'} → ${maxDate || '?'}`;
  }

  jumpToRegistry(item: FactorAvailabilityItem): void {
    this.registrySearch = item.name;
    this.selectedTabIndex = 0;
    this.msg.info(`Focused ${item.name} in Factor Registry`);
  }

  jumpToRanking(item: FactorAvailabilityItem): void {
    this.rankFactor = item.name;
    if (!this.rankDate) {
      this.rankDate = this.todayStr();
    }
    this.selectedTabIndex = 3;
    this.loadRanking();
  }

  jumpToSnapshot(item: FactorAvailabilityItem): void {
    this.snapshotFocusFactor = item.name;
    this.selectedTabIndex = 2;
    if (this.snapSymbol && this.snapDate) {
      this.loadSnapshot();
    } else {
      this.msg.info(`Switched to Snapshot. Enter symbol/date to inspect ${item.name}.`);
    }
  }

  snapshotRowId(section: 'raw' | 'norm' | 'missing', factorName: string): string {
    return `snapshot-${section}-${factorName}`.replace(/[^a-zA-Z0-9_-]/g, '-');
  }

  private scrollToSnapshotFocus(): void {
    if (!this.snapshotFocusFactor) {
      return;
    }
    setTimeout(() => {
      const targets = [
        this.snapshotRowId('raw', this.snapshotFocusFactor),
        this.snapshotRowId('norm', this.snapshotFocusFactor),
        this.snapshotRowId('missing', this.snapshotFocusFactor),
      ];
      for (const id of targets) {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({behavior: 'smooth', block: 'center'});
          break;
        }
      }
    }, 0);
  }

  getRankValue(item: FactorRankItem): number {
    const val = item[this.rankFactor];
    return typeof val === 'number' ? val : 0;
  }

  categoryColor(cat: string): string {
    const map: Record<string, string> = {
      profitability: 'green', growth: 'blue', quality: 'purple', solvency: 'gold',
      valuation: 'magenta', efficiency: 'cyan', per_share: 'orange'
    };
    return map[cat?.toLowerCase()] || 'default';
  }

  financialPolicyLabel(meta: FactorMeta): string {
    const mode = meta.financial_policy?.mode || (meta.exclude_financial ? 'financial_variant_pending' : 'standard');
    const map: Record<string, string> = {
      standard: 'Standard',
      financial_variant_pending: 'Financial Variant Pending',
      excluded: 'Excluded',
    };
    return map[mode] || mode;
  }

  financialPolicyColor(meta: FactorMeta): string {
    const mode = meta.financial_policy?.mode || (meta.exclude_financial ? 'financial_variant_pending' : 'standard');
    const map: Record<string, string> = {
      standard: 'green',
      financial_variant_pending: 'orange',
      excluded: 'red',
    };
    return map[mode] || 'default';
  }

  primaryPhoenixPath(meta: FactorMeta): string {
    return meta.phoenix_queries?.[0]?.endpoint || 'registry-only';
  }

  sourceFieldPreview(meta: FactorMeta): string {
    const fields = meta.source_fields || [];
    if (!fields.length) {
      return 'No catalog lineage yet';
    }
    return fields.slice(0, 3).join(' · ');
  }

  availabilityPreview(meta: FactorMeta): string {
    const reqs = meta.availability?.requirements || [];
    if (!reqs.length) {
      return 'Runtime details in snapshot meta';
    }
    return reqs.slice(0, 2).join(' · ');
  }

  availabilityColor(expected?: string): string {
    const map: Record<string, string> = {
      ready: 'green',
      conditional: 'orange',
      blocked: 'red',
    };
    return map[(expected || '').toLowerCase()] || 'default';
  }

  availabilityRuntimeColor(status?: string): string {
    const map: Record<string, string> = {
      available: 'green',
      partial: 'orange',
      missing: 'red',
      unknown: 'default',
    };
    return map[(status || '').toLowerCase()] || 'default';
  }

  providerSummary(sources?: Record<string, number>): string {
    const entries = Object.entries(sources || {});
    if (!entries.length) {
      return '-';
    }
    return entries.map(([name, count]) => `${name} (${count})`).join(' · ');
  }

  sourceLabel(name: string): string {
    if (!name) {
      return '-';
    }
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  helpText(key: FactorEngineHelpKey): string {
    return this.helpTexts[key] || '';
  }

  knownFieldsSummary(fields?: string[]): string {
    const items = fields || [];
    if (!items.length) {
      return '-';
    }
    if (items.length <= 4) {
      return items.join(' · ');
    }
    return `${items.slice(0, 4).join(' · ')} · +${items.length - 4} more`;
  }

  previewList(items?: string[] | null, limit: number = 3): string {
    const values = items || [];
    if (!values.length) {
      return '-';
    }
    if (values.length <= limit) {
      return values.join(' · ');
    }
    return `${values.slice(0, limit).join(' · ')} · +${values.length - limit} more`;
  }

  dataTypeSummary(dataTypes?: string[]): string {
    const items = dataTypes || [];
    if (!items.length) {
      return '-';
    }
    return items.join(' · ');
  }

  formatRowCount(rowCount?: number): string {
    if (typeof rowCount !== 'number' || Number.isNaN(rowCount)) {
      return '-';
    }
    return rowCount.toLocaleString();
  }

  capabilitySourceColor(source?: string): string {
    const map: Record<string, string> = {
      phoenixA_catalog: 'green',
      phoenixA_catalog_empty: 'orange',
      unavailable: 'red',
    };
    return map[source || ''] || 'default';
  }

  capabilitySourceMessage(source?: string): string {
    return FACTOR_ENGINE_CAPABILITY_SOURCE_MESSAGES[source || ''] || '';
  }

  isMissingField(item: FactorAvailabilityItem, field: string): boolean {
    return (item.missing_fields || []).includes(field);
  }

  isUnknownField(item: FactorAvailabilityItem, field: string): boolean {
    return (item.unknown_fields || []).includes(field);
  }

  sourceReadinessLabel(detail?: {status?: string; available?: boolean} | null): string {
    const status = (detail?.status || '').toLowerCase();
    if (status) {
      return status;
    }
    return detail?.available ? 'ready' : 'missing';
  }

  sourceReadinessColor(detail?: {status?: string; available?: boolean} | null): string {
    const status = (detail?.status || '').toLowerCase();
    const map: Record<string, string> = {
      ready: 'green',
      empty: 'orange',
      missing: 'red',
      unknown: 'default',
    };
    if (status) {
      return map[status] || 'default';
    }
    return detail?.available ? 'green' : 'red';
  }

  freshnessColor(label?: string): string {
    const map: Record<string, string> = {
      fresh: 'green',
      acceptable: 'blue',
      stale: 'orange',
      very_stale: 'red',
    };
    return map[(label || '').toLowerCase()] || 'default';
  }

  private resetSourceBoundState(): void {
    this.computeResult = null;
    this.incrResult = null;
    this.snapshot = null;
    this.snapshotFocusFactor = '';
    this.snapshotRawEntries = [];
    this.snapshotNormEntries = [];
    this.snapshotMissingEntries = [];
    this.rankItems = [];
    this.availabilityResponse = null;
    this.availabilityItems = [];
    this.availabilitySourceEntries = [];
    this.expandedAvailabilityRows = {};
    this.availabilityLinkedSourceFilter = '';
  }

  private todayStr(): string {
    const d = new Date();
    return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  }
}

