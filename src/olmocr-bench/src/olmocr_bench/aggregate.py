"""Recompute the official olmOCR-Bench score from a Harbor job directory.

Harbor averages the per-task `reward` (fraction of a page's tests passed). olmOCR-Bench
instead reports the mean of per-JSONL-file pass rates (7 test files + the auto-added
"baseline" group), as printed by `python -m olmocr.bench.benchmark`. This script reads
every trial's verifier/test_results.json and applies benchmark.py's aggregation.

Usage:
    uv run olmocr-bench-aggregate jobs/<job-name> [--expected-tasks 1403]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def aggregate(job_dir: Path) -> dict:
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})
    seen_pdfs: set[str] = set()
    n_files = 0
    for results_path in sorted(job_dir.rglob("verifier/test_results.json")):
        results = json.loads(results_path.read_text(encoding="utf-8"))
        if not results:
            continue
        pdf = results[0]["pdf"]
        if pdf in seen_pdfs:
            # one result per page; repeated trials of a task belong in separate jobs
            raise SystemExit(f"Duplicate results for {pdf} in {job_dir}; aggregate one attempt per task")
        seen_pdfs.add(pdf)
        n_files += 1
        for r in results:
            groups[r["jsonl"]]["total"] += 1
            by_type[r["type"]]["total"] += 1
            if r["passed"]:
                groups[r["jsonl"]]["passed"] += 1
                by_type[r["type"]]["passed"] += 1

    per_jsonl = {k: v["passed"] / v["total"] for k, v in sorted(groups.items()) if v["total"]}
    overall = sum(per_jsonl.values()) / len(per_jsonl) if per_jsonl else 0.0
    return {
        "n_tasks": n_files,
        "overall": overall,
        "per_jsonl": per_jsonl,
        "per_jsonl_counts": {k: dict(v) for k, v in sorted(groups.items())},
        "per_test_type": {k: v["passed"] / v["total"] for k, v in sorted(by_type.items()) if v["total"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--expected-tasks", type=int, default=None, help="Warn if fewer graded tasks were found")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    res = aggregate(args.job_dir)
    if args.json:
        print(json.dumps(res, indent=2))
        return
    if args.expected_tasks and res["n_tasks"] < args.expected_tasks:
        print(f"WARNING: only {res['n_tasks']}/{args.expected_tasks} tasks have verifier results; missing tasks are not counted")
    print(f"Graded tasks: {res['n_tasks']}")
    print(f"olmOCR-Bench overall (mean of per-JSONL pass rates): {res['overall'] * 100:.1f}%")
    for name, rate in res["per_jsonl"].items():
        c = res["per_jsonl_counts"][name]
        print(f"  {name:24s} {rate * 100:5.1f}%  ({c['passed']}/{c['total']})")
    print("Per test type:")
    for name, rate in res["per_test_type"].items():
        print(f"  {name:10s} {rate * 100:5.1f}%")


if __name__ == "__main__":
    main()
