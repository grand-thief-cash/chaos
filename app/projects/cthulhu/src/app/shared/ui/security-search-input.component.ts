import { Component, EventEmitter, Input, OnDestroy, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { of, Subject, Subscription } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, filter, finalize, switchMap, tap } from 'rxjs/operators';

import { SecurityLookupService, SecuritySearchItem } from '../../core/services/security-lookup.service';

/**
 * Reusable securities typeahead: type a name (fuzzy contains) or a symbol
 * (exact) and pick from the dropdown. Emits the selected item, or `null` the
 * moment the user edits the text after a selection - so a parent that gates a
 * "查询" button on a non-null selection can never query a stale security_id.
 *
 * HTTP lives in SecurityLookupService; debounce / cancellation (switchMap) /
 * min-length live here so the service stays a thin reusable client.
 */
@Component({
  selector: 'app-security-search-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="ssi-wrap">
      <input
        type="text"
        class="ssi-input"
        [(ngModel)]="text"
        (input)="onInput($event)"
        (focus)="open = results.length > 0"
        (blur)="onBlur()"
        [placeholder]="placeholder"
        autocomplete="off"
      />
      @if (open) {
        <div class="ssi-dropdown" role="listbox">
          @if (lastError) {
            <div class="ssi-empty ssi-error">搜索失败：{{ lastError }}</div>
          } @else if (loading) {
            <div class="ssi-empty">搜索中…</div>
          } @else if (results.length === 0) {
            <div class="ssi-empty">无匹配</div>
          } @else {
            @for (item of results; track item.security_id) {
              <button
                type="button"
                class="ssi-option"
                (mousedown)="select(item)"
              >
                <span class="ssi-name">{{ item.name || item.symbol }}</span>
                <span class="ssi-sym">{{ item.symbol }}</span>
                <span class="ssi-ex">{{ item.exchange }}</span>
                @if (item.status !== 'active') {
                  <span class="ssi-tag">停牌/退市</span>
                }
              </button>
            }
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .ssi-wrap {
      position: relative;
      display: inline-block;
    }

    .ssi-input {
      height: 34px;
      width: 240px;
      border: 1px solid rgba(34, 72, 112, 0.26);
      background: rgba(255, 255, 255, 0.45);
      color: #1b2a3c;
      padding: 0 10px;
      border-radius: 4px;
      font-weight: 620;
      outline: none;
    }

    .ssi-dropdown {
      position: absolute;
      top: 100%;
      left: 0;
      z-index: 20;
      margin-top: 4px;
      min-width: 320px;
      max-height: 320px;
      overflow-y: auto;
      background: #fff;
      border: 1px solid #d7e0ea;
      box-shadow: 0 6px 18px rgba(24, 86, 150, 0.16);
    }

    .ssi-empty {
      padding: 10px 14px;
      color: #8a97a8;
      font-size: 13px;
    }

    .ssi-error {
      color: #cf1322;
    }

    .ssi-option {
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      padding: 8px 14px;
      border: 0;
      background: #fff;
      text-align: left;
      cursor: pointer;
      font-size: 13px;
      line-height: 1.4;
    }

    .ssi-option:hover,
    .ssi-option:focus {
      background: #eef5ff;
    }

    .ssi-name {
      flex: 1 1 auto;
      color: #152033;
      font-weight: 680;
    }

    .ssi-sym {
      color: #1d5fae;
      font-weight: 700;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    .ssi-ex {
      color: #8a97a8;
      font-size: 12px;
    }

    .ssi-tag {
      color: #cf1322;
      font-size: 11px;
      border: 1px solid #ffccc7;
      border-radius: 3px;
      padding: 0 4px;
    }
  `],
})
export class SecuritySearchInputComponent implements OnDestroy {
  private readonly lookup = inject(SecurityLookupService);

  @Input() placeholder = '输入名称或代码';
  @Input() market = 'zh_a';
  @Input() assetType = 'stock';
  @Input() limit = 20;
  /** Minimum trimmed term length before firing a search. */
  @Input() minTerm = 1;
  @Output() securitySelected = new EventEmitter<SecuritySearchItem | null>();

  text = '';
  results: SecuritySearchItem[] = [];
  loading = false;
  open = false;
  lastError: string | null = null;

  private selected: SecuritySearchItem | null = null;
  private readonly terms = new Subject<string>();
  private readonly sub: Subscription;

  constructor() {
    this.sub = this.terms.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      tap((term) => {
        if (term.trim().length < this.minTerm) {
          this.results = [];
          this.open = false;
        }
      }),
      filter((term) => term.trim().length >= this.minTerm),
      switchMap((term) => {
        // loading lifecycle is scoped to each inner observable so a canceled
        // request's finalize can't reset the active request's flag.
        this.loading = true;
        this.lastError = null;
        return this.lookup
          .search(term.trim(), { market: this.market, asset_type: this.assetType, limit: this.limit })
          .pipe(
            // A failed search must NOT kill the outer stream - swallow the
            // error into an empty result + error state so the next keystroke
            // still triggers a search.
            catchError((err) => {
              this.lastError = err?.message ?? '搜索失败';
              this.results = [];
              return of({ items: [], total: 0, limit: this.limit, offset: 0 } as { items: SecuritySearchItem[]; total: number; limit: number; offset: number });
            }),
            finalize(() => (this.loading = false)),
          );
      }),
    ).subscribe((resp) => {
      this.results = resp?.items ?? [];
      this.open = true;
    });
  }

  onInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    // Sync guard: clear a prior selection the instant the text diverges, so a
    // parent gating on a non-null selection can't fire a stale security_id
    // during the 300ms debounce window. Only the HTTP search is debounced.
    if (this.selected && value !== this.display(this.selected)) {
      this.clearSelection();
    }
    this.terms.next(value);
  }

  onBlur(): void {
    // Defer close so a mousedown on an option registers before the input
    // loses focus and the dropdown collapses.
    setTimeout(() => {
      this.open = false;
    }, 150);
  }

  select(item: SecuritySearchItem): void {
    this.selected = item;
    this.text = this.display(item);
    this.results = [item];
    this.open = false;
    this.securitySelected.emit(item);
  }

  private clearSelection(): void {
    this.selected = null;
    this.securitySelected.emit(null);
  }

  private display(item: SecuritySearchItem): string {
    return item.name ? `${item.name} · ${item.symbol}` : item.symbol;
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }
}
