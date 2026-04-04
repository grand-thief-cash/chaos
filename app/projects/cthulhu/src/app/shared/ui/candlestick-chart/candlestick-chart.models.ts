import { Bar, IndicatorSeriesMeta } from '../../../features/workbench/models/workbench.model';

export interface SignalEvent {
  date: string;
  signal: 'BUY' | 'SELL';
  price: number;
}

export { Bar, IndicatorSeriesMeta };
