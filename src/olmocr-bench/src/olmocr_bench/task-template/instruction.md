Transcribe the single-page PDF at `/workspace/input.pdf` into Markdown and save the result to `/workspace/output.md` (UTF-8).

Return the plain text representation of the page as if you were reading it naturally:

- Turn equations and math symbols into a LaTeX representation. Use `\(` and `\)` as delimiters for inline math, and `\[` and `\]` for block math. Do not use ASCII or Unicode math symbols such as ∈ ∉ ⊂ ⊃ ⊆ ⊇ ∅ ∪ ∩ ∀ ∃ ¬; use LaTeX syntax instead, e.g. `\( \in \)`, `\( \notin \)`.
- Convert tables into HTML format. Keep the syntax simple, but use `<th>` for header rows, and use `rowspan` and `colspan` appropriately. Don't use `<br>` inside table cells; split that into new rows as needed. Do not use LaTeX or Markdown table syntax.
- Remove the page headers and footers (running titles, page numbers, etc.), but keep references and footnotes.
- Read any natural handwriting.
- If there are any figures or charts, label them with Markdown image syntax: `![Alt text describing the contents of the figure](figure.png)`.
- This is likely one page out of several in the document, so preserve any sentences that come from the previous page or continue onto the next page exactly as they are.
- Do not hallucinate. If there is no text at all on the page that should be read, write an empty `/workspace/output.md`.

Only `/workspace/output.md` is graded.
