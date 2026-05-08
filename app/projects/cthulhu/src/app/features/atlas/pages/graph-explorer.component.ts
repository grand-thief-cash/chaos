import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NgxEchartsModule } from 'ngx-echarts';
import { EChartsOption } from 'echarts';
import { AtlasApiService } from '../services/atlas-api.service';

const NODE_COLORS: Record<string, string> = {
  Company: '#1890ff', Product: '#13c2c2', Resource: '#fa8c16', Industry: '#52c41a',
  Technology: '#722ed1', Event: '#f5222d', Policy: '#eb2f96', Asset: '#2f54eb', Market: '#a0d911',
};

@Component({
  selector: 'app-graph-explorer',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzCardModule, NzInputModule, NzButtonModule,
    NzSpinModule, NzEmptyModule, NzIconModule, NzTagModule, NzTableModule,
    NzTabsModule, NgxEchartsModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <!-- Search -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: center;">
          <input nz-input [(ngModel)]="searchText" placeholder="Search company name..."
            nzSize="small" style="max-width: 300px;" (keyup.enter)="search()" />
          <button nz-button nzType="primary" nzSize="small" [nzLoading]="loading" (click)="search()">
            <span nz-icon nzType="search"></span> Search
          </button>
          @if (selectedCompany) {
            <nz-tag nzColor="blue" [nzMode]="'closeable'" (nzOnClose)="clearSelection()">
              {{ selectedCompany }}
            </nz-tag>
          }
        </div>
      </nz-card>

      <!-- Main: Graph + Details -->
      <div style="display: flex; gap: 12px; min-height: 550px;">
        <!-- Graph visualization -->
        <nz-card nzSize="small" [nzBordered]="false"
          style="flex: 1; box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          @if (loading) {
            <nz-spin nzSimple style="display: flex; justify-content: center; padding: 80px;"></nz-spin>
          } @else if (chartOptions) {
            <div echarts [options]="chartOptions" style="width: 100%; height: 500px;"
              (chartClick)="onChartClick($event)"></div>
          } @else {
            <nz-empty nzNotFoundContent="Search a company to visualize its supply chain"></nz-empty>
          }
        </nz-card>

        <!-- Details panel -->
        @if (selectedCompany) {
          <nz-card nzSize="small" [nzBordered]="false"
            style="flex: 0 0 360px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: auto;">
            <nz-tabset nzSize="small" [nzAnimated]="false">
              <nz-tab nzTitle="Relationships">
                @if (relationships.length > 0) {
                  <nz-table #relTable [nzData]="relationships" nzSize="small" [nzShowPagination]="false"
                    [nzScroll]="{ y: '420px' }" nzFrontPagination="false">
                    <thead><tr>
                      <th nzWidth="120px">Type</th>
                      <th>Target</th>
                      <th nzWidth="50px">Dir</th>
                    </tr></thead>
                    <tbody>
                      @for (r of relTable.data; track $index) {
                        <tr>
                          <td style="font-size: 11px;"><nz-tag>{{ r.rel_type }}</nz-tag></td>
                          <td style="font-size: 12px; cursor: pointer; color: #1890ff;"
                            (click)="exploreNeighbor(r)">
                            {{ r.neighbor?.name || r.neighbor?.normalized_name || '?' }}
                          </td>
                          <td style="font-size: 11px;">{{ r.direction === 'outgoing' ? '→' : '←' }}</td>
                        </tr>
                      }
                    </tbody>
                  </nz-table>
                } @else {
                  <nz-empty nzNotFoundContent="No relationships"></nz-empty>
                }
              </nz-tab>
              <nz-tab nzTitle="Timeline">
                @if (timeline.length > 0) {
                  <div style="max-height: 450px; overflow: auto;">
                    @for (t of timeline; track $index) {
                      <div style="padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px;">
                        <span style="color: #999; font-family: monospace;">{{ t.time }}</span>
                        <nz-tag nzColor="blue" style="margin-left: 6px; font-size: 10px;">{{ t.rel_type }}</nz-tag>
                        <span style="margin-left: 4px;">{{ t.neighbor_name }}</span>
                      </div>
                    }
                  </div>
                } @else {
                  <nz-empty nzNotFoundContent="No timeline data"></nz-empty>
                }
              </nz-tab>
              <nz-tab nzTitle="Competitors">
                @if (competitors.length > 0) {
                  @for (c of competitors; track c.competitor) {
                    <div style="padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px;">
                      <span style="font-weight: 500; cursor: pointer; color: #1890ff;"
                        (click)="searchText = c.competitor; search()">{{ c.competitor }}</span>
                      @if (c.product) {
                        <nz-tag style="margin-left: 6px;">{{ c.product }}</nz-tag>
                      }
                    </div>
                  }
                } @else {
                  <nz-empty nzNotFoundContent="No competitors found"></nz-empty>
                }
              </nz-tab>
            </nz-tabset>
          </nz-card>
        }
      </div>
    </div>
  `,
})
export class GraphExplorerComponent {
  private api = inject(AtlasApiService);
  private msg = inject(NzMessageService);

  searchText = '';
  selectedCompany = '';
  loading = false;
  chartOptions: EChartsOption | null = null;
  relationships: any[] = [];
  timeline: any[] = [];
  competitors: any[] = [];

  search(): void {
    if (!this.searchText.trim()) return;
    this.selectedCompany = this.searchText.trim();
    this.loading = true;
    this.loadCompanyGraph(this.selectedCompany);
  }

  clearSelection(): void {
    this.selectedCompany = '';
    this.chartOptions = null;
    this.relationships = [];
    this.timeline = [];
    this.competitors = [];
  }

  private loadCompanyGraph(name: string): void {
    this.api.getCompany(name).subscribe({
      next: (data) => {
        if (data.company) {
          this.relationships = data.relationships || [];
          this.buildChart(name, data);
          this.loadTimeline(name);
          this.loadCompetitors(name);
        } else {
          this.msg.info('Company not found');
          this.relationships = [];
          this.chartOptions = null;
        }
        this.loading = false;
      },
      error: () => { this.msg.error('Failed to load company'); this.loading = false; },
    });
  }

  private loadTimeline(name: string): void {
    this.api.getCompanyTimeline(name).subscribe({
      next: (r) => this.timeline = r.timeline || [],
      error: () => {},
    });
  }

  private loadCompetitors(name: string): void {
    this.api.getCompanyCompetitors(name).subscribe({
      next: (r) => this.competitors = r.competitors || [],
      error: () => {},
    });
  }

  private buildChart(centerName: string, data: any): void {
    const nodes: any[] = [];
    const links: any[] = [];
    const nodeSet = new Set<string>();

    // Center node
    nodes.push({
      name: centerName, symbolSize: 40,
      itemStyle: { color: NODE_COLORS['Company'] },
      label: { show: true, fontSize: 12, fontWeight: 'bold' },
      category: 0,
    });
    nodeSet.add(centerName);

    // Neighbor nodes
    const rels = data.relationships || [];
    for (const r of rels) {
      const neighborName = r.neighbor?.name || r.neighbor?.normalized_name || '';
      if (!neighborName || nodeSet.has(neighborName)) continue;
      nodeSet.add(neighborName);
      const label = r.neighbor_label || 'Company';
      nodes.push({
        name: neighborName, symbolSize: 26,
        itemStyle: { color: NODE_COLORS[label] || '#999' },
        label: { show: true, fontSize: 10 },
        category: this.getCategoryIndex(label),
      });
      links.push({
        source: r.direction === 'outgoing' ? centerName : neighborName,
        target: r.direction === 'outgoing' ? neighborName : centerName,
        label: { show: false },
        lineStyle: { color: '#ccc' },
      });
    }

    const categories = ['Company', 'Product', 'Resource', 'Industry', 'Technology', 'Event', 'Policy', 'Asset', 'Market']
      .map(n => ({ name: n }));

    this.chartOptions = {
      tooltip: { formatter: (p: any) => p.data?.name || '' },
      legend: { data: categories.map(c => c.name), bottom: 0, textStyle: { fontSize: 10 } },
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        data: nodes,
        links: links,
        categories: categories,
        force: { repulsion: 200, edgeLength: [80, 160], gravity: 0.1 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
        label: { position: 'bottom' },
        lineStyle: { curveness: 0.1 },
      }],
    };
  }

  private getCategoryIndex(label: string): number {
    const cats = ['Company', 'Product', 'Resource', 'Industry', 'Technology', 'Event', 'Policy', 'Asset', 'Market'];
    const idx = cats.indexOf(label);
    return idx >= 0 ? idx : 0;
  }

  onChartClick(event: any): void {
    if (event?.name && event.name !== this.selectedCompany) {
      this.searchText = event.name;
      this.search();
    }
  }

  exploreNeighbor(rel: any): void {
    const name = rel.neighbor?.normalized_name || rel.neighbor?.name;
    if (name) {
      this.searchText = name;
      this.search();
    }
  }
}

