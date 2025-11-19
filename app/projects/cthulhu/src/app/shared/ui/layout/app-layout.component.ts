import {Component} from '@angular/core';
import {NzBreadCrumbComponent, NzBreadCrumbItemComponent} from "ng-zorro-antd/breadcrumb";
import {NzContentComponent, NzHeaderComponent, NzLayoutComponent, NzSiderComponent} from "ng-zorro-antd/layout";
import {NzMenuDirective, NzMenuItemComponent, NzSubMenuComponent} from "ng-zorro-antd/menu";
import {NzIconModule} from 'ng-zorro-antd/icon';
import {CommonModule} from '@angular/common';
import {Router, RouterLink, RouterLinkActive, RouterModule, RouterOutlet} from '@angular/router';
import {Observable} from 'rxjs';
import {TopNavItem, TopNavService} from "../../../core/services/top-nav.service";
import {SideMenuGroup, SideMenuService} from "../../../core/services/side-menu.service";
import {BreadcrumbItem, BreadcrumbService} from "../../../core/services/breadcrumb.service";
import {NzButtonModule} from 'ng-zorro-antd/button';
import {ErrorBannerComponent} from '../errors/error-banner.component';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    RouterModule, // 额外导入 RouterModule 保障 router-outlet 指令作用域
    NzBreadCrumbComponent,
    NzBreadCrumbItemComponent,
    NzContentComponent,
    NzSiderComponent,
    NzLayoutComponent,
    NzMenuItemComponent,
    NzHeaderComponent,
    NzMenuDirective,
    NzSubMenuComponent,
    NzIconModule, // 确保图标功能可用
    NzButtonModule, // 新增按钮模块
    ErrorBannerComponent // 全局错误提示
  ],
  templateUrl: './app-layout.component.html',
  styleUrls: ['./app-layout.component.scss']
})
export class AppLayoutComponent {
  navItems: TopNavItem[] = []; // 顶部导航来源于 TopNavService
  sideMenuGroups: SideMenuGroup[] = [];
  breadcrumbs$: Observable<BreadcrumbItem[]> = this.breadcrumbService.breadcrumbs$;
  isCollapsed = false; // 侧边栏折叠状态

  constructor(public router: Router, private sideMenuService: SideMenuService, private breadcrumbService: BreadcrumbService, private topNavService: TopNavService) {
    console.log('[AppLayout] constructing, current url:', this.router.url);
    this.navItems = [...this.topNavService.getItems()];
    this.router.events.subscribe(() => {
      // 使用微队列避免在导航早期获取旧 URL
      Promise.resolve().then(() => {
        this.updateSideMenu();
      });
    });
    this.updateSideMenu();
  }

  toggleSider() {
    this.isCollapsed = !this.isCollapsed; }
    get siderToggleIcon(): string { return this.isCollapsed ? 'menu-unfold' : 'menu-fold';
  }

  private updateSideMenu() {
    const firstSegment = this.router.url.split('/')[1] || 'cronjobs';
    this.sideMenuGroups = this.sideMenuService.getGroups(firstSegment);
  }
}
