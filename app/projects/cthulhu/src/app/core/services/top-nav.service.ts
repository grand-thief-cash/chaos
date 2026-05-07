import {Injectable} from '@angular/core';

export interface TopNavItem { key: string; label: string; icon: string; path: string; }

@Injectable({ providedIn: 'root' })
export class TopNavService {
  private readonly items: TopNavItem[] = [
    { key: 'cronjobs', label: 'Cron Jobs', icon: 'user', path: '/cronjobs' },
    { key: 'artemis', label: 'Artemis', icon: 'bars', path: '/artemis' },
    { key: 'workbench', label: 'Workbench', icon: 'line-chart', path: '/workbench' },
    { key: 'phoenixa', label: 'PhoenixA', icon: 'database', path: '/phoenixa' }
  ];
  getItems(): ReadonlyArray<TopNavItem> { return this.items; }
}
