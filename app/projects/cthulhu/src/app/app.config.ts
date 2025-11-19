import {ApplicationConfig} from '@angular/core';
import {provideRouter} from '@angular/router';
import {provideAnimations} from '@angular/platform-browser/animations';
import {provideHttpClient, withInterceptors} from '@angular/common/http';
import {NZ_ICONS} from 'ng-zorro-antd/icon'; // 使用旧版 token 方式注册图标
import {routes} from './routing/app.routes';
import {
  LaptopOutline,
  MenuFoldOutline,
  MenuUnfoldOutline,
  NotificationOutline,
  UserOutline
} from '@ant-design/icons-angular/icons';
import {errorNotificationInterceptor} from './core/errors/error-notification.interceptor';
import {ERROR_NOTIFICATIONS_OPTIONS, STATUS_MESSAGE_MAP} from './core/errors/error-notification.model';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideAnimations(), // 启用动画
    provideHttpClient(withInterceptors([errorNotificationInterceptor])), // HttpClient + 全局错误拦截
    {provide: NZ_ICONS, useValue: [UserOutline, LaptopOutline, NotificationOutline, MenuFoldOutline, MenuUnfoldOutline]},
    {provide: STATUS_MESSAGE_MAP, useValue: {/* 可自定义覆盖 */}},
    {provide: ERROR_NOTIFICATIONS_OPTIONS, useValue: {maxItems: 5, dedupeWindowMs: 10000, autoDismissMs: 0}}
  ]
};
