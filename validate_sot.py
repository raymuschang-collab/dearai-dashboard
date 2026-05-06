#!/usr/bin/env python3
"""
validate_sot.py — schema audit comparing sajangnim eps against pharaoh's canonical layout.

Probes pharaoh once to extract the reference shape, then runs the same checks
against each sajangnim ep. Output is per-ep PASS/FAIL list.

Reads only — does not modify any sheet.

Run:
  python3 validate_sot.py            # all 6 eps
  python3 validate_sot.py --ep 1     # just Ep 1
"""
from __future__ import annotations

import argparse
import time
import gspread
from auth import get_credentials


PHARAOH_SHEET = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"

EPS = {
    1: '1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc',
    2: '1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4',
    3: '10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I',
    4: '1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4',
    5: '1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg',
    6: '1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI',
}


# ====== Reference probe (pharaoh) ======

def probe_reference(sh) -> dict:
    """Read pharaoh's structure and capture the invariants we'll check sajangnim against."""
    ref = {}

    # Storyboard Prompts: rows 1-10 + a sample data row
    sp = sh.worksheet("Storyboard Prompts")
    sp_top = sp.get("A1:N12", value_render_option="FORMATTED_VALUE")
    ref["sp_global_labels"] = [(r + [""])[0] for r in sp_top[:8]]   # col A rows 1-8
    ref["sp_row_9_blank"]   = not (sp_top[8][0] if len(sp_top) > 8 and sp_top[8] else "")
    ref["sp_header_row_10"] = sp_top[9] if len(sp_top) > 9 else []
    # SP!C and D should be formulas — we'll check sajangnim by getting FORMULA value
    sp_first_data = (sp_top[10] if len(sp_top) > 10 else [])
    ref["sp_data_row_first_set"] = sp_first_data[:2] if sp_first_data else []  # ['1', '1-5'] expected

    # Video Prompts: rows 1-9
    vp = sh.worksheet("Video Prompts")
    vp_top = vp.get("A1:H10", value_render_option="FORMATTED_VALUE")
    ref["vp_global_labels"] = [(r + [""])[0] for r in vp_top[:6]]
    ref["vp_row_7_blank"]   = not (vp_top[6][0] if len(vp_top) > 6 and vp_top[6] else "")
    ref["vp_header_row_8"]  = vp_top[7] if len(vp_top) > 7 else []

    # Shotlist tab — pharaoh's name is "Strike! Pharaoh King - Ep 1"; sajangnim's is "Shotlist"
    # We just check Q/R formulas presence in the dedicated shotlist tab
    # CHARACTERS bible: row 1 header
    ws = sh.worksheet("CHARACTERS")
    ref["chars_header_row_1"] = ws.row_values(1)
    # LOCATIONS row 4
    ws = sh.worksheet("LOCATIONS")
    ref["locs_header_row_4"] = ws.row_values(4)
    # COSTUME / PROPS / EFFECTS row 5
    for tab in ("COSTUME", "PROPS", "EFFECTS"):
        ws = sh.worksheet(tab)
        ref[f"{tab.lower()}_header_row_5"] = ws.row_values(5)

    return ref


# ====== Per-ep validator ======

def check(report, name, passed, detail=""):
    """Append a check result to the report."""
    report.append({"name": name, "pass": passed, "detail": detail})


def detect_shotlist_tab(sh) -> str | None:
    """The shotlist tab is the one that isn't a bible/SP/VP/Asset/_README."""
    bibles = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
              "COSTUME", "PROPS", "EFFECTS", "Asset Library", "_README"}
    for ws in sh.worksheets():
        if ws.title not in bibles:
            return ws.title
    return None


