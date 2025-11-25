import {TestBed} from '@angular/core/testing';
import {ErrorNotificationService} from './error-notification.service';
import {HttpErrorResponse} from '@angular/common/http';

function mockHttpError(status: number, url: string, body?: any) {
  return new HttpErrorResponse({ status, url, statusText: 'X', error: body });
}

describe('ErrorNotificationService', () => {
  let service: ErrorNotificationService;
  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ErrorNotificationService);
  });

  it('adds errors and enforces max size', () => {
    for (let i = 0; i < 7; i++) {
      service.addHttpError(mockHttpError(500, '/api/' + i));
    }
    service.records$.subscribe((list: any[]) => {
      expect(list.length).toBeLessThanOrEqual(5);
    });
  });

  it('dedupes identical errors within window', () => {
    service.addHttpError(mockHttpError(404, '/same'));
    const firstTs = service.getRecordsSnapshot()[0].timestamp;
    service.addHttpError(mockHttpError(404, '/same'));
    const records = service.getRecordsSnapshot();
    expect(records.length).toBe(1);
    expect(records[0].timestamp).toBeGreaterThanOrEqual(firstTs);
  });

  it('dismiss removes item', () => {
    service.addHttpError(mockHttpError(500, '/x'));
    const id = service.getRecordsSnapshot()[0].id;
    service.dismiss(id);
    expect(service.getRecordsSnapshot().length).toBe(0);
  });
});
