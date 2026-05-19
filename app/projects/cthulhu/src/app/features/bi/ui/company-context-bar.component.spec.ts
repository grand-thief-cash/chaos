import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CompanyContextBarComponent } from './company-context-bar.component';

describe('CompanyContextBarComponent', () => {
  let fixture: ComponentFixture<CompanyContextBarComponent>;
  let component: CompanyContextBarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CompanyContextBarComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CompanyContextBarComponent);
    component = fixture.componentInstance;
    component.company = {
      symbol: '000001',
      name: '测试股份',
      market: 'zh_a',
      exchange: 'SZ',
      industry: { taxonomy: 'sw', level: 1, code: '801120', name: '食品饮料', index_code: '801120.SI' },
      comp_type_code: 1,
      financial_sector: false,
    };
    component.asOfDate = '2026-05-19';
    component.latestPeriod = '2025-12-31';
    fixture.detectChanges();
  });

  it('should render company context information', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('测试股份');
    expect(text).toContain('000001');
    expect(text).toContain('2026-05-19');
    expect(text).toContain('2025-12-31');
  });
});

