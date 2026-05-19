import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { BiApiService } from './bi-api.service';
import { environment } from '../../../../environments/environment';

describe('BiApiService', () => {
  let service: BiApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        BiApiService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(BiApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should call dashboard endpoint with required query params', () => {
    service.getCompanyDashboard('000001', '2026-05-19').subscribe();

    const req = httpMock.expectOne(r =>
      r.method === 'GET' &&
      r.url === `${environment.artemisApiBase}/bi/financial/company/000001/dashboard`
    );
    expect(req.request.params.get('as_of_date')).toBe('2026-05-19');
    expect(req.request.params.get('market')).toBe('zh_a');
    expect(req.request.params.get('source')).toBe('amazing_data');
    req.flush({});
  });

  it('should call dupont endpoint with required query params', () => {
    service.getCompanyDupont('000001', '2026-05-19').subscribe();

    const req = httpMock.expectOne(r =>
      r.method === 'GET' &&
      r.url === `${environment.artemisApiBase}/bi/financial/company/000001/dupont`
    );
    expect(req.request.params.get('as_of_date')).toBe('2026-05-19');
    expect(req.request.params.get('market')).toBe('zh_a');
    expect(req.request.params.get('source')).toBe('amazing_data');
    req.flush({});
  });

  it('should call quality endpoint with required query params', () => {
    service.getCompanyQuality('000001', '2026-05-19').subscribe();

    const req = httpMock.expectOne(r =>
      r.method === 'GET' &&
      r.url === `${environment.artemisApiBase}/bi/financial/company/000001/quality`
    );
    expect(req.request.params.get('as_of_date')).toBe('2026-05-19');
    expect(req.request.params.get('market')).toBe('zh_a');
    expect(req.request.params.get('source')).toBe('amazing_data');
    req.flush({});
  });

  it('should call metric definition endpoint', () => {
    service.getMetricDefinitions().subscribe();

    const req = httpMock.expectOne(`${environment.artemisApiBase}/bi/meta/metrics`);
    expect(req.request.method).toBe('GET');
    req.flush({ version: 'v1', metrics: [] });
  });

  it('should call securities search endpoint', () => {
    service.searchSecurities('maotai').subscribe();

    const req = httpMock.expectOne(r =>
      r.method === 'GET' &&
      r.url === `${environment.artemisApiBase}/bi/search/securities`
    );
    expect(req.request.params.get('query')).toBe('maotai');
    expect(req.request.params.get('limit')).toBe('20');
    req.flush({ query: 'maotai', market: 'zh_a', total: 0, items: [] });
  });

  it('should call peer comparison endpoint', () => {
    service.getPeerComparison({ symbols: ['000001', '600519'], as_of_date: '2026-05-19', metrics: ['revenue_total'] }).subscribe();

    const req = httpMock.expectOne(`${environment.artemisApiBase}/bi/financial/peer-comparison`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.symbols).toEqual(['000001', '600519']);
    req.flush({ as_of_date: '2026-05-19', market: 'zh_a', industry_code: '', requested_metrics: ['revenue_total'], rows: [] });
  });

  it('should call structured insight endpoint', () => {
    service.getCompanyInsight('000001', '2026-05-19').subscribe();

    const req = httpMock.expectOne(r =>
      r.method === 'GET' &&
      r.url === `${environment.artemisApiBase}/bi/financial/company/000001/insight`
    );
    expect(req.request.params.get('as_of_date')).toBe('2026-05-19');
    expect(req.request.params.get('market')).toBe('zh_a');
    expect(req.request.params.get('source')).toBe('amazing_data');
    req.flush({ symbol: '000001', as_of_date: '2026-05-19', latest_period: '2025-12-31', company: {}, headline: '', structured_highlights: [], anomalies: [], trend_summary: [], source_notes: [] });
  });
});



