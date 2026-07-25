import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTableModule } from 'ng-zorro-antd/table';
import {
  ManifestCatalogItem,
  ManifestCatalogResponse,
  ManifestValidationResponse,
  RegistrySyncPreviewResponse,
} from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-manifest-catalog-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzButtonModule,
    NzCheckboxModule,
    NzEmptyModule,
    NzInputModule,
    NzModalModule,
    NzSpinModule,
    NzTableModule,
    FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar">
        <div class="fp-toolbar-fields">
          <div class="fp-field">
            <label>Source profile</label>
            <input nz-input [(ngModel)]="sourceProfile" style="width:150px" />
          </div>
          <div class="fp-field">
            <label>Filter</label>
            <input nz-input [(ngModel)]="filter" placeholder="path or Feature identity" style="width:260px" />
          </div>
        </div>
        <div class="fp-actions">
          <button nz-button (click)="validate()" [nzLoading]="validating">Validate {{ selectedPaths.size ? 'selected' : 'all' }}</button>
          <button nz-button (click)="previewSync()" [nzLoading]="previewing">Preview sync</button>
          <button nz-button nzType="primary" (click)="load()" [nzLoading]="loading">Inspect catalog</button>
        </div>
      </section>

      <div class="fp-alert">
        <strong>Read-only governance view.</strong>
        Manifests remain Git-owned. This page validates local files and compares them with PhoenixA Registry without changing either source.
      </div>
      @if (error) {
        <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div>
      }
      @for (warning of catalog?.warnings || []; track warning) {
        <div class="fp-alert"><strong>Registry warning.</strong> {{ warning }}</div>
      }
      @if (validation; as result) {
        <div class="fp-alert" [class.danger]="!result.valid">
          <strong>{{ result.valid ? 'Validation passed.' : 'Validation failed.' }}</strong>
          {{ result.count }} manifest(s) checked.
        </div>
      }

      @if (syncPreview; as preview) {
        <section class="fp-panel">
          <div class="fp-panel-title">
            <div>
              <div class="fp-eyebrow">Optimistic registry change set</div>
              <h3>Sync Preview</h3>
            </div>
            <div class="fp-actions">
              <span class="fp-code" [title]="preview.catalog_checksum">{{ shortChecksum(preview.catalog_checksum) }}</span>
              <button nz-button nzType="primary" [disabled]="preview.blocked.length > 0 || actionableChanges(preview) === 0" (click)="syncModalVisible = true">
                Sync {{ actionableChanges(preview) }} change(s)
              </button>
            </div>
          </div>
          @if (preview.blocked.length) {
            <div class="fp-alert danger"><strong>Sync blocked.</strong> Resolve all blocked entries before applying this change set.</div>
          }
          <nz-table #previewTable [nzData]="preview.changes" nzSize="small" [nzShowPagination]="false">
            <thead><tr><th>Manifest</th><th>Action</th><th>Current</th><th>Changed fields</th><th>Evidence</th></tr></thead>
            <tbody>
              @for (change of previewTable.data; track change.identity) {
                <tr>
                  <td class="fp-code">{{ change.identity }}</td>
                  <td><app-feature-status-badge [status]="change.action"></app-feature-status-badge></td>
                  <td>{{ change.current_status || 'not registered' }}</td>
                  <td><div class="fp-chip-list">@for (field of change.changed_fields; track field) { <span class="fp-chip">{{ field }}</span> }</div></td>
                  <td>{{ change.message || 'Ready to apply.' }}</td>
                </tr>
              }
            </tbody>
          </nz-table>
        </section>
      }

      <section class="fp-panel">
        <div class="fp-panel-title">
          <div>
            <div class="fp-eyebrow">Git → Catalog → Registry</div>
            <h2>Manifest Catalog</h2>
          </div>
          @if (catalog; as data) {
            <div class="catalog-summary">
              <span>{{ validCount(data.items) }} valid / {{ data.count }} files</span>
              <span class="fp-code" [title]="data.catalog_checksum">catalog {{ shortChecksum(data.catalog_checksum) }}</span>
              <span>{{ data.loaded_at | date:'medium' }}</span>
            </div>
          }
        </div>

        <nz-spin [nzSpinning]="loading" nzTip="Validating manifests and comparing Registry...">
          @if (!loading && filteredItems().length === 0) {
            <nz-empty nzNotFoundContent="No manifests match this view."></nz-empty>
          } @else {
            <nz-table #catalogTable [nzData]="filteredItems()" nzSize="small" [nzPageSize]="20">
              <thead>
                <tr>
                  <th nzWidth="42px">
                    <label nz-checkbox [ngModel]="allVisibleSelected()" (ngModelChange)="selectAllVisible($event)"></label>
                  </th>
                  <th>Manifest</th>
                  <th>Validation</th>
                  <th>Plugin</th>
                  <th>Registry</th>
                  <th>Checksums</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                @for (item of catalogTable.data; track item.path) {
                  <tr>
                    <td><label nz-checkbox [ngModel]="selectedPaths.has(item.path)" (ngModelChange)="select(item.path, $event)"></label></td>
                    <td>
                      <div class="fp-code">{{ item.identity || 'identity unavailable' }}</div>
                      <div class="path">{{ item.path }}</div>
                    </td>
                    <td><app-feature-status-badge [status]="item.validation_status"></app-feature-status-badge></td>
                    <td><app-feature-status-badge [status]="item.plugin_status"></app-feature-status-badge></td>
                    <td>
                      <app-feature-status-badge [status]="item.registry_status"></app-feature-status-badge>
                      <div class="fp-muted">{{ item.registry_action }}</div>
                    </td>
                    <td>
                      <div class="checksum" [title]="item.manifest_checksum || ''">manifest {{ shortChecksum(item.manifest_checksum) }}</div>
                      <div class="checksum" [title]="item.registry_checksum || ''">registry {{ shortChecksum(item.registry_checksum) }}</div>
                    </td>
                    <td>
                      @if (item.changed_fields.length) {
                        <div class="fp-chip-list">
                          @for (field of item.changed_fields; track field) { <span class="fp-chip">{{ field }}</span> }
                        </div>
                      }
                      @for (entry of item.errors; track entry.code + entry.message) {
                        <div class="catalog-error"><span class="fp-code">{{ entry.code }}</span> {{ entry.message }}</div>
                      }
                      @if (!item.changed_fields.length && !item.errors.length) {
                        <span class="fp-muted">No drift detected.</span>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          }
        </nz-spin>
      </section>

      <nz-modal
        [(nzVisible)]="syncModalVisible"
        nzTitle="Confirm Registry synchronization"
        [nzOkLoading]="syncing"
        nzOkText="Apply change set"
        (nzOnCancel)="syncModalVisible = false"
        (nzOnOk)="syncRegistry()">
        <ng-container *nzModalContent>
          <div class="fp-alert">
            The catalog checksum is locked to <span class="fp-code">{{ shortChecksum(syncPreview?.catalog_checksum) }}</span>.
            A changed catalog will be rejected with 409 and must be previewed again.
          </div>
        </ng-container>
      </nz-modal>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .catalog-summary { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px 16px; color:var(--fp-muted); font-size:12px; }
    .path { max-width:360px; margin-top:4px; overflow-wrap:anywhere; color:var(--fp-muted); font-size:12px; }
    .checksum { white-space:nowrap; color:var(--fp-muted); font:11px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .catalog-error { max-width:440px; margin-top:5px; padding:6px 8px; border-left:3px solid #bd4b35; background:#fff1ed; overflow-wrap:anywhere; font-size:12px; }
    @media(max-width:800px){.catalog-summary{justify-content:flex-start}}
  `],
})
export class ManifestCatalogPageComponent implements OnInit {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly store = inject(FeaturePlatformStore);

  sourceProfile = this.store.sourceProfile();
  filter = '';
  catalog: ManifestCatalogResponse | null = null;
  validation: ManifestValidationResponse | null = null;
  syncPreview: RegistrySyncPreviewResponse | null = null;
  selectedPaths = new Set<string>();
  loading = false;
  validating = false;
  previewing = false;
  syncing = false;
  syncModalVisible = false;
  error: ReturnType<typeof featurePlatformError> | null = null;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const profile = this.sourceProfile.trim();
    if (!profile) {
      this.error = { code: 'SOURCE_PROFILE_REQUIRED', message: 'Source profile is required.' };
      return;
    }
    this.loading = true;
    this.error = null;
    this.store.setSourceProfile(profile);
    this.api.getManifestCatalog(profile).subscribe({
      next: (catalog) => {
        this.catalog = catalog;
        this.selectedPaths = new Set(
          [...this.selectedPaths].filter((path) => catalog.items.some((item) => item.path === path)),
        );
        this.loading = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.loading = false;
      },
    });
  }

  validate(): void {
    this.validating = true;
    this.validation = null;
    this.error = null;
    this.api.validateManifests(this.selection()).subscribe({
      next: (validation) => {
        this.validation = validation;
        this.validating = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.validating = false;
      },
    });
  }

  previewSync(): void {
    this.previewing = true;
    this.syncPreview = null;
    this.error = null;
    this.api.previewRegistrySync(this.selection()).subscribe({
      next: (preview) => {
        this.syncPreview = preview;
        this.previewing = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.previewing = false;
      },
    });
  }

  syncRegistry(): void {
    if (!this.syncPreview) return;
    this.syncing = true;
    this.error = null;
    this.api.syncRegistry({
      ...this.selection(),
      expected_catalog_checksum: this.syncPreview.catalog_checksum,
    }).subscribe({
      next: () => {
        this.syncing = false;
        this.syncModalVisible = false;
        this.syncPreview = null;
        this.load();
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.syncing = false;
        this.syncModalVisible = false;
      },
    });
  }

  select(path: string, selected: boolean): void {
    const next = new Set(this.selectedPaths);
    selected ? next.add(path) : next.delete(path);
    this.selectedPaths = next;
  }

  selectAllVisible(selected: boolean): void {
    const next = new Set(this.selectedPaths);
    for (const item of this.filteredItems()) {
      selected ? next.add(item.path) : next.delete(item.path);
    }
    this.selectedPaths = next;
  }

  allVisibleSelected(): boolean {
    const visible = this.filteredItems();
    return visible.length > 0 && visible.every((item) => this.selectedPaths.has(item.path));
  }

  actionableChanges(preview: RegistrySyncPreviewResponse): number {
    return preview.changes.filter((change) => change.action !== 'unchanged' && change.action !== 'blocked').length;
  }

  private selection() {
    return {
      paths: [...this.selectedPaths],
      check_entrypoints: true,
      source_profile: this.sourceProfile.trim(),
    };
  }

  filteredItems(): ManifestCatalogItem[] {
    const query = this.filter.trim().toLowerCase();
    const items = this.catalog?.items || [];
    if (!query) return items;
    return items.filter((item) =>
      item.path.toLowerCase().includes(query)
      || (item.identity || '').toLowerCase().includes(query),
    );
  }

  validCount(items: ManifestCatalogItem[]): number {
    return items.filter((item) => item.validation_status === 'valid').length;
  }

  shortChecksum(value: string | undefined): string {
    return value ? value.slice(0, 10) : 'n/a';
  }
}
