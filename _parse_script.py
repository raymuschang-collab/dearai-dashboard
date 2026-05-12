#!/usr/bin/env python3
"""Parse uploaded script files into plain UTF-8 text."""
from __future__ import annotations

from pathlib import Path


def parse_script(source_path: str, dest_txt_path: str) -> str:
    """Read source_path, write plain text to dest_txt_path, and return it."""
    src = Path(source_path)
    ext = src.suffix.lower()

    if ext in {".txt", ".md"}:
        text = src.read_text(encoding="utf-8")
    elif ext == ".pdf":
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(str(src)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)
    elif ext == ".docx":
        import docx

        doc = docx.Document(str(src))
        text = "\n\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(
            f"unsupported script file extension {ext!r}; use .txt, .md, .docx, or .pdf"
        )

    Path(dest_txt_path).write_text(text, encoding="utf-8")
    return text
