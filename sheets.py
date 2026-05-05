"""Thin gspread helpers backed by the OAuth user credentials in token.json."""
from typing import Any

import gspread

from auth import get_credentials


def _client() -> gspread.Client:
    return gspread.authorize(get_credentials())


def read_calendar(sheet_id: str, tab: str = "Calendar") -> list[dict[str, Any]]:
    """Return all rows of `tab` as dicts keyed by the header row."""
    ws = _client().open_by_key(sheet_id).worksheet(tab)
    return ws.get_all_records()


def append_rows(
    sheet_id: str,
    rows: list[list[Any]],
    tab: str = "Calendar",
) -> dict[str, Any]:
    """Batch-append `rows` to `tab`. Each row is a list of cell values."""
    ws = _client().open_by_key(sheet_id).worksheet(tab)
    return ws.append_rows(rows, value_input_option="USER_ENTERED")
