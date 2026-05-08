import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { AtlasApiService, EventItem } from '../services/atlas-api.service';

@Component({
  selector: 'app-event-impact',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzCardModule, NzTableModule, NzTagModule,
    NzSpinModule, NzEmptyModule, NzIconModule, NzButtonModule,
    NzInputModule, NzSelectModule, NzDividerModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <!-- Filters -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          <nz-select [(ngModel)]="filterType" nzPlaceHolder="Event Type" nzSize="small"
            nzAllowClear style="width: 160px;" (ngModelChange)="loadEvents()">
            @for (t of eventTypes; track t) {
              <nz-option [nzValue]="t" [nzLabel]="t"></nz-option>
            }
          </nz-select>
          <input nz-input [(ngModel)]="filterEntity" nzSize="small" placeholder="Entity name..."
            style="width: 180px;" (keyup.enter)="loadEvents()" />
          <button nz-button nzSize="small" nzType="primary" [nzLoading]="loadingEvents" (click)="loadEvents()">
            <span nz-icon nzType="filter"></span> Filter
          </button>
        </div>
      </nz-card>

      <!-- Events + Impact -->
      <div style="display: flex; gap: 12px; min-height: 500px;">
        <!-- Events list -->
        <nz-card nzSize="small" nzTitle="Events" [nzBordered]="false"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: auto;">
          @if (loadingEvents) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else if (events.length > 0) {
            <nz-table #evtTable [nzData]="events" nzSize="small" [nzShowPagination]="false"
              [nzScroll]="{ y: '440px' }" nzFrontPagination="false">
              <thead><tr>
                <th nzWidth="130px">Entity</th>
                <th nzWidth="100px">Type</th>
                <th nzWidth="55px">Dir</th>
                <th nzWidth="55px">Sev</th>
                <th nzWidth="45px">Srcs</th>
                <th nzWidth="75px">Time</th>
                <th nzWidth="60px"></th>
              </tr></thead>
              <tbody>
                @for (e of evtTable.data; track e.id) {
                  <tr [style.background]="selectedEvent?.id === e.id ? '#e6f7ff' : ''"
                    style="cursor: pointer;" (click)="selectEvent(e)">
                    <td style="font-size: 12px; font-weight: 500;">{{ e.entity_name }}</td>
                    <td><nz-tag nzColor="blue" style="font-size: 10px;">{{ e.event_type }}</nz-tag></td>
                    <td>
                      <nz-tag [nzColor]="e.direction === 'up' ? 'red' : e.direction === 'down' ? 'green' : 'default'"
                        style="font-size: 10px;">{{ e.direction || '-' }}</nz-tag>
                    </td>
                    <td>
                      <nz-tag [nzColor]="e.severity === 'high' ? 'red' : e.severity === 'medium' ? 'orange' : 'default'"
                        style="font-size: 10px;">{{ e.severity }}</nz-tag>
                    </td>
                    <td style="font-size: 12px; text-align: center;">{{ e.source_count }}</td>
                    <td style="font-size: 11px; color: #999;">{{ e.time_bucket }}</td>
                    <td>
                      <button nz-button nzType="link" nzSize="small" (click)="analyzeEvent(e); $event.stopPropagation()">
                        <span nz-icon nzType="thunderbolt"></span>
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          } @else {
            <nz-empty nzNotFoundContent="No events found"></nz-empty>
          }
        </nz-card>

        <!-- Impact analysis -->
        <nz-card nzSize="small" nzTitle="Impact Analysis" [nzBordered]="false"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: auto;">
          @if (loadingImpact) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else if (impactResult) {
            <div style="margin-bottom: 8px;">
              <span style="font-size: 13px; font-weight: 500;">{{ impactResult.event }}</span>
              <nz-tag nzColor="blue" style="margin-left: 8px;">{{ impactResult.total_affected }} affected</nz-tag>
            </div>

            @if (impactResult.direct_impacts?.length) {
              <div style="font-size: 12px; font-weight: 500; margin: 8px 0 4px;">Direct Impacts</div>
              @for (imp of impactResult.direct_impacts; track imp.company) {
                <div style="display: flex; gap: 6px; padding: 4px 0; border-bottom: 1px solid #f5f5f5; font-size: 12px; align-items: center;">
                  <span style="font-weight: 500; min-width: 80px;">{{ imp.company }}</span>
                  <nz-tag [nzColor]="imp.direction === 'positive' ? 'green' : imp.direction === 'negative' ? 'red' : 'default'"
                    style="font-size: 10px;">{{ imp.direction }}</nz-tag>
                  <nz-tag style="font-size: 10px;">{{ imp.type }}</nz-tag>
                  <span style="color: #999; font-size: 11px; flex: 1;">{{ imp.path }}</span>
                </div>
              }
            }

            @if (impactResult.indirect_impacts?.length) {
              <div style="font-size: 12px; font-weight: 500; margin: 12px 0 4px;">Indirect Impacts</div>
              @for (imp of impactResult.indirect_impacts; track imp.company) {
                <div style="display: flex; gap: 6px; padding: 4px 0; border-bottom: 1px solid #f5f5f5; font-size: 12px; align-items: center;">
                  <span style="font-weight: 500; min-width: 80px;">{{ imp.company }}</span>
                  <nz-tag style="font-size: 10px;">hop {{ imp.hop }}</nz-tag>
                  <span style="color: #999; font-size: 11px;">{{ imp.via_relation }}</span>
                </div>
              }
            }

            @if (impactResult.llm_analysis) {
              <nz-divider nzText="LLM Analysis" nzOrientation="left"></nz-divider>
              <div style="font-size: 12px; white-space: pre-wrap; line-height: 1.6; color: #333;">
                {{ impactResult.llm_analysis }}
              </div>
            }
          } @else {
            <nz-empty nzNotFoundContent="Select an event and click ⚡ to analyze impact"></nz-empty>
          }
        </nz-card>
      </div>
    </div>
  `,
})
export class EventImpactComponent implements OnInit {
  private api = inject(AtlasApiService);
  private msg = inject(NzMessageService);

  events: EventItem[] = [];
  selectedEvent: EventItem | null = null;
  impactResult: any = null;
  loadingEvents = false;
  loadingImpact = false;
  filterType = '';
  filterEntity = '';

  eventTypes = [
    'price_change', 'supply_change', 'policy_new', 'policy_change', 'tariff_change',
    'tech_breakthrough', 'capacity_change', 'merger_acquisition', 'investment',
    'leadership_change', 'earnings_beat', 'earnings_miss', 'accident_disaster', 'sanction', 'other',
  ];

  ngOnInit(): void {
    this.loadEvents();
  }

  loadEvents(): void {
    this.loadingEvents = true;
    this.api.listEvents({
      event_type: this.filterType,
      entity_name: this.filterEntity,
      limit: 100,
    }).subscribe({
      next: (r) => { this.events = r.events || []; this.loadingEvents = false; },
      error: () => { this.msg.error('Failed to load events'); this.loadingEvents = false; },
    });
  }

  selectEvent(e: EventItem): void {
    this.selectedEvent = e;
  }

  analyzeEvent(e: EventItem): void {
    this.selectedEvent = e;
    this.loadingImpact = true;
    this.api.getEventImpact(e.entity_name).subscribe({
      next: (r) => { this.impactResult = r; this.loadingImpact = false; },
      error: () => { this.msg.error('Failed to analyze impact'); this.loadingImpact = false; },
    });
  }
}

