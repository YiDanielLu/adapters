"""Grade one olmOCR-Bench page with the upstream olmOCR test classes.

This mirrors `evaluate_candidate()` in olmocr/bench/benchmark.py for a single PDF with a
single repeat: every test for the page (plus the auto-added BaselineTest, exactly as
benchmark.py adds it) is run against the agent's Markdown with `test.run(md_content)`.
The grading logic itself is the unmodified `olmocr` package, installed in the task image
from a pinned upstream commit (see environment/Dockerfile).

Outputs (under /logs/verifier):
  reward.json        {"reward": passed/total}
  test_results.json  per-test results, incl. the source JSONL file of each test, so the
                     official olmOCR-Bench score (mean of per-JSONL pass rates) can be
                     recomputed across tasks with `olmocr-bench-aggregate`

The only addition to upstream behaviour: if headless Chromium (used for KaTeX math rendering)
crashes, the renderer is relaunched and the step retried, so an infrastructure crash does not
turn into a zero score.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from olmocr.bench.katex import render as katex_render
from olmocr.bench.tests import BaselineTest, load_single_test

HERE = Path(__file__).resolve().parent

INFRA_ATTEMPTS = 3


def _is_browser_error(exc: BaseException) -> bool:
    """Playwright/Chromium failures (e.g. a headless shell crashing on launch) are
    infrastructure errors, not grading outcomes."""
    return type(exc).__module__.startswith("playwright")


def _reset_renderer() -> None:
    """Drop the KaTeX renderer's thread pool so the next render launches a fresh Chromium.
    Upstream keeps one browser per executor thread and never relaunches a dead one."""
    old = katex_render._render_executor
    katex_render._render_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="playwright-render")
    old.shutdown(wait=False)


def with_browser_retry(fn, *args):
    """Run fn(*args), retrying only on browser crashes. Grading semantics are unchanged:
    any other exception propagates exactly as it would upstream."""
    for attempt in range(1, INFRA_ATTEMPTS + 1):
        try:
            return fn(*args)
        except Exception as e:
            if not _is_browser_error(e) or attempt == INFRA_ATTEMPTS:
                raise
            print(f"Browser error (attempt {attempt}/{INFRA_ATTEMPTS}), relaunching: {str(e).splitlines()[0][:200]}")
            _reset_renderer()
            time.sleep(2 * attempt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", default="/workspace/output.md")
    parser.add_argument("--tests", default=str(HERE / "tests.jsonl"))
    parser.add_argument("--sources", default=str(HERE / "test_sources.json"))
    parser.add_argument("--out-dir", default="/logs/verifier")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    tests = []
    for line in Path(args.tests).read_text(encoding="utf-8").splitlines():
        if line.strip():
            tests.append(with_browser_retry(load_single_test, line))

    # benchmark.py adds one BaselineTest per PDF that has none (it is reported under "baseline").
    pdfs = sorted({t.pdf for t in tests})
    for pdf in pdfs:
        if not any(t.type == "baseline" for t in tests if t.pdf == pdf):
            tests.append(BaselineTest(id=f"{pdf}_baseline", pdf=pdf, page=1, type="baseline"))
            sources[tests[-1].id] = "baseline"

    md_path = Path(args.md)
    md_content = None
    read_error = None
    if not md_path.is_file():
        read_error = f"Missing output file {md_path}"
    else:
        try:
            md_content = md_path.read_text(encoding="utf-8")
        except Exception as e:  # mirrors benchmark.py: an unreadable file fails every test
            read_error = f"Error reading {md_path}: {e}"

    results = []
    for test in tests:
        if md_content is None:
            passed, explanation = False, read_error
        else:
            try:
                passed, explanation = with_browser_retry(test.run, md_content)
            except Exception as e:  # benchmark.py counts an exception as a failed repeat
                passed, explanation = False, f"Error running test {test.id}: {e}"
        results.append(
            {
                "id": test.id,
                "pdf": test.pdf,
                "page": test.page,
                "type": test.type,
                "jsonl": sources.get(test.id, "unknown"),
                "passed": bool(passed),
                "explanation": explanation,
            }
        )

    n_tests = len(results)
    n_passed = sum(r["passed"] for r in results)
    reward = n_passed / n_tests if n_tests else 0.0

    (out_dir / "test_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "reward.json").write_text(json.dumps({"reward": reward}), encoding="utf-8")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['type']:9s} {r['id']} {'' if r['passed'] else '- ' + str(r['explanation'])[:200]}")
    print(f"olmOCR-Bench page score: {n_passed}/{n_tests} = {reward:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
