# CRONJOB CONFIG


Task: STOCK_ZH_A_HIST_PARENT

| Fields      | Type   | Required | Value                       |
|-------------|--------|----------|-----------------------------|
| adjust      | string | T        | none/qfq/hfq                |
| period      | string | T        | daily/monthly/weekly/...    |
| code_list   | string | F        | 000001,000002               |
| start_data  | string | F        | 2026-01-01                  |
| end_data    | string | F        | 2026-12-31                  |
| fields      | string | F        | date,code,open,high,low,... |

```json
{"code_list":"000001","period": "daily", "adjust": "none","start_date":"2026-01-01"}
```