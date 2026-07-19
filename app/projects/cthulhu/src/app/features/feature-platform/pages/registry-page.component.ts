import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTableModule } from 'ng-zorro-antd/table';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureRegistryRow } from '../models/feature-platform.models';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-registry-page',
  standalone: true,
  imports: [
    CommonModule, FormsModule, RouterLink, NzButtonModule, NzEmptyModule, NzIconModule,
    NzInputModule, NzSelectModule, NzSpinModule, NzTableModule, FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar">
        <div class="fp-toolbar-fields">
          <div class="fp-field">
            <label>Search</label>
            <input nz-input [(ngModel)]="search" placeholder="code or display name" style="width:240px" />
          </div>
          <div class="fp-field">
            <label>Status</label>
            <nz-select [(ngModel)]="status" nzAllowClear nzPlaceHolder="All" style="width:130px">
              <nz-option nzValue="draft" nzLabel="Draft"></nz-option>
              <nz-option nzValue="active" nzLabel="Active"></nz-option>
              <nz-option nzValue="deprecated" nzLabel="Deprecated"></nz-option>
              <nz-option nzValue="retired" nzLabel="Retired"></nz-option>
            </nz-select>
          </div>
          <div class="fp-field">
            <label>Category</label>
            <input nz-input [(ngModel)]="category" placeholder="exact category" style="width:145px" />
          </div>
          <div class="fp-field">
            <label>Owner</label>
            <input nz-input [(ngModel)]="owner" placeholder="exact owner" style="width:135px" />
          </div>
          <div class="fp-field">
            <label>Source profile</label>
            <input nz-input [(ngModel)]="sourceProfile" style="width:130px" />
          </div>
        </div>
        <button nz-button nzType="primary" (click)="reload()" [nzLoading]="store.registryLoading()">
          <span nz-icon nzType="reload"></span> Refresh registry
        </button>
      </section>

      @if (store.registryError()) {
        <div class="fp-alert danger"><strong>Registry unavailable.</strong> {{ store.registryError() }}</div>
      }

      <section class="fp-panel">
        <div class="fp-panel-title">
          <div><div class="fp-eyebrow">Governed definitions</div><h2>Registry</h2></div>
          <div class="fp-muted">{{ filteredRows().length }} / {{ store.registryRows().length }} definitions · profile <span class="fp-code">{{ store.sourceProfile() }}</span></div>
        </div>
        <nz-spin [nzSpinning]="store.registryLoading()" nzTip="Resolving versions and availability...">
          @if (!store.registryLoading() && filteredRows().length === 0) {
            <nz-empty nzNotFoundContent="No Feature definitions match this view."></nz-empty>
          } @else {
            <nz-table #registryTable [nzData]="filteredRows()" nzSize="small" [nzPageSize]="20" [nzShowSizeChanger]="true">
              <thead><tr>
                <th>Feature</th><th>Semantics</th><th>Published</th><th>Readiness</th><th>Data</th><th>Materialization</th><th>Last success</th>
              </tr></thead>
              <tbody>
                @for (row of registryTable.data; track row.definition.feature_code) {
                  <tr>
                    <td>
                      <a class="fp-link fp-code" [routerLink]="['../definitions', row.definition.feature_code]">{{ row.definition.feature_code }}</a>
                      <div><strong>{{ row.definition.display_name }}</strong></div>
                      <div class="fp-muted">{{ row.definition.owner }} · {{ row.definition.category || 'uncategorized' }}</div>
                    </td>
                    <td>
                      <div class="fp-chip-list">
                        <span class="fp-chip">{{ row.definition.kind }}</span><span class="fp-chip">{{ row.definition.entity_type }}</span><span class="fp-chip">{{ row.definition.value_type }}</span>
                      </div>
                    </td>
                    <td>
                      @if (row.latest_published_version) {
                        <a class="fp-link" [routerLink]="['../definitions', row.definition.feature_code]">v{{ row.latest_published_version.version_number }}</a>
                      } @else { <app-feature-status-badge status="missing"></app-feature-status-badge> }
                    </td>
                    <td><app-feature-status-badge [status]="row.availability.execution_readiness"></app-feature-status-badge></td>
                    <td><app-feature-status-badge [status]="row.availability.data_status"></app-feature-status-badge></td>
                    <td><app-feature-status-badge [status]="row.availability.materialization_status"></app-feature-status-badge></td>
                    <td>
                      @if (row.availability.latest_succeeded_run; as run) {
                        <a class="fp-link fp-code" [routerLink]="['../runs', run.run_id]">{{ run.finished_at || run.updated_at | date:'yyyy-MM-dd HH:mm' }}</a>
                      } @else { <span class="fp-muted">Never</span> }
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          }
        </nz-spin>
      </section>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
})
export class RegistryPageComponent implements OnInit {
  readonly store = inject(FeaturePlatformStore);
  search = '';
  status: string | null = null;
  category = '';
  owner = '';
  sourceProfile = this.store.sourceProfile();

  ngOnInit(): void { this.store.loadRegistry(); }

  reload(): void {
    this.store.setSourceProfile(this.sourceProfile);
    this.store.loadRegistry({ status: this.status || undefined, category: this.category.trim(), owner: this.owner.trim() });
  }

  filteredRows(): FeatureRegistryRow[] {
    const query = this.search.trim().toLowerCase();
    return this.store.registryRows().filter((row) => !query ||
      row.definition.feature_code.toLowerCase().includes(query) ||
      row.definition.display_name.toLowerCase().includes(query));
  }
}
