#!/usr/bin/env python3
"""
byteplus_balance.py — Query the BytePlus wallet balance.

NOTE: BytePlus may not expose wallet balance via API to subaccounts (the HK
parent company may have it gated). This script tries the standard endpoints
and reports what comes back.

For PRODUCTION TRACKING use byteplus_expense.py (your cumulative spend tally,
which works regardless of wallet visibility).
"""
import os, sys, json, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3")

if not ARK_API_KEY:
    sys.exit("BYTEPLUS_ARK_API_KEY not set in .env")

candidates = [
    f"{ARK_BASE}/account/balance",
    f"{ARK_BASE}/wallet/balance",
    f"{ARK_BASE}/account/info",
    f"{ARK_BASE}/billing/balance",
]

print("Querying BytePlus wallet balance...")
for endpoint in candidates:
    try:
        r = requests.get(endpoint, headers={"Authorization": f"Bearer {ARK_API_KEY}"}, timeout=15)
        if r.status_code == 200:
            print(f"\n✓ {endpoint}")
            print(json.dumps(r.json(), indent=2))
            sys.exit(0)
        else:
            print(f"  {endpoint} → {r.status_code}")
    except Exception as e:
        print(f"  {endpoint} → exception: {e}")

print("\n⚠ No balance endpoint responded. Likely:")
print("  - Subaccount lacks billing visibility (HK parent owns wallet)")
print("  - Endpoint path is different than tried — check BytePlus console")
print("\nFor production tracking, use:")
print("  python3 byteplus_expense.py")
print("  (cumulative spend tally from local .byteplus_expense.json)")
