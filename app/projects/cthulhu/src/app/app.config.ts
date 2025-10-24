import {ApplicationConfig} from '@angular/core';
import {provideRouter} from '@angular/router';
import {provideAnimations} from '@angular/platform-browser/animations';
import {provideHttpClient} from '@angular/common/http';
import {NZ_ICONS} from 'ng-zorro-antd/icon'; // 使用旧版 token 方式注册图标
import {routes} from './routing/app.routes';
import {
  LaptopOutline,
  MenuFoldOutline,
  MenuUnfoldOutline,
  NotificationOutline,
  UserOutline
} from '@ant-design/icons-angular/icons';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideAnimations(), // 启用动画
    provideHttpClient(), // HttpClient 支持（图标/其他 HTTP 功能需要）
    { provide: NZ_ICONS, useValue: [UserOutline, LaptopOutline, NotificationOutline, MenuFoldOutline, MenuUnfoldOutline] }
  ]
};
