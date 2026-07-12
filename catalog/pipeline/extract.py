"""Stage 1: extract per-page text (and light layout) from the catalog PDF into a cache.

The catalog is a large (~719pp) CourseLeaf PDF. Re-extracting on every parser run is
slow, so this stage runs once and writes a JSON cache that later stages read.

Output: catalog/data/pages.json
    {
      "source": "<pdf filename>",
      "page_count": <int>,
      "printed_offset": <int|null>,   # printed_page_number - pdf_index, if detectable
      "pages": [ {"index": i, "printed": <int|null>, "text": "..."} , ... ]
    }
"""
import json
import os
import re
import sys

import pdfplumber

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PDF_PATH = os.path.join(ROOT, "2024-2025 Undergraduate.pdf")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pages.json")


def detect_printed_number(page):
    """Read a bare page number from the page footer, if present."""
    h = page.height
    try:
        words = page.extract_words()
    except Exception:
        return None
    footer = [w for w in words if w["top"] > h * 0.90 and re.fullmatch(r"\d{1,4}", w["text"])]
    if footer:
        # bottom-most bare integer
        footer.sort(key=lambda w: w["top"])
        return int(footer[-1]["text"])
    return None


def main():
    if not os.path.exists(PDF_PATH):
        sys.exit(f"PDF not found: {PDF_PATH}")
    pages = []
    printed_offsets = []
    with pdfplumber.open(PDF_PATH) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            printed = detect_printed_number(page)
            if printed is not None:
                printed_offsets.append(printed - i)
            pages.append({"index": i, "printed": printed, "text": text})
            if i % 50 == 0:
                print(f"  extracted page {i}/{n}", flush=True)
    # most common (printed - index) offset
    offset = None
    if printed_offsets:
        offset = max(set(printed_offsets), key=printed_offsets.count)
    out = {
        "source": os.path.basename(PDF_PATH),
        "page_count": len(pages),
        "printed_offset": offset,
        "pages": pages,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f)
    print(f"Wrote {OUT_PATH}: {len(pages)} pages, printed_offset={offset}", flush=True)


if __name__ == "__main__":
    main()
