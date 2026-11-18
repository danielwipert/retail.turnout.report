## Model bake-off

Quarters per model: 24

| Model | Verified | Flagged | Missing | Derived | Suspected false passes | Errors | Cost (USD) | Input tokens |
|---|---|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 105 | 9 | 3 | 3 | 6 | 0 | $0.0452 | 696,969 |
| `google/gemini-2.5-flash` | 108 | 2 | 10 | 0 | 5 | 0 | $0.2239 | 683,336 |
| `google/gemini-3.1-flash-lite` | 106 | 9 | 5 | 0 | 4 | 0 | $0.2418 | 910,862 |

**Recommended:** none passed. Look at the disagreements below.

### Disagreements (verified values that differ between models)

| Chain | Quarter | Field | Values | Majority |
|---|---|---|---|---|
| FND | 2024-12-26 | margin_pct | gemini-2.5-flash=43.5, gemini-3.1-flash-lite=43.3, gpt-oss-20b=43.5 | 43.5 |
| FND | 2025-12-25 | comp_traffic_pct | gemini-3.1-flash-lite=-3.5, gpt-oss-20b=-4.8 | None |
| TXRH | 2025-04-01 | margin_pct | gemini-2.5-flash=16.7, gemini-3.1-flash-lite=16.7, gpt-oss-20b=16.6 | 16.7 |
| TXRH | 2025-07-01 | comp_ticket_pct | gemini-2.5-flash=1.8, gemini-3.1-flash-lite=1.8, gpt-oss-20b=5.8 | 1.8 |
| TXRH | 2025-09-30 | margin_pct | gemini-2.5-flash=14.4, gemini-3.1-flash-lite=14.4, gpt-oss-20b=14.3 | 14.4 |
| TXRH | 2026-09-29 | comp_sales_pct | gemini-2.5-flash=4.4, gemini-3.1-flash-lite=4.3, gpt-oss-20b=4.3 | 4.3 |
| TXRH | 2026-09-29 | margin_pct | gemini-2.5-flash=14.8, gemini-3.1-flash-lite=14.8, gpt-oss-20b=14.6 | 14.8 |
| WMT | 2024-10-31 | comp_sales_pct | gemini-2.5-flash=5.3, gemini-3.1-flash-lite=5.1, gpt-oss-20b=5.3 | 5.3 |
| WMT | 2024-10-31 | ending_units | gemini-3.1-flash-lite=4606.0, gpt-oss-20b=1050.0 | None |
| WMT | 2025-01-31 | margin_pct | gemini-2.5-flash=26.8, gemini-3.1-flash-lite=23.9, gpt-oss-20b=23.9 | 23.9 |
| WMT | 2025-04-30 | comp_sales_pct | gemini-2.5-flash=4.5, gemini-3.1-flash-lite=3.1, gpt-oss-20b=4.5 | 4.5 |
| WMT | 2025-04-30 | margin_pct | gemini-3.1-flash-lite=27.5, gpt-oss-20b=24.2 | None |
| WMT | 2025-07-31 | margin_pct | gemini-2.5-flash=24.5, gemini-3.1-flash-lite=24.5, gpt-oss-20b=27.9 | 24.5 |
| WMT | 2025-10-31 | comp_sales_pct | gemini-2.5-flash=4.8, gemini-3.1-flash-lite=4.5, gpt-oss-20b=4.5 | 4.5 |
| WMT | 2025-10-31 | ending_units | gemini-2.5-flash=698.0, gemini-3.1-flash-lite=4606.0 | None |
| WMT | 2025-10-31 | margin_pct | gemini-2.5-flash=27.6, gpt-oss-20b=24.2 | None |
| WMT | 2026-01-31 | margin_pct | gemini-2.5-flash=26.9, gemini-3.1-flash-lite=26.9, gpt-oss-20b=24.0 | 26.9 |
| WMT | 2026-04-30 | comp_sales_pct | gemini-2.5-flash=4.1, gemini-3.1-flash-lite=4.3, gpt-oss-20b=4.1 | 4.1 |
| WMT | 2026-04-30 | ending_units | gemini-2.5-flash=699.0, gemini-3.1-flash-lite=4614.0, gpt-oss-20b=4614.0 | 4614.0 |
| WMT | 2026-04-30 | margin_pct | gemini-2.5-flash=24.3, gemini-3.1-flash-lite=0.29, gpt-oss-20b=27.8 | None |
| WMT | 2026-07-31 | ending_units | gemini-2.5-flash=699.0, gemini-3.1-flash-lite=4615.0, gpt-oss-20b=4615.0 | 4615.0 |
