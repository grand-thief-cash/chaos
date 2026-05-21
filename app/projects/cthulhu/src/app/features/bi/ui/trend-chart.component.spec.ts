import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TrendChartComponent } from './trend-chart.component';
import { BITrendSection } from '../models/bi.models';

describe('TrendChartComponent', () => {
  let fixture: ComponentFixture<TrendChartComponent>;
  let component: TrendChartComponent;

  const section: BITrendSection = {
    code: 'revenue_trend',
    title: 'Revenue Trend',
    periods: ['2024-12-31', '2023-12-31', '2025-03-31', '2025-12-31'],
    series: [
      {
        code: 'revenue_total',
        label: 'Revenue',
        values: [40, 30, 35, 50],
      },
    ],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TrendChartComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TrendChartComponent);
    component = fixture.componentInstance;
  });

  it('renders chronological quarterly periods with period limit', () => {
    component.section = section;
    component.periodLimit = 12;
    component.viewMode = 'quarterly';

    component.ngOnChanges();

    const option = component.options as any;
    expect(option.xAxis.data).toEqual(['2023-12-31', '2024-12-31', '2025-03-31', '2025-12-31']);
    expect(option.series[0].data).toEqual([30, 40, 35, 50]);
  });

  it('filters annual mode and keeps latest N points', () => {
    component.section = {
      ...section,
      periods: [
        '2012-12-31', '2013-12-31', '2014-12-31', '2015-12-31', '2016-12-31', '2017-12-31',
        '2018-12-31', '2019-12-31', '2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31',
        '2024-03-31', '2024-12-31', '2025-12-31',
      ],
      series: [{ code: 'revenue_total', label: 'Revenue', values: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 999, 13, 14] }],
    };
    component.viewMode = 'annual';
    component.periodLimit = 12;

    component.ngOnChanges();

    const option = component.options as any;
    expect(option.xAxis.data).toEqual([
      '2014-12-31', '2015-12-31', '2016-12-31', '2017-12-31', '2018-12-31', '2019-12-31',
      '2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31', '2024-12-31', '2025-12-31',
    ]);
    expect(option.series[0].data).toEqual([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]);
  });
});


