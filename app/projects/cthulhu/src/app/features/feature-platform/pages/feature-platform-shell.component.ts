import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-feature-platform-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <section class="fp-shell">
      <header class="fp-masthead">
        <div>
          <div class="fp-kicker"><span></span> FEATURE CONTROL PLANE</div>
          <h1>Feature Platform</h1>
          <p>Registry semantics, execution evidence and materialized values in one traceable workspace.</p>
        </div>
        <nav aria-label="Feature Platform sections">
          <a routerLink="registry" routerLinkActive="active">Registry</a>
          <a routerLink="runs" routerLinkActive="active">Runs</a>
          <a routerLink="values" routerLinkActive="active">Values</a>
          <a routerLink="compute" routerLinkActive="active">Compute</a>
        </nav>
      </header>
      <main class="fp-stage"><router-outlet></router-outlet></main>
    </section>
  `,
  styles: [`
    :host { display: block; --fp-ink: #17202a; --fp-muted: #66717d; --fp-line: #d8d3c9; --fp-paper: #f7f4ed; --fp-accent: #d96c24; }
    .fp-shell { min-width: 0; max-width: 100%; min-height: calc(100vh - 132px); color: var(--fp-ink); background: var(--fp-paper); border: 1px solid var(--fp-line); }
    .fp-masthead { position: relative; display: flex; justify-content: space-between; gap: 28px; padding: 24px 28px 19px; overflow: hidden; border-bottom: 1px solid var(--fp-line); background: radial-gradient(circle at 88% -40%, rgba(217,108,36,.22), transparent 48%), linear-gradient(115deg, #fffdf8, #f1ede3); }
    .fp-masthead::after { content: ''; position: absolute; right: 24px; top: 0; width: 180px; height: 100%; opacity: .2; background: repeating-linear-gradient(90deg, transparent 0 18px, #8f887b 18px 19px); pointer-events: none; }
    .fp-kicker { display: flex; align-items: center; gap: 8px; color: #76523a; font: 700 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .16em; }
    .fp-kicker span { width: 26px; height: 3px; background: var(--fp-accent); }
    h1 { margin: 7px 0 2px; font: 700 30px/1.05 Georgia, 'Times New Roman', serif; letter-spacing: -.025em; }
    p { margin: 0; max-width: 680px; color: var(--fp-muted); }
    nav { z-index: 1; align-self: end; display: flex; flex-wrap: wrap; gap: 5px; }
    nav a { color: #4f5660; padding: 7px 10px; border-bottom: 2px solid transparent; font-size: 12px; font-weight: 700; }
    nav a.active { color: #9f4415; border-color: var(--fp-accent); background: rgba(255,255,255,.56); }
    .fp-stage { min-width: 0; padding: 22px; background-image: linear-gradient(rgba(75,72,65,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(75,72,65,.035) 1px, transparent 1px); background-size: 24px 24px; }
    @media (max-width: 800px) { .fp-masthead { display: block; padding: 18px; } h1 { font-size: 27px; } nav { margin-top: 14px; } nav a { padding: 7px 8px; } .fp-stage { padding: 10px; } }
  `],
})
export class FeaturePlatformShellComponent {}