def validate_ep(sh, ref: dict, ep_label: str) -> list[dict]:
    report = []

    # === Tab presence ===
    # Sajangnim model: bibles live on Ep 1's sheet only (BIBLE_SHEET = ep1_id),
    # so eps 2-6 only need Storyboard Prompts + Video Prompts + a Shotlist tab.
    titles = {ws.title for ws in sh.worksheets()}
    has_bibles = "CHARACTERS" in titles
    required_always = ["Storyboard Prompts", "Video Prompts"]
    for t in required_always:
        check(report, f"tab `{t}` exists", t in titles)
    sl_tab = detect_shotlist_tab(sh)
    check(report, "shotlist tab exists", sl_tab is not None,
          f"detected: {sl_tab!r}")
    if has_bibles:
        for t in ("CHARACTERS", "LOCATIONS", "COSTUME", "PROPS", "EFFECTS", "Asset Library"):
            check(report, f"tab `{t}` exists", t in titles)
    else:
        check(report, "bibles share a different sheet (this ep is bible-less)", True,
              "sajangnim shares bibles via SERIES_CONFIG.bible_sheet → Ep 1")

    # === Storyboard Prompts ===
    sp = sh.worksheet("Storyboard Prompts")
    sp_top = sp.get("A1:N12", value_render_option="FORMATTED_VALUE")
    sp_labels = [(r + [""])[0] for r in sp_top[:8]]
    check(report, "SP rows 1-8 = globals (col A labels match pharaoh)",
          [s.lower().strip() for s in sp_labels] == [s.lower().strip() for s in ref["sp_global_labels"]],
          f"got: {sp_labels} | expected: {ref['sp_global_labels']}")
    check(report, "SP row 9 = blank",
          not (sp_top[8][0] if len(sp_top) > 8 and sp_top[8] else ""))
    sp_header = sp_top[9] if len(sp_top) > 9 else []
    check(report, "SP row 10 = 14-col header", len(sp_header) >= 9 and sp_header[0] == "Set #")
    sp_first_data = sp_top[10] if len(sp_top) > 10 else []
    check(report, "SP row 11 = first set data (col A digit, col B = shot range)",
          len(sp_first_data) >= 2 and sp_first_data[0].isdigit() and sp_first_data[1])

    # SP!C, D, J, K formula check — read FORMULA option
    sp_formulas = sp.get("C11:K11", value_render_option="FORMULA")
    if sp_formulas and sp_formulas[0]:
        f = sp_formulas[0] + [""] * 9
        check(report, "SP!C11 is a formula (storyboard prompt)", f[0].startswith("="),
              f"got: {f[0][:80]!r}")
        check(report, "SP!D11 is a formula (bahasa storyboard)", f[1].startswith("="),
              f"got: {f[1][:80]!r}")
        check(report, "SP!J11 is a formula (body)", f[7].startswith("="),
              f"got: {f[7][:80]!r}")
        check(report, "SP!K11 is a formula (bahasa body)", f[8].startswith("="),
              f"got: {f[8][:80]!r}")
    else:
        check(report, "SP row 11 has formulas", False, "no data at row 11")

    # === Video Prompts ===
    vp = sh.worksheet("Video Prompts")
    vp_top = vp.get("A1:H10", value_render_option="FORMATTED_VALUE")
    vp_labels = [(r + [""])[0] for r in vp_top[:6]]
    check(report, "VP rows 1-6 = globals (col A labels)",
          all(vp_labels[i].lower().strip() == ref["vp_global_labels"][i].lower().strip()
              for i in range(min(len(vp_labels), len(ref["vp_global_labels"])))),
          f"got: {vp_labels} | expected: {ref['vp_global_labels']}")
    check(report, "VP row 7 = blank",
          not (vp_top[6][0] if len(vp_top) > 6 and vp_top[6] else ""))
    vp_header = vp_top[7] if len(vp_top) > 7 else []
    check(report, "VP row 8 = header (Set # in col A)",
          len(vp_header) >= 1 and vp_header[0] == "Set #")
    # VP!C9, D9 formulas
    vp_formulas = vp.get("C9:D9", value_render_option="FORMULA")
    if vp_formulas and vp_formulas[0]:
        f = vp_formulas[0] + ["", ""]
        check(report, "VP!C9 is a formula (English video prompt)", f[0].startswith("="),
              f"got: {f[0][:80]!r}")
        check(report, "VP!D9 is a formula (Bahasa video prompt)", f[1].startswith("="),
              f"got: {f[1][:80]!r}")

    # === Shotlist Q + R formulas ===
    if sl_tab:
        sl = sh.worksheet(sl_tab)
        sl_formulas = sl.get("Q2:R2", value_render_option="FORMULA")
        if sl_formulas and sl_formulas[0]:
            f = sl_formulas[0] + ["", ""]
            check(report, "Shotlist!Q2 is a formula (per-shot prompt)", f[0].startswith("="),
                  f"got: {f[0][:80]!r}")
            check(report, "Shotlist!R2 is a formula (Bahasa per-shot)", f[1].startswith("="),
                  f"got: {f[1][:80]!r}")
        else:
            check(report, "Shotlist!Q2:R2 are formulas", False, "no data at row 2")

    # === Bibles (only check if this ep has them — see has_bibles guard above) ===
    if has_bibles:
        chars_hdr = sh.worksheet("CHARACTERS").row_values(1)
        check(report, "CHARACTERS row 1 has 'Name' as col A",
              chars_hdr and chars_hdr[0] == "Name", f"got: {chars_hdr[:3]}")
        check(report, "CHARACTERS has Iter 1 URL column",
              any("iter 1" in (h or "").lower() for h in chars_hdr))

        locs_hdr = sh.worksheet("LOCATIONS").row_values(4)
        check(report, "LOCATIONS row 4 has 'Name' as col A",
              locs_hdr and locs_hdr[0] == "Name")

        for tab in ("COSTUME", "PROPS", "EFFECTS"):
            hdr = sh.worksheet(tab).row_values(5)
            check(report, f"{tab} row 5 has 'Name' as col A",
                  hdr and hdr[0] == "Name")

    return report


