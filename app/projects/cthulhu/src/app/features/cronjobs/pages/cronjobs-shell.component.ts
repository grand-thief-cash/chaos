import {Component} from '@angular/core';
import {RouterOutlet} from '@angular/router';

@Component({
  selector: 'cronjobs-shell',
  standalone: true,
  imports: [RouterOutlet],
  template: `<div class="cronjobs-shell"><router-outlet></router-outlet></div>`
})
export class CronjobsShellComponent {
  constructor() {
    console.log('[CronjobsShell] initialized');
  }
}
