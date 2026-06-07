---
description: Query BytePlus wallet balance via API. May be gated for subaccounts — falls back to byteplus-expense if balance endpoint isn't accessible.
argument-hint: (no args)
---

```bash
cd "/Users/raymuschang/Documents/Shotlist Workflows"
python3 byteplus_balance.py
```

If the API responds with balance: report it.
If the API gates the endpoint (subaccount can't see parent wallet): suggest running `/byteplus-expense` for the local cumulative spend tally.

## Note

The HK parent company owns the $1M wallet. Subaccount visibility may be restricted by their billing setup. **`/byteplus-expense` is the more reliable production tracker** — it's a local tally based on actual gens fired, regardless of wallet API access.
