import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { ECharts, EChartsOption } from 'echarts';
import { NgxEchartsModule } from 'ngx-echarts';
import { Subject, combineLatest, map, of, switchMap, takeUntil } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { FeatureGraphNode, FeatureLineage, FeatureLineageVersion } from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-lineage-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, RouterLink, NgxEchartsModule, NzButtonModule,
    NzEmptyModule, NzInputModule, NzSelectModule, NzSpinModule, FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar">
        <div>
          <div class="fp-eyebrow">Governed dependency graph</div>
          <h2 style="margin:3px 0 0">Lineage / <span class="fp-code">{{ lineage?.feature_code }}</span></h2>
        </div>
        <div class="fp-toolbar-fields">
          <div class="fp-field"><label>Feature code</label><input nz-input [(ngModel)]="featureCodeInput" (keyup.enter)="openLineage()" placeholder="financial.pe_ttm" style="width:220px" /></div>
          <button nz-button nzType="primary" (click)="openLineage()">Open</button>
          @if (lineage) {
          <div class="fp-field"><label>Version</label><nz-select [(ngModel)]="selectedVersionId" (ngModelChange)="selectVersion($event)" style="width:150px">
            @for (version of lineage.versions; track version.feature_version_id) {
              <nz-option [nzValue]="version.feature_version_id" [nzLabel]="'v' + version.version_number + ' / ID ' + version.feature_version_id"></nz-option>
            }
          </nz-select></div>
          <div class="fp-field"><label>Find node</label><input nz-input [(ngModel)]="searchText" (keyup.enter)="locateNode()" placeholder="code, field, or fv:ID" style="width:220px" /></div>
          <button nz-button (click)="locateNode()">Locate</button>
          <button nz-button (click)="resetGraph()">Refocus</button>
          <a nz-button [routerLink]="['../../definitions', lineage.feature_code]">Definition</a>
          }
        </div>
      </section>
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      @if (searchMessage) { <div class="fp-alert">{{ searchMessage }}</div> }
      <nz-spin [nzSpinning]="loading">
        @if (selected(); as version) {
          <section class="fp-panel graph-shell">
            <div class="fp-panel-title">
              <div><div class="fp-eyebrow">Interactive DAG</div><h3>v{{ version.version_number }} dependency neighborhood</h3></div>
              <span class="fp-muted">{{ version.nodes.length }} nodes / {{ version.edges.length }} directed edges</span>
            </div>
            <div echarts [options]="graphOptions" (chartInit)="onChartInit($event)" class="lineage-chart"></div>
            <div class="legend">
              <span><i class="root"></i>selected root</span><span><i class="feature"></i>feature version</span><span><i class="field"></i>data field</span>
            </div>
          </section>

          <section class="fp-panel">
            <div class="fp-panel-title"><h3>Graph table fallback</h3><span class="fp-muted">Stable IDs preserve evidence outside the chart.</span></div>
            <div class="fallback-grid">
              <div>
                <h4>Nodes</h4>
                <div class="table-scroll"><table><thead><tr><th>ID</th><th>Type</th><th>Label</th><th>Status</th></tr></thead><tbody>
                  @for (node of version.nodes; track node.id) {
                    <tr><td class="fp-code">{{ node.id }}</td><td>{{ node.node_type }}</td><td>{{ node.label }}</td><td><app-feature-status-badge [status]="node.root ? 'root' : (node.status || 'unknown')"></app-feature-status-badge></td></tr>
                  }
                </tbody></table></div>
              </div>
              <div>
                <h4>Edges</h4>
                <div class="table-scroll"><table><thead><tr><th>Kind</th><th>Source</th><th>Target</th></tr></thead><tbody>
                  @for (edge of version.edges; track edge.id) {
                    <tr><td>{{ edge.kind }}</td><td class="fp-code">{{ edge.source }}</td><td class="fp-code">{{ edge.target }}</td></tr>
                  }
                </tbody></table></div>
              </div>
            </div>
          </section>
        } @else if (!loading) {
          <nz-empty [nzNotFoundContent]="lineage ? 'No lineage versions are available.' : 'Enter a Feature Code to open its lineage DAG.'"></nz-empty>
        }
      </nz-spin>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .graph-shell { background:linear-gradient(145deg,#fffdf7,#eef4f1); }
    .lineage-chart { width:100%;height:560px; }
    .legend { display:flex;gap:20px;justify-content:center;color:#676f73;font-size:12px; }
    .legend i { display:inline-block;width:10px;height:10px;margin-right:6px;border-radius:50%; }
    .legend .root { background:#d75f22; }.legend .feature { background:#426f7d; }.legend .field { background:#b0913e; }
    .fallback-grid { display:grid;grid-template-columns:1fr 1fr;gap:20px; }
    .table-scroll { overflow:auto;max-height:360px; }
    table { width:100%;border-collapse:collapse;font-size:12px; }
    th,td { padding:8px;border-bottom:1px solid #e2ded5;text-align:left; }
    @media(max-width:850px){.fallback-grid{grid-template-columns:1fr}.lineage-chart{height:430px}}
  `],
})
export class LineagePageComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(FeaturePlatformApiService);
  private readonly destroy$ = new Subject<void>();
  private chart?: ECharts;

  lineage: FeatureLineage | null = null;
  selectedVersionId: number | null = null;
  loading = true;
  error: ReturnType<typeof featurePlatformError> | null = null;
  graphOptions: EChartsOption = {};
  featureCodeInput = '';
  searchText = '';
  searchMessage = '';

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.route.queryParamMap]).pipe(
      switchMap(([params, query]) => {
        this.loading = true;
        this.error = null;
        const requested = Number(query.get('version_id')) || null;
        const featureCode = params.get('featureCode') || '';
        this.featureCodeInput = featureCode;
        if (!featureCode) {
          return of({ lineage: null, requested });
        }
        return this.api.getLineage(featureCode).pipe(map((lineage) => ({ lineage, requested })));
      }),
      takeUntil(this.destroy$),
    ).subscribe({
      next: ({ lineage, requested }) => {
        this.lineage = lineage;
        this.selectedVersionId = lineage?.versions.some((item) => item.feature_version_id === requested)
          ? requested : lineage?.versions[0]?.feature_version_id ?? null;
        this.buildGraph();
        this.loading = false;
      },
      error: (error) => { this.error = featurePlatformError(error); this.loading = false; },
    });
  }

  selected(): FeatureLineageVersion | undefined {
    return this.lineage?.versions.find((item) => item.feature_version_id === this.selectedVersionId);
  }

  openLineage(): void {
    const featureCode = this.featureCodeInput.trim();
    if (!featureCode) {
      this.searchMessage = 'Enter a Feature Code.';
      return;
    }
    this.searchMessage = '';
    this.router.navigate(['/workbench/features/lineage', featureCode]);
  }

  selectVersion(versionId: number): void {
    this.router.navigate([], { relativeTo: this.route, queryParams: { version_id: versionId }, replaceUrl: true });
  }

  onChartInit(chart: ECharts): void { this.chart = chart; }

  locateNode(): void {
    const needle = this.searchText.trim().toLowerCase();
    const nodes = this.selected()?.nodes || [];
    const index = nodes.findIndex((node) => node.id.toLowerCase() === needle || node.label.toLowerCase().includes(needle));
    if (!needle || index < 0) {
      this.searchMessage = needle ? `No graph node matches "${this.searchText.trim()}".` : 'Enter a node ID, feature code, or field name.';
      return;
    }
    this.searchMessage = `Focused ${nodes[index].id}: ${nodes[index].label}`;
    this.chart?.dispatchAction({ type: 'downplay', seriesIndex: 0 });
    this.chart?.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: index });
    this.chart?.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: index });
  }

  resetGraph(): void {
    this.searchMessage = '';
    this.searchText = '';
    this.chart?.dispatchAction({ type: 'restore' });
    this.buildGraph();
  }

  private buildGraph(): void {
    const version = this.selected();
    if (!version) { this.graphOptions = {}; return; }
    const category = (node: FeatureGraphNode) => node.root ? 0 : node.node_type === 'data_field' ? 2 : 1;
    this.graphOptions = {
      animationDurationUpdate: 450,
      tooltip: {
        formatter: (params: unknown) => {
          const value = params as { dataType?: string; data?: FeatureGraphNode };
          if (value.dataType !== 'node' || !value.data) return '';
          return `<strong>${value.data.label}</strong><br>${value.data.id}<br>${value.data.status || value.data.node_type}`;
        },
      },
      legend: [{ data: ['Selected root', 'Feature version', 'Data field'], top: 4 }],
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        force: { repulsion: 520, edgeLength: [110, 210], gravity: 0.08 },
        categories: [
          { name: 'Selected root', itemStyle: { color: '#d75f22' } },
          { name: 'Feature version', itemStyle: { color: '#426f7d' } },
          { name: 'Data field', itemStyle: { color: '#b0913e' } },
        ],
        data: version.nodes.map((node) => ({
          ...node, name: node.id, category: category(node), symbolSize: node.root ? 64 : node.node_type === 'data_field' ? 38 : 48,
          label: { show: true, formatter: node.label, position: 'bottom', distance: 7, color: '#2d383e', fontSize: 11 },
          itemStyle: node.status === 'deprecated' ? { color: '#8a8176', borderColor: '#534f49', borderWidth: 2 } : undefined,
        })),
        links: version.edges.map((edge) => ({
          ...edge, lineStyle: { color: edge.kind === 'data_field' ? '#b0913e' : '#718b91', width: 1.5, curveness: 0.08 },
        })),
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      }],
    };
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
