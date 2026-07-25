import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SKIP_GLOBAL_ERROR_NOTIFICATION } from '../../../core/errors/error-notification.interceptor';
import { FeaturePlatformApiService } from './feature-platform-api.service';

describe('FeaturePlatformApiService', () => {
  let service: FeaturePlatformApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(FeaturePlatformApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('serializes run filters without empty parameters', () => {
    service.listRuns({ status: 'running', feature_version_id: 17, producer_service: '' }).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/api/v2/features/runs'));
    expect(request.request.params.get('status')).toBe('running');
    expect(request.request.params.get('feature_version_id')).toBe('17');
    expect(request.request.params.has('producer_service')).toBeFalse();
    request.flush({ items: [], total: 0, limit: 100, offset: 0 });
  });

  it('uses succeeded-only latest endpoint and comma separated security ids', () => {
    service.queryValues({ feature_code: 'platform.security.constant_one', security_ids: [1, 2] }, true).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/api/v2/features/values/numeric/latest'));
    expect(request.request.params.get('feature_code')).toBe('platform.security.constant_one');
    expect(request.request.params.get('security_ids')).toBe('1,2');
    request.flush({ items: [], total: 0, limit: 100, offset: 0 });
  });

  it('submits manual compute to Artemis without changing the request contract', () => {
    const body = {
      features: [{ code: 'platform.security.constant_one', version: 1 }],
      security_ids: [1],
      as_of_time: '2026-07-18T02:00:00.000Z',
      data_cutoff_time: '2026-07-18T01:00:00.000Z',
      market: 'zh_a', source_profile: 'home', trigger_type: 'manual' as const,
      parameters: {}, force: false,
    };
    service.compute(body).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/features/compute'));
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    expect(request.request.context.get(SKIP_GLOBAL_ERROR_NOTIFICATION)).toBeTrue();
    request.flush({ accepted: true, reused: false, run_id: 'run', status: 'queued', request_fingerprint: 'hash' });
  });

  it('loads manifest catalog from Artemis with explicit validation options', () => {
    service.getManifestCatalog('home', true).subscribe();
    const request = http.expectOne((req) => req.url.endsWith('/features/manifests/catalog'));
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('source_profile')).toBe('home');
    expect(request.request.params.get('check_entrypoints')).toBe('true');
    expect(request.request.context.get(SKIP_GLOBAL_ERROR_NOTIFICATION)).toBeTrue();
    request.flush({
      catalog_checksum: 'a'.repeat(64),
      loaded_at: '2026-07-25T00:00:00Z',
      source_profile: 'home',
      count: 0,
      items: [],
      warnings: [],
    });
  });

  it('keeps Registry preview and lifecycle transitions as separate writes', () => {
    service.previewRegistrySync({ source_profile: 'home' }).subscribe();
    const preview = http.expectOne((req) => req.url.endsWith('/features/registry/sync:preview'));
    expect(preview.request.body).toEqual({ source_profile: 'home' });
    preview.flush({
      catalog_checksum: 'a'.repeat(64),
      source_profile: 'home',
      changes: [],
      blocked: [],
      unchanged: [],
      warnings: [],
    });

    const transition = {
      expected_status: 'draft' as const,
      expected_manifest_checksum: 'b'.repeat(64),
    };
    service.publishVersion('financial.valuation.pe_ttm', 2, transition).subscribe();
    const publish = http.expectOne((req) => req.url.endsWith(
      '/definitions/financial.valuation.pe_ttm/versions/2:publish',
    ));
    expect(publish.request.body).toEqual(transition);
    publish.flush({ status: 'published', version: 2, event: {} });
  });
});
