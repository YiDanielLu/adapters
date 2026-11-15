"""Build reference ("oracle") Markdown for an olmOCR-Bench page from its unit tests.

olmOCR-Bench ships no gold transcription, only rule-based unit tests. The oracle is
constructed from the tests themselves so that a correct adaptation scores 100%:

* present  -> the text is emitted verbatim (texts restricted to the first/last N
              characters are placed at the very start/end of the document)
* absent   -> nothing is emitted for it; neutral filler text pads the start and end
              so `first_n`/`last_n` windows never contain unrelated content
* order    -> the ordered snippets are emitted, then emitted a second time; any
              `before` occurrence in the first copy then precedes any `after`
              occurrence in the second copy, which satisfies every order test
* math     -> the reference LaTeX is emitted verbatim in display delimiters, which
              hits the exact-match path of MathTest.run()
* table    -> one small HTML table per test, placing the target cell and its
              up/down/left/right neighbours and top/left headings around it
* baseline -> satisfied by the filler (non-empty, no repetition, no CJK/emoji)

Every snippet goes in its own paragraph: olmOCR's normalize_text() strips `*`/`_`
emphasis pairs only within a line, so separating snippets keeps the normalized
document identical to the normalized test strings.
"""

from __future__ import annotations

import html
from typing import Iterable

FILLER_START = "Reference transcription of the page follows."
FILLER_END = "End of the reference transcription."


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _math_blocks(maths: list[str]) -> list[str]:
    """Display-math paragraphs for the reference LaTeX strings.

    MathTest.run() extracts \\(..\\) first, then \\[..\\], then $$..$$, then $..$ (each
    non-greedy over the whole document) and passes on an exact match, else on a KaTeX
    rendering comparison. Equations that themselves contain `\\[`/`\\(` (e.g. a `\\\\[15pt]`
    row break) are written with $$ and placed after every \\[..\\] block, so the earlier
    patterns cannot pair their brackets with a later closing delimiter.
    """
    clean, tricky = [], []
    for math in maths:
        m = math.strip()
        if m.endswith("\\"):
            # a trailing "\ " (explicit space) would be stripped into a dangling backslash;
            # an empty group keeps the rendering identical
            m = m + " {}"
        if any(d in m for d in ("\\[", "\\]", "\\(", "\\)")):
            tricky.append(f"$${m}$$")
        else:
            clean.append(f"\\[{m}\\]")
    return clean + tricky


def _table_html(test: dict) -> str:
    cell = test.get("cell") or ""
    up, down = test.get("up") or "", test.get("down") or ""
    left, right = test.get("left") or "", test.get("right") or ""
    top_heading, left_heading = test.get("top_heading") or "", test.get("left_heading") or ""

    # Column layout: [left_heading] [left] target [right]
    cols: list[str] = []
    if left_heading:
        cols.append("left_heading")
    if left:
        cols.append("left")
    cols.append("target")
    if right:
        cols.append("right")
    # Row layout: [top_heading] [up] target [down]
    rows: list[str] = []
    if top_heading:
        rows.append("top_heading")
    if up:
        rows.append("up")
    rows.append("target")
    if down:
        rows.append("down")

    tc, tr = cols.index("target"), rows.index("target")
    grid = [["" for _ in cols] for _ in rows]
    grid[tr][tc] = cell
    if up:
        grid[rows.index("up")][tc] = up
    if down:
        grid[rows.index("down")][tc] = down
    if left:
        grid[tr][cols.index("left")] = left
    if right:
        grid[tr][cols.index("right")] = right
    if top_heading:
        grid[0][tc] = top_heading
    if left_heading:
        grid[tr][0] = left_heading

    lines = ["<table>"]
    for row in grid:
        lines.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def build_reference_markdown(tests: list[dict]) -> str:
    """Return Markdown that should pass every test in `tests` (raw JSONL dicts for one PDF)."""
    present = [t for t in tests if t.get("type") == "present"]
    head = _dedupe(t["text"] for t in present if t.get("first_n") and not t.get("last_n"))
    tail = _dedupe(t["text"] for t in present if t.get("last_n") and not t.get("first_n"))
    body_present = _dedupe(t["text"] for t in present if t["text"] not in head and t["text"] not in tail)

    order_snippets = _dedupe(s for t in tests if t.get("type") == "order" for s in (t["before"], t["after"]))
    maths = _dedupe(t["math"] for t in tests if t.get("type") == "math")
    tables = [t for t in tests if t.get("type") == "table"]

    paragraphs: list[str] = []
    paragraphs.extend(head if head else [FILLER_START])
    paragraphs.extend(body_present)
    paragraphs.extend(order_snippets)
    paragraphs.extend(order_snippets)
    paragraphs.extend(_table_html(t) for t in tables)
    paragraphs.extend(_math_blocks(maths))
    paragraphs.extend(tail if tail else [FILLER_END])
    return "\n\n".join(paragraphs) + "\n"
