export interface Cronjob {
  id: string;
  name: string;
  schedule: string; // Cron 表达式
  status: 'active' | 'inactive' | 'error';
  lastRunAt?: string;
  nextRunAt?: string;
}

