#!/usr/bin/env python3
"""Rebuild Storyboard Prompts tab to reflect post-Daniel-rewrite shotlist (12 sets).
- Sets 1, 2 unchanged (content didn't shift)
- Sets 3-11 content shifted by +5 shots due to Daniel scene rewrite — reset status, clear URLs
- Set 12 (new, shots 56-59) added
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import gspread
from auth import get_credentials

SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
TAB = "Storyboard Prompts"

# Per-row updates: (row, set#, shot_range, status, location, clear_urls)
ROWS = [
    # (row, set, range, status, location, clear)
    (13, 3,  "11-15", "Pending", "Grace's Home Studio",                  True),
    (14, 4,  "16-20", "Pending", "Grace's Home Studio",                  True),
    (15, 5,  "21-25", "Pending", "Grace's Home Studio",                  True),
    (16, 6,  "26-30", "Pending", "Grace's Home Studio + Dhoby Ghaut MRT", True),
    (17, 7,  "31-35", "Pending", "Dhoby Ghaut MRT + Carmen's Apartment", True),
    (18, 8,  "36-40", "Pending", "Carmen's Apartment",                   True),
    (19, 9,  "41-45", "Pending", "Carmen's Apartment",                   True),
    (20, 10, "46-50", "Pending", "Carmen's Apartment + Grace's Home Studio", True),
    (21, 11, "51-55", "Pending", "Grace's Home Studio",                  True),
    (22, 12, "56-59", "Pending", "Grace's Home Studio + Long Take",      True),  # NEW row
]


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(TAB)

    print("Pre-state: reading row 21 formulas to clone to row 22...")
    row21_formulas = ws.get("A21:N21", value_render_option="FORMULA")[0]

    # Build the row 22 (set 12) — copy formulas from row 21 with row-number bump
    # Cols: A B C D E F G H I J K L M N
    # A: set #, B: range, C: formula (uses $B$ absolutes + TEXTJOIN — row-relative via ROW())
    # D: =IF(A22="","",GOOGLETRANSLATE(C22,"en","id"))
    # E: drive folder (manual), F: status, G/H: storyboard URLs (manual)
    # I: error, J: formula via INDIRECT row-relative, K: bahasa translate of J
    # L: location, M/N: video URLs (manual)
    def bump_formula(f, from_row, to_row):
        """Replace bare A{from}, C{from}, etc with A{to} (avoiding $-prefixed absolutes)."""
        import re
        return re.sub(
            rf"(?<![\$\w]){chr(0)}",
            "",
            re.sub(rf"(?<![\$\w])([A-N]){from_row}\b", rf"\g<1>{to_row}", f)
        )

    c_formula = bump_formula(row21_formulas[2], 21, 22)
    d_formula = bump_formula(row21_formulas[3], 21, 22)
    j_formula = bump_formula(row21_formulas[9], 21, 22)
    k_formula = bump_formula(row21_formulas[10], 21, 22)

    # Apply per-row updates via batch
    print("\nBatch updates:")
    updates = []
    for row, set_n, shot_range, status, location, clear_urls in ROWS:
        is_new = (row == 22)
        print(f"  row {row}: set {set_n}, range {shot_range}, status {status}, location '{location[:40]}', clear_urls={clear_urls}, NEW={is_new}")
        if is_new:
            # Build full new row
            updates.append({
                "range": f"A{row}:N{row}",
                "values": [[
                    set_n,           # A: set #
                    shot_range,      # B: range
                    c_formula,       # C: storyboard prompt
                    d_formula,       # D: bahasa
                    "",              # E: drive folder (manual setup later)
                    status,          # F
                    "",              # G iter 1
                    "",              # H iter 2
                    "",              # I error
                    j_formula,       # J body
                    k_formula,       # K bahasa body
                    location,        # L
                    "",              # M video iter 1
                    "",              # N video iter 2
                ]],
            })
        else:
            # Update existing row — keep formulas + E (drive folder)
            updates.append({"range": f"B{row}", "values": [[shot_range]]})
            updates.append({"range": f"F{row}", "values": [[status]]})
            if clear_urls:
                # Clear G/H/I (storyboard URLs + error) and M/N (video URLs)
                updates.append({"range": f"G{row}:I{row}", "values": [["", "", ""]]})
                updates.append({"range": f"M{row}:N{row}", "values": [["", ""]]})
            updates.append({"range": f"L{row}", "values": [[location]]})

    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"\n✓ Applied {len(updates)} updates")

    # Verify
    print("\nVerifying...")
    after = ws.get("A11:N22", value_render_option="FORMATTED_VALUE")
    for ri, r in enumerate(after, start=11):
        if not r: continue
        pad = r + ['']*(14-len(r))
        print(f"  row {ri}: set={pad[0]}, range={pad[1]:<6}, status={pad[5]:<8}, location={pad[11][:50]}")


if __name__ == "__main__":
    main()
