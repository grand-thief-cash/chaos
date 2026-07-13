import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { SecuritySearchInputComponent } from './security-search-input.component';
import { SecurityLookupService, SecuritySearchItem } from '../../core/services/security-lookup.service';

describe('SecuritySearchInputComponent', () => {
  let fixture: ComponentFixture<SecuritySearchInputComponent>;
  let component: SecuritySearchInputComponent;
  let mockSearch: jasmine.Spy;

  const item = (over: Partial<SecuritySearchItem>): SecuritySearchItem => ({
    security_id: 1,
    symbol: '000001',
    name: '平安银行',
    exchange: 'SZ',
    asset_type: 'stock',
    market: 'zh_a',
    status: 'active',
    ...over,
  });

  beforeEach(async () => {
    mockSearch = jasmine.createSpy('search');
    await TestBed.configureTestingModule({
      imports: [SecuritySearchInputComponent],
      providers: [{ provide: SecurityLookupService, useValue: { search: mockSearch } }],
    }).compileComponents();

    fixture = TestBed.createComponent(SecuritySearchInputComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => component.ngOnDestroy());

  function typeInput(value: string): void {
    component.onInput({ target: { value } } as unknown as Event);
  }

  it('emits the selected item and sets the display text', () => {
    const emissions: (SecuritySearchItem | null)[] = [];
    component.securitySelected.subscribe((v) => emissions.push(v));

    component.select(item({ security_id: 2, symbol: '600519', name: '贵州茅台' }));

    expect(emissions).toEqual([item({ security_id: 2, symbol: '600519', name: '贵州茅台' })]);
    expect(component.text).toBe('贵州茅台 · 600519');
  });

  it('emits null synchronously when text diverges after a selection (no debounce wait)', () => {
    const emissions: (SecuritySearchItem | null)[] = [];
    component.securitySelected.subscribe((v) => emissions.push(v));

    component.select(item({ security_id: 2, symbol: '600519', name: '贵州茅台' }));
    expect(emissions).toEqual([item({ security_id: 2, symbol: '600519', name: '贵州茅台' })]);

    // User edits the picked text to something else. The null must arrive
    // SYNCHRONOUSLY (in onInput, before debounceTime) so a parent gating a
    // "查询" button can't fire a stale security_id during the 300ms window.
    typeInput('something else');
    expect(emissions[1]).toBeNull();
    expect(emissions.length).toBe(2);
  });

  it('keeps the selection when the text still matches the display', () => {
    const emissions: (SecuritySearchItem | null)[] = [];
    component.securitySelected.subscribe((v) => emissions.push(v));
    const picked = item({ security_id: 2, symbol: '600519', name: '贵州茅台' });
    component.select(picked);

    // re-typing the exact same display value must NOT clear the selection.
    typeInput(component.text);
    expect(emissions).toEqual([picked]);
  });

  it('does not search for input shorter than minTerm', fakeAsync(() => {
    typeInput('');
    tick(300);
    expect(mockSearch).not.toHaveBeenCalled();
    expect(component.results).toEqual([]);
  }));

  it('survives an HTTP error and keeps searching on subsequent input', fakeAsync(() => {
    // First search errors; the stream must NOT die - the next keystroke should
    // still trigger a search and populate results.
    mockSearch.and.returnValues(
      throwError(() => new Error('boom')),
      of({ items: [item({ security_id: 2, symbol: '600519', name: '贵州茅台' })], total: 1, limit: 20, offset: 0 }),
    );

    typeInput('茅台');
    tick(300);
    expect(component.lastError).toBe('boom');
    expect(component.results).toEqual([]);

    // second input after the failure -> stream still alive -> results populate
    typeInput('茅台2');
    tick(300);
    expect(component.lastError).toBeNull();
    expect(component.results.length).toBe(1);
    expect(component.results[0].security_id).toBe(2);
  }));
});
