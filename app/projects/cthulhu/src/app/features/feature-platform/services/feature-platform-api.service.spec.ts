import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
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
    request.flush({ accepted: true, reused: false, run_id: 'run', status: 'queued', request_fingerprint: 'hash' });
  });
});
