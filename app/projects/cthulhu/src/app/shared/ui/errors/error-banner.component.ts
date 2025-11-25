import {ChangeDetectionStrategy, Component} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ErrorNotificationService} from '../../../core/errors/error-notification.service';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzAlertModule} from 'ng-zorro-antd/alert';

@Component({
  selector: 'app-error-banner',
  standalone: true,
  imports: [CommonModule, NzIconModule, NzButtonModule, NzAlertModule],
  templateUrl: './error-banner.component.html',
  styleUrls: ['./error-banner.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ErrorBannerComponent {
  records$ = this.errorService.records$;
  constructor(private errorService: ErrorNotificationService) {}
  dismiss(id: string) { this.errorService.dismiss(id); }
  clearAll() { this.errorService.clearAll(); }
  trackById = (_: number, r: any) => r.id;
  alertType(severity: string){
    switch(severity){
      case 'error': return 'error';
      case 'warning': return 'warning';
      default: return 'info';
    }
  }
  formatDescription(r: any){
    const parts: string[] = [];
    if (r.status) parts.push(`状态: ${r.status} ${r.statusText||''}`.trim());
    if (r.rawMessage) parts.push(r.rawMessage);
    if (r.url) parts.push(r.url);
    return parts.join(' \n ');
  }
}
