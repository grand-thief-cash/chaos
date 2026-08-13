import {provideHttpClient} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import {TestBed} from '@angular/core/testing';
import {AtlasApiService} from './atlas-api.service';

describe('AtlasApiService', () => {
  let service: AtlasApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AtlasApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('submits explicit report types for discovery sampling', () => {
    service.createSampleRun({
      sample_size: 120,
      report_types: ['stock', 'industry'],
      published_from: null,
      published_to: null,
      force: false,
    }).subscribe();
    const request = http.expectOne(req =>
      req.url.endsWith('/api/v1/atlas-kg/sample-runs'),
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      sample_size: 120,
      report_types: ['stock', 'industry'],
      published_from: null,
      published_to: null,
      force: false,
    });
    request.flush({sample_run_id: 'run-1', accepted: true, cronjob_run_id: null});
  });

  it('keeps review and semantic publication as separate writes', () => {
    const payload = {
      run_id: 'run-1',
      status: 'PROPOSED',
      report_type_assessments: [],
      predicate_proposals: [],
      concept_proposals: [],
    };
    service.reviewDiscovery('run-1', payload).subscribe();
    const review = http.expectOne(req =>
      req.url.endsWith('/discovery-runs/run-1/review'),
    );
    expect(review.request.method).toBe('PUT');
    expect(review.request.body).toBe(payload);
    review.flush({...payload, status: 'REVIEWED'});

    service.publishSemantic('run-1', 'atlas-semantic-v0002').subscribe();
    const publish = http.expectOne(req =>
      req.url.endsWith('/semantic-versions:publish'),
    );
    expect(publish.request.method).toBe('POST');
    expect(publish.request.body).toEqual({
      discovery_run_id: 'run-1',
      version: 'atlas-semantic-v0002',
    });
    publish.flush({yaml_path: 'config/semantic/atlas-semantic-v0002.yaml'});
  });

  it('submits a company review through the Atlas read-only agent', () => {
    service.companyReview('Company A').subscribe();
    const request = http.expectOne(req =>
      req.url.endsWith('/api/v1/atlas-kg/company-reviews'),
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({company_name: 'Company A'});
    request.flush({answer: 'review', citations: [], tool_trace: []});
  });

  it('saves entity review decisions through PhoenixA', () => {
    const entity = {
      id: 'af99c598-e49b-48a9-b0c6-30c61ae362e4',
      canonical_name: 'Company A',
      normalized_name: 'companya',
      entity_type: 'COMPANY',
      country_code: 'CN',
      resolution_state: 'RESOLVED_KNOWLEDGE_ENTITY',
      attributes: {},
    };
    service.saveEntities([entity]).subscribe();
    const request = http.expectOne(req =>
      req.url.endsWith('/api/v1/atlas-kg/entities:batch'),
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual([entity]);
    request.flush({count: 1});
  });

  it('keeps crosswalk review and publication as separate writes', () => {
    const payload = {run_id: 'run-2', status: 'READY_FOR_REVIEW'};
    service.reviewCrosswalk('run-2', payload).subscribe();
    const review = http.expectOne(req =>
      req.url.endsWith('/crosswalk-runs/run-2/review'),
    );
    expect(review.request.method).toBe('PUT');
    expect(review.request.body).toBe(payload);
    review.flush({...payload, status: 'REVIEWED'});

    service.publishCrosswalk('run-2', 'atlas-semantic-v0003').subscribe();
    const publish = http.expectOne(req =>
      req.url.endsWith('/crosswalk-semantic-versions:publish'),
    );
    expect(publish.request.body).toEqual({
      crosswalk_run_id: 'run-2',
      version: 'atlas-semantic-v0003',
    });
    publish.flush({yaml_path: 'atlas-semantic-v0003.yaml'});
  });

  it('can run every configured required crosswalk', () => {
    service.runRequiredCrosswalks().subscribe();
    const request = http.expectOne(req =>
      req.url.endsWith('/crosswalk-runs:required'),
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush({count: 3, runs: []});
  });

  it('starts a governed extraction batch through Atlas', () => {
    service.startExtractionBatch({
      published_from: '2026-01-01',
      published_to: null,
      report_types: null,
      limit: 100,
      force: false,
    }).subscribe();
    const request = http.expectOne(req =>
      req.url.endsWith('/api/v1/atlas-kg/extraction-batches'),
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body.report_types).toBeNull();
    expect(request.request.body.force).toBeFalse();
    request.flush({count: 0, runs: []});
  });

  it('falls back to empty graph stats when the graph endpoint is unavailable', () => {
    let stats: {entities: number; claims: number} | undefined;
    service.graphStats().subscribe(value => (stats = value));
    const request = http.expectOne(req =>
      req.url.endsWith('/api/v1/atlas-graph/stats'),
    );
    // The graph service may be undeployed (404); the call must not surface as
    // a global error and must resolve to zeros so overview cards still render.
    request.flush('404 page not found', {status: 404, statusText: 'Not Found'});
    expect(stats).toEqual({entities: 0, claims: 0});
  });
});
