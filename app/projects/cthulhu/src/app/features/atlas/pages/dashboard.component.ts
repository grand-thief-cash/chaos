import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzMessageService } from 'ng-zorro-antd/message';
import { AtlasApiService, DailyRun, EventItem, GraphStats } from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-dashboard',
  standalone: true,
  imports: [
    CommonModule, NzCardModule, NzStatisticModule, NzGridModule,
    NzTableModule, NzTagModule, NzSpinModule, NzEmptyModule,
    NzIconModule, NzButtonModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- Stats Row -->
      <div nz-row [nzGutter]="16">
        <div nz-col [nzSpan]="6">
          <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <nz-statistic [nzValue]="stats?.total_nodes || 0" nzTitle="Total Nodes"
              [nzPrefix]="nodeIcon"></nz-statistic>
            <ng-template #nodeIcon><span nz-icon nzType="apartment" style="color: #1890ff;"></span></ng-template>
          </nz-card>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <nz-statistic [nzValue]="stats?.total_edges || 0" nzTitle="Total Edges"
              [nzPrefix]="edgeIcon"></nz-statistic>
            <ng-template #edgeIcon><span nz-icon nzType="branches" style="color: #52c41a;"></span></ng-template>
          </nz-card>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <nz-statistic [nzValue]="recentEvents.length" nzTitle="Recent Events (7d)"
              [nzPrefix]="eventIcon"></nz-statistic>
            <ng-template #eventIcon><span nz-icon nzType="thunderbolt" style="color: #faad14;"></span></ng-template>
          </nz-card>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            <nz-statistic [nzValue]="dailyRuns.length" nzTitle="Pipeline Runs"
              [nzPrefix]="runIcon"></nz-statistic>
            <ng-template #runIcon><span nz-icon nzType="rocket" style="color: #722ed1;"></span></ng-template>
          </nz-card>
        </div>
      </div>

      <!-- Node type breakdown -->
      @if (stats?.node_counts) {
        <nz-card nzSize="small" nzTitle="Node Types" [nzBordered]="false"
          style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="display: flex; flex-wrap: wrap; gap: 12px;">
            @for (entry of nodeTypeEntries; track entry[0]) {
              <div style="display: flex; align-items: center; gap: 6px;">
                <nz-tag [nzColor]="getNodeColor(entry[0])">{{ entry[0] }}</nz-tag>
                <span style="font-size: 14px; font-weight: 500;">{{ entry[1] }}</span>
              </div>
            }
          </div>
        </nz-card>
      }

      <!-- Two columns: Recent Events + Daily Runs -->
      <div style="display: flex; gap: 16px;">
        <!-- Recent Events -->
        <nz-card nzSize="small" nzTitle="Recent Events" [nzBordered]="false"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          @if (loadingEvents) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else if (recentEvents.length > 0) {
            <nz-table #evtTable [nzData]="recentEvents" nzSize="small" [nzShowPagination]="false"
              [nzScroll]="{ y: '320px' }" nzFrontPagination="false">
              <thead><tr>
                <th nzWidth="140px">Entity</th>
                <th nzWidth="110px">Type</th>
                <th nzWidth="60px">Dir.</th>
                <th nzWidth="60px">Sev.</th>
                <th nzWidth="50px">Srcs</th>
                <th>Time</th>
              </tr></thead>
              <tbody>
                @for (e of evtTable.data; track e.id) {
                  <tr>
                    <td style="font-size: 12px; font-weight: 500;">{{ e.entity_name }}</td>
                    <td><nz-tag nzColor="blue" style="font-size: 11px;">{{ e.event_type }}</nz-tag></td>
                    <td>
                      <nz-tag [nzColor]="e.direction === 'up' ? 'red' : e.direction === 'down' ? 'green' : 'default'"
                        style="font-size: 11px;">{{ e.direction || '-' }}</nz-tag>
                    </td>
                    <td>
                      <nz-tag [nzColor]="e.severity === 'high' ? 'red' : e.severity === 'medium' ? 'orange' : 'default'"
                        style="font-size: 11px;">{{ e.severity }}</nz-tag>
                    </td>
                    <td style="font-size: 12px; text-align: center;">{{ e.source_count }}</td>
                    <td style="font-size: 11px; color: #999;">{{ e.time_bucket }}</td>
                  </tr>
                }
              </tbody>
            </nz-table>
          } @else {
            <nz-empty nzNotFoundContent="No recent events"></nz-empty>
          }
        </nz-card>

        <!-- Daily Runs -->
        <nz-card nzSize="small" nzTitle="Pipeline Runs" [nzBordered]="false"
          [nzExtra]="runExtra"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <ng-template #runExtra>
            <button nz-button nzType="primary" nzSize="small" [nzLoading]="triggeringPipeline"
              (click)="triggerPipeline()">
              <span nz-icon nzType="play-circle"></span> Run Now
            </button>
          </ng-template>
          @if (loadingRuns) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 40px;"></nz-spin>
          } @else if (dailyRuns.length > 0) {
            <nz-table #runTable [nzData]="dailyRuns" nzSize="small" [nzShowPagination]="false"
              [nzScroll]="{ y: '320px' }" nzFrontPagination="false">
              <thead><tr>
                <th nzWidth="90px">Date</th>
                <th nzWidth="50px">Docs</th>
                <th nzWidth="60px">Events</th>
                <th nzWidth="60px">Dedup</th>
                <th nzWidth="70px">Cost</th>
                <th nzWidth="70px">Status</th>
              </tr></thead>
              <tbody>
                @for (r of runTable.data; track r.id) {
                  <tr>
                    <td style="font-size: 12px; font-family: monospace;">{{ r.run_date }}</td>
                    <td style="font-size: 12px; text-align: center;">{{ r.docs_fetched }}</td>
                    <td style="font-size: 12px; text-align: center;">{{ r.events_new }}</td>
                    <td style="font-size: 12px; text-align: center;">{{ r.events_deduped }}</td>
                    <td style="font-size: 12px;">\${{ r.total_cost_usd | number:'1.2-2' }}</td>
                    <td>
                      <nz-tag [nzColor]="r.status === 'completed' ? 'green' : r.status === 'failed' ? 'red' : 'blue'"
                        style="font-size: 11px;">{{ r.status }}</nz-tag>
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          } @else {
            <nz-empty nzNotFoundContent="No pipeline runs yet"></nz-empty>
          }
        </nz-card>
      </div>
    </div>
  `,
})
export class AtlasDashboardComponent implements OnInit {
  private api = inject(AtlasApiService);
  private msg = inject(NzMessageService);

  stats: GraphStats | null = null;
  recentEvents: EventItem[] = [];
  dailyRuns: DailyRun[] = [];
  loadingEvents = false;
  loadingRuns = false;
  triggeringPipeline = false;

  get nodeTypeEntries(): [string, number][] {
    if (!this.stats?.node_counts) return [];
    return Object.entries(this.stats.node_counts).filter(([, v]) => v > 0);
  }

  ngOnInit(): void {
    this.loadStats();
    this.loadEvents();
    this.loadRuns();
  }

  private loadStats(): void {
    this.api.getGraphStats().subscribe({
      next: (s) => this.stats = s,
      error: () => {},
    });
  }

  private loadEvents(): void {
    this.loadingEvents = true;
    this.api.getRecentEvents(7, 20).subscribe({
      next: (r) => { this.recentEvents = r.events || []; this.loadingEvents = false; },
      error: () => this.loadingEvents = false,
    });
  }

  private loadRuns(): void {
    this.loadingRuns = true;
    this.api.getDailyRuns(15).subscribe({
      next: (r) => { this.dailyRuns = r.runs || []; this.loadingRuns = false; },
      error: () => this.loadingRuns = false,
    });
  }

  triggerPipeline(): void {
    this.triggeringPipeline = true;
    this.api.triggerDailyPipeline().subscribe({
      next: () => { this.msg.success('Pipeline triggered'); this.triggeringPipeline = false; this.loadRuns(); },
      error: () => { this.msg.error('Failed to trigger pipeline'); this.triggeringPipeline = false; },
    });
  }

  getNodeColor(label: string): string {
    const colors: Record<string, string> = {
      Company: 'blue', Product: 'cyan', Resource: 'orange', Industry: 'green',
      Technology: 'purple', Event: 'red', Policy: 'magenta', Asset: 'geekblue', Market: 'lime',
    };
    return colors[label] || 'default';
  }
}

