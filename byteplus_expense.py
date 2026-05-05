#!/usr/bin/env python3
"""
byteplus_expense.py — Cumulative BytePlus spend tally for your team.

Reads .byteplus_expense.json (written by byteplus_vidgen.py on every gen)
and reports total + breakdown by date / set / model.

Useful when subaccount can't see wallet balance — gives you LOCAL truth on
how much you've burned. Pairs with the Dash UI counter.

Usage:
  python3 byteplus_expense.py                # full tally
  python3 byteplus_expense.py --since 2026-05-01
  python3 byteplus_expense.py --by-set       # group by set #
"""
import argparse, json, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

LOG = Path(__file__).parent / ".byteplus_expense.json"

ap = argparse.ArgumentParser()
ap.add_argument("--since", help="ISO date filter (e.g., 2026-05-01)")
ap.add_argument("--by-set", action="store_true")
ap.add_argument("--by-model", action="store_true")
args = ap.parse_args()

if not LOG.exists():
    print("No expense log yet. (.byteplus_expense.json doesn't exist)")
    print("It auto-creates after the first vidgen call.")
    sys.exit(0)

log = json.loads(LOG.read_text())
entries = log.get("entries", [])

if args.since:
    entries = [e for e in entries if e["ts"] >= args.since]

print(f"=== BytePlus Expense Tally ===\n")
print(f"  total entries: {len(entries)}")
print(f"  cumulative USD: ${sum(e['estimated_usd'] for e in entries):.2f}")
print(f"  earliest: {entries[0]['ts'] if entries else 'n/a'}")
print(f"  latest:   {entries[-1]['ts'] if entries else 'n/a'}")

if args.by_set:
    by_set = defaultdict(lambda: {"count": 0, "usd": 0.0})
    for e in entries:
        by_set[e["set"]]["count"] += 1
        by_set[e["set"]]["usd"] += e["estimated_usd"]
    print(f"\n  By set:")
    for s in sorted(by_set):
        v = by_set[s]
        print(f"    set {s:>2}: {v['count']:>3} gens, ${v['usd']:.2f}")

if args.by_model:
    by_model = defaultdict(lambda: {"count": 0, "usd": 0.0})
    for e in entries:
        by_model[e["model"]]["count"] += 1
        by_model[e["model"]]["usd"] += e["estimated_usd"]
    print(f"\n  By model:")
    for m, v in sorted(by_model.items()):
        print(f"    {m:<20}: {v['count']:>3} gens, ${v['usd']:.2f}")

# Recent (last 5 entries)
if entries:
    print(f"\n  Recent 5:")
    for e in entries[-5:]:
        print(f"    [{e['ts'][:16]}] set {e.get('set','?'):>2} slot {e.get('slot','?')} {e.get('model','?'):<10} {e.get('duration','?')}s {e.get('resolution','?'):<6} ${e['estimated_usd']:.2f}")
