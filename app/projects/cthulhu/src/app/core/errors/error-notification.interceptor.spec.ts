import {TestBed} from '@angular/core/testing';
import {HttpClient, provideHttpClient, withInterceptors} from '@angular/common/http';
import {HttpTestingController, provideHttpClientTesting} from '@angular/common/http/testing';
import {errorNotificationInterceptor} from './error-notification.interceptor';
import {ErrorNotificationService} from './error-notification.service';

describe('errorNotificationInterceptor', () => {
  let http: HttpClient;
  let ctrl: HttpTestingController;
  let service: ErrorNotificationService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorNotificationInterceptor])),
        provideHttpClientTesting()
      ]
    });
    http = TestBed.inject(HttpClient);
    ctrl = TestBed.inject(HttpTestingController);
    service = TestBed.inject(ErrorNotificationService);
  });

  it('captures 404 error', () => {
    http.get('/missing').subscribe({
      next: () => fail('should have errored'),
      error: () => {
        const recs = service.getRecordsSnapshot();
        expect(recs.length).toBe(1);
        expect(recs[0].status).toBe(404);
      }
    });
    const req = ctrl.expectOne('/missing');
    req.flush({ message: 'Not found' }, { status: 404, statusText: 'Not Found' });
    ctrl.verify();
  });

  it('captures network error status 0', () => {
    http.get('/network').subscribe({ error: () => {
      const recs = service.getRecordsSnapshot();
      expect(recs[0].status).toBe(0);
    }});
    const req = ctrl.expectOne('/network');
    req.error(new ProgressEvent('error'));
    ctrl.verify();
  });
});
