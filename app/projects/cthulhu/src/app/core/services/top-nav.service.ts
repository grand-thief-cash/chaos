import {Injectable} from '@angular/core';

export interface TopNavItem { key: string; label: string; icon: string; path: string; }

@Injectable({ providedIn: 'root' })
export class TopNavService {
  private readonly items: TopNavItem[] = [
    { key: 'cronjobs', label: 'Cron Jobs', icon: 'user', path: '/cronjobs' }
  ];
  getItems(): ReadonlyArray<TopNavItem> { return this.items; }
}