def print_report(label: str, report: list[dict]):
    passed = sum(1 for r in report if r["pass"])
    failed = len(report) - passed
    color_pass = "✓"
    color_fail = "✗"
    print(f"\n=== {label}  ({passed}/{len(report)} pass, {failed} fail) ===")
    for r in report:
        mark = color_pass if r["pass"] else color_fail
        line = f"  {mark} {r['name']}"
        if not r["pass"] and r["detail"]:
            line += f"\n      {r['detail'][:200]}"
        print(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ep", type=int, help="Validate only this ep number")
    args = ap.parse_args()

    gc = gspread.authorize(get_credentials())

    print(f"→ probing pharaoh reference schema…")
    pharaoh = gc.open_by_key(PHARAOH_SHEET)
    ref = probe_reference(pharaoh)
    print(f"  ✓ reference captured: {len(ref['sp_global_labels'])} SP globals, "
          f"{len(ref['vp_global_labels'])} VP globals, "
          f"{len(ref['sp_header_row_10'])}-col SP header")

    eps_to_check = [args.ep] if args.ep else list(EPS.keys())
    summaries = []
    for n in eps_to_check:
        sid = EPS[n]
        last_err = None
        for attempt in range(3):
            try:
                sh = gc.open_by_key(sid)
                report = validate_ep(sh, ref, f"Ep {n}")
                print_report(f"Ep {n}", report)
                passed = sum(1 for r in report if r["pass"])
                summaries.append((n, passed, len(report)))
                last_err = None
                break
            except Exception as e:
                last_err = e
                if "429" in str(e) and attempt < 2:
                    print(f"\n=== Ep {n} === 429 quota — sleeping 60s then retrying…")
                    time.sleep(60)
                    continue
                break
        if last_err:
            print(f"\n=== Ep {n} ===\n  ERROR probing: {str(last_err)[:120]}")
            summaries.append((n, 0, 0))
        time.sleep(8)  # quota courtesy

    print("\n=== ROLLUP ===")
    for n, passed, total in summaries:
        pct = (100 * passed / total) if total else 0
        status = "✓" if passed == total else "⚠"
        print(f"  {status} Ep {n}: {passed}/{total} pass ({pct:.0f}%)")


if __name__ == "__main__":
    main()
