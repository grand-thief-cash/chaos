import { computed, inject, Injectable, signal } from '@angular/core';
import { catchError, forkJoin, map, of, switchMap } from 'rxjs';
import {
  DefinitionFilters,
  FeatureDefinition,
  FeatureDefinitionDetail,
  FeatureRegistryRow,
} from '../models/feature-platform.models';
import { featurePlatformError, unknownAvailability } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';

const PROFILE_STORAGE_KEY = 'feature-platform-source-profile';

@Injectable({ providedIn: 'root' })
export class FeaturePlatformStore {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly _sourceProfile = signal(localStorage.getItem(PROFILE_STORAGE_KEY) || 'default');
  private readonly _registryRows = signal<FeatureRegistryRow[]>([]);
  private readonly _registryLoading = signal(false);
  private readonly _registryError = signal<string | null>(null);

  readonly sourceProfile = computed(() => this._sourceProfile());
  readonly registryRows = computed(() => this._registryRows());
  readonly registryLoading = computed(() => this._registryLoading());
  readonly registryError = computed(() => this._registryError());

  setSourceProfile(profile: string): void {
    const normalized = profile.trim() || 'default';
    this._sourceProfile.set(normalized);
    localStorage.setItem(PROFILE_STORAGE_KEY, normalized);
  }

  loadRegistry(filters: DefinitionFilters = {}): void {
    this._registryLoading.set(true);
    this._registryError.set(null);
    const sourceProfile = this._sourceProfile();
    this.api.listDefinitions({ ...filters, limit: filters.limit ?? 500 }).pipe(
      switchMap((response) => {
        if (!response.items.length) return of([] as FeatureRegistryRow[]);
        return forkJoin(response.items.map((definition) => this.enrich(definition, sourceProfile)));
      }),
    ).subscribe({
      next: (rows) => {
        this._registryRows.set(rows);
        this._registryLoading.set(false);
      },
      error: (error) => {
        this._registryRows.set([]);
        this._registryError.set(featurePlatformError(error).message);
        this._registryLoading.set(false);
      },
    });
  }

  private enrich(definition: FeatureDefinition, sourceProfile: string) {
    const fallbackDetail: FeatureDefinitionDetail = { definition, versions: [] };
    return forkJoin({
      detail: this.api.getDefinition(definition.feature_code).pipe(catchError(() => of(fallbackDetail))),
      availability: this.api.getAvailability(definition.feature_code, sourceProfile).pipe(
        catchError((error) => of(unknownAvailability(
          definition.feature_code,
          sourceProfile,
          featurePlatformError(error).message,
        ))),
      ),
    }).pipe(map(({ detail, availability }) => {
      const publishedVersions = [...detail.versions]
        .map((summary) => summary.version)
        .filter((version) => version.status === 'published')
        .sort((left, right) => right.version_number - left.version_number);
      return {
        definition,
        published_versions: publishedVersions,
        latest_published_version: publishedVersions[0],
        availability,
      };
    }));
  }
}
