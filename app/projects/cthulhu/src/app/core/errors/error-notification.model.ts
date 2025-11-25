import {InjectionToken} from '@angular/core';
import {HttpErrorResponse} from '@angular/common/http';

export type ErrorSeverity = 'info' | 'warning' | 'error';

export interface ErrorRecord {
  id: string; // unique id (timestamp + random)
  status: number;
  statusText: string;
  message: string; // user facing message (mapped)
  rawMessage?: string; // original backend message if available
  url?: string; // request URL
  timestamp: number; // epoch ms
  severity: ErrorSeverity;
}

export interface StatusMessageMap {
  [status: number]: string;
  default?: string;
  network?: string; // network error (status 0)
}

export interface ErrorNotificationOptions {
  maxItems: number; // maximum stored error records
  dedupeWindowMs: number; // window to treat duplicates as same
  autoDismissMs: number; // 0 => never auto dismiss
}

export const STATUS_MESSAGE_MAP = new InjectionToken<StatusMessageMap>('STATUS_MESSAGE_MAP');
export const ERROR_NOTIFICATIONS_OPTIONS = new InjectionToken<ErrorNotificationOptions>('ERROR_NOTIFICATIONS_OPTIONS');

export function deriveSeverity(status: number): ErrorSeverity {
  if (status >= 500) return 'error';
  if (status >= 400) return status === 404 ? 'info' : 'warning';
  return 'info';
}

export function buildRecord(err: HttpErrorResponse, map: StatusMessageMap): ErrorRecord {
  const now = Date.now();
  const id = `${now}-${Math.random().toString(36).slice(2,8)}`;
  let message: string;
  if (err.status === 0) {
    message = map.network || '网络异常，请检查网络连接';
  } else {
    message = map[err.status] || map.default || '请求失败，请稍后重试';
  }
  const raw = err.error;
  let rawMessage: string | undefined;
  if (raw) {
    if (typeof raw === 'string') {
      rawMessage = raw;
    } else if (typeof raw === 'object') {
      // 优先 message 字段，其次 error 字段
      if ('message' in raw && raw.message) {
        rawMessage = String(raw.message);
      } else if ('error' in raw && raw.error) {
        rawMessage = String((raw as any).error);
      } else {
        // 提取可读的简单键值对
        const keys = Object.keys(raw).filter(k => typeof (raw as any)[k] !== 'object');
        if (keys.length) {
          rawMessage = keys.map(k => `${k}: ${(raw as any)[k]}`).join(', ');
        } else {
          try { rawMessage = JSON.stringify(raw).substring(0, 300); } catch { /* ignore */ }
        }
      }
    }
  }
  return {
    id,
    status: err.status,
    statusText: err.statusText || '',
    message,
    rawMessage,
    url: err.url || undefined,
    timestamp: now,
    severity: deriveSeverity(err.status)
  };
}
