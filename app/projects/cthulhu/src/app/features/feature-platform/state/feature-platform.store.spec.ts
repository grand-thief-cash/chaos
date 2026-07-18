import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeaturePlatformStore } from './feature-platform.store';

describe('FeaturePlatformStore', () => {
  let store: FeaturePlatformStore;
  let api: jasmine.SpyObj<FeaturePlatformApiService>;

  beforeEach(() => {
    localStorage.clear();
    api = jasmine.createSpyObj<FeaturePlatformApiService>('FeaturePlatformApiService', [
      'listDefinitions', 'getDefinition', 'getAvailability',
    ]);
    TestBed.configureTestingModule({ providers: [
      FeaturePlatformStore,
      { provide: FeaturePlatformApiService, useValue: api },
    ] });
    store = TestBed.inject(FeaturePlatformStore);
  });

  it('represents a successful empty registry without an error', fakeAsync(() => {
    api.listDefinitions.and.returnValue(of({ items: [], total: 0, limit: 500, offset: 0 }));
    store.loadRegistry();
    tick();
    expect(store.registryLoading()).toBeFalse();
    expect(store.registryError()).toBeNull();
    expect(store.registryRows()).toEqual([]);
  }));

  it('exposes a top-level registry loading error', fakeAsync(() => {
    api.listDefinitions.and.returnValue(throwError(() => new Error('registry offline')));
    store.loadRegistry();
    tick();
    expect(store.registryLoading()).toBeFalse();
    expect(store.registryError()).toBe('registry offline');
  }));

  it('keeps a definition visible with unknown availability when aggregation fails', fakeAsync(() => {
    const definition = {
      id: 1, feature_code: 'platform.security.constant_one', display_name: 'Constant One', description: '',
      kind: 'metric', entity_type: 'security', value_type: 'number', unit: 'scalar', category: 'platform',
      owner: 'platform', status: 'active', tags: [], created_at: '', updated_at: '',
    };
    const version = {
      id: 11, feature_id: 1, version_number: 1, status: 'published', frequency: 'on_demand',
      as_of_semantics: 'snapshot', missing_policy: 'explicit_missing', manifest_checksum: 'x',
      manifest_snapshot: {}, created_at: '', updated_at: '',
    };
    api.listDefinitions.and.returnValue(of({ items: [definition], total: 1, limit: 500, offset: 0 }));
    api.getDefinition.and.returnValue(of({ definition, versions: [{ version, implementations: [], dependencies: [] }] }));
    api.getAvailability.and.returnValue(throwError(() => new Error('coverage offline')));
    store.setSourceProfile('home');
    store.loadRegistry();
    tick();
    expect(store.registryRows().length).toBe(1);
    expect(store.registryRows()[0].published_versions.map((item) => item.version_number)).toEqual([1]);
    expect(store.registryRows()[0].latest_published_version?.version_number).toBe(1);
    expect(store.registryRows()[0].availability.execution_readiness).toBe('unknown');
    expect(store.registryRows()[0].availability.reasons).toContain('coverage offline');
  }));
});
