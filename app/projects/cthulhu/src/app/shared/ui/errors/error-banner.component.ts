import {ChangeDetectionStrategy, Component} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ErrorNotificationService} from '../../../core/errors/error-notification.service';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzButtonModule} from 'ng-zorro-antd/button';

@Component({
  selector: 'app-error-banner',
  standalone: true,
  imports: [CommonModule, NzIconModule, NzButtonModule],
  templateUrl: './error-banner.component.html',
  styleUrls: ['./error-banner.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ErrorBannerComponent {
  records$ = this.errorService.records$;
  constructor(private errorService: ErrorNotificationService) {}
  dismiss(id: string) { this.errorService.dismiss(id); }
  clearAll() { this.errorService.clearAll(); }
}
