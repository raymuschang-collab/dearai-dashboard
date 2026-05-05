---
description: Local cumulative tally of all BytePlus vidgen spend. Reads .byteplus_expense.json (auto-written on every vidgen). More reliable than balance for production tracking.
argument-hint: [--since YYYY-MM-DD] [--by-set] [--by-model]
---

```bash
cd "/Users/raymuschang/Desktop/Shotlist Workflows"
python3 byteplus_expense.py "$ARGUMENTS"
```

## What it shows

- Total entries (each = one vidgen call)
- Cumulative USD spent (estimated based on resolution × duration × tier)
- Earliest + latest timestamp
- Optional grouping by set # or model
- Recent 5 entries

## When to use

- Weekly: check team spend velocity
- Before large batch: confirm wallet has headroom
- Post-episode: see how much Episode 1 cost end-to-end
- When troubleshooting: spot abnormal spend spikes

## Note on accuracy

Estimates are based on published BytePlus pricing tiers, not actual billing. The HK parent company's actual ledger is authoritative — but `byteplus-expense` gives you a useful local proxy that doesn't require parent-account visibility.

Pairs with the Dash UI counter (when shipped).
