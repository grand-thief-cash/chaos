import {Inject, Injectable, Optional} from '@angular/core';
import {BehaviorSubject, Observable} from 'rxjs';
import {
  buildRecord,
  ERROR_NOTIFICATIONS_OPTIONS,
  ErrorNotificationOptions,
  ErrorRecord,
  STATUS_MESSAGE_MAP,
  StatusMessageMap
} from './error-notification.model';
import {HttpErrorResponse} from '@angular/common/http';

const DEFAULT_STATUS_MAP: StatusMessageMap = {
  400: '请求参数错误',
  401: '未授权，请重新登录',
  403: '没有访问权限',
  404: '资源未找到',
  409: '请求冲突',
  422: '请求数据无法处理',
  429: '请求过于频繁，请稍后再试',
  500: '服务器内部错误',
  502: '网关错误',
  503: '服务暂时不可用',
  504: '网关超时',
  default: '请求失败，请稍后重试',
  network: '网络异常，请检查网络连接'
};

const DEFAULT_OPTIONS: ErrorNotificationOptions = {
  maxItems: 5,
  dedupeWindowMs: 10_000,
  autoDismissMs: 0
};

@Injectable({ providedIn: 'root' })
export class ErrorNotificationService {
  private readonly recordsSubject = new BehaviorSubject<ErrorRecord[]>([]);
  readonly records$: Observable<ErrorRecord[]> = this.recordsSubject.asObservable();

  constructor(
    @Optional() @Inject(STATUS_MESSAGE_MAP) private statusMap: StatusMessageMap | null,
    @Optional() @Inject(ERROR_NOTIFICATIONS_OPTIONS) private opts: ErrorNotificationOptions | null
  ) {
    if (!this.statusMap) this.statusMap = DEFAULT_STATUS_MAP;
    if (!this.opts) this.opts = DEFAULT_OPTIONS;
  }

  getRecordsSnapshot(): ErrorRecord[] { return this.recordsSubject.getValue(); }

  addHttpError(err: HttpErrorResponse) {
    if ((err as any).name === 'AbortError') return; // ignore abort errors
    const record = buildRecord(err, this.statusMap!);
    this.addRecord(record);
  }

  private addRecord(record: ErrorRecord) {
    let current = this.recordsSubject.getValue();
    const now = Date.now();
    const existing = current.find(r => r.status === record.status && r.url === record.url && r.message === record.message && (now - r.timestamp) < this.opts!.dedupeWindowMs);
    if (existing) {
      existing.timestamp = now; // refresh timestamp
      this.recordsSubject.next([...current]);
      return;
    }
    current = [record, ...current];
    if (current.length > this.opts!.maxItems) {
      current = current.slice(0, this.opts!.maxItems);
    }
    this.recordsSubject.next(current);
    if (this.opts!.autoDismissMs > 0) {
      setTimeout(() => this.dismiss(record.id), this.opts!.autoDismissMs);
    }
  }

  dismiss(id: string) {
    const next = this.recordsSubject.getValue().filter(r => r.id !== id);
    this.recordsSubject.next(next);
  }

  clearAll() { this.recordsSubject.next([]); }
}
