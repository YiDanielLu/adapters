"""Generate Harbor tasks from olmOCR-Bench (allenai/olmOCR-bench on Hugging Face).

One Harbor task per benchmark PDF (every PDF is a single page). The agent sees only
the PDF at /workspace/input.pdf and must write /workspace/output.md. The verifier runs
the page's upstream unit tests (plus olmOCR's auto-added baseline test) with the
vendored, unmodified olmOCR grading code.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from .oracle import build_reference_markdown

HF_REPO_ID = "allenai/olmOCR-bench"
# Pinned dataset revision (Hugging Face commit) so task contents are reproducible.
HF_REVISION = "54a96a6fb6a2bd3b297e59869491db4d3625b711"
# Upstream olmocr commit the grading code under task-template/tests/olmocr_grader was copied from.
OLMOCR_COMMIT = "f7cfe4c22098b154c76b6ec950d1c0a464eecf8d"

ORG = "allenai"
DATASET = "olmocr-bench"

JSONL_FILES = [
    "arxiv_math.jsonl",
    "headers_footers.jsonl",
    "long_tiny_text.jsonl",
    "multi_column.jsonl",
    "old_scans.jsonl",
    "old_scans_math.jsonl",
    "table_tests.jsonl",
]

TEMPLATE_DIR = Path(__file__).parent / "task-template"


def task_id_for_pdf(pdf_rel: str) -> str:
    """Stable, registry-safe task id from the PDF path relative to bench_data/pdfs."""
    stem = pdf_rel[:-4] if pdf_rel.lower().endswith(".pdf") else pdf_rel
    tid = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return tid


def download_bench_data(data_dir: Path | None = None) -> Path:
    """Return the local `bench_data` directory, downloading the pinned snapshot if needed."""
    if data_dir is not None:
        bench = Path(data_dir)
        if (bench / "bench_data").is_dir():
            bench = bench / "bench_data"
        if not (bench / "pdfs").is_dir():
            raise FileNotFoundError(f"{bench} does not look like olmOCR-bench bench_data (no pdfs/ folder)")
        return bench

    from huggingface_hub import snapshot_download

    root = snapshot_download(
        repo_id=HF_REPO_ID,
        repo_type="dataset",
        revision=HF_REVISION,
        allow_patterns=["bench_data/*.jsonl", "bench_data/pdfs/**"],
    )
    return Path(root) / "bench_data"


def load_tests_by_pdf(bench_dir: Path) -> dict[str, list[tuple[str, dict]]]:
    """Map PDF path -> list of (source jsonl name, raw test dict), in file order."""
    by_pdf: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for name in JSONL_FILES:
        path = bench_dir / name
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                by_pdf[data["pdf"]].append((name, data))
    return dict(by_pdf)


class OlmOCRBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_dir: Path | None = None,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.data_dir = data_dir

    def run(self) -> None:
        bench_dir = download_bench_data(self.data_dir)
        tests_by_pdf = load_tests_by_pdf(bench_dir)

        pdfs = sorted(tests_by_pdf)
        ids = {pdf: task_id_for_pdf(pdf) for pdf in pdfs}
        if len(set(ids.values())) != len(ids):
            raise RuntimeError("Task id collision after sanitizing PDF names")

        selected = [p for p in pdfs if self.task_ids is None or ids[p] in self.task_ids or p in self.task_ids]
        if self.limit is not None:
            selected = selected[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = skipped = 0
        for pdf in selected:
            task_dir = self.output_dir / ids[pdf]
            if task_dir.exists():
                if not self.overwrite:
                    skipped += 1
                    continue
                shutil.rmtree(task_dir)
            self._write_task(task_dir, ids[pdf], pdf, tests_by_pdf[pdf], bench_dir)
            written += 1
        print(f"Wrote {written} tasks to {self.output_dir} (skipped {skipped} existing; {len(pdfs)} PDFs in benchmark)")

    def _write_task(self, task_dir: Path, task_id: str, pdf: str, tests: list[tuple[str, dict]], bench_dir: Path) -> None:
        shutil.copytree(TEMPLATE_DIR, task_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        raw_tests = [t for _, t in tests]
        sources = {t["id"]: src for src, t in tests}
        source_jsonl = sorted(set(sources.values()))
        test_types = sorted({t["type"] for t in raw_tests})
        category = pdf.split("/", 1)[0]

        # task.toml
        toml_path = task_dir / "task.toml"
        toml = toml_path.read_text(encoding="utf-8")
        toml = (
            toml.replace("{task_name}", f"{ORG}/{DATASET}__{task_id}")
            .replace("{category}", category)
            .replace("{n_tests}", str(len(raw_tests) + (0 if "baseline" in test_types else 1)))
            .replace("{source_pdf}", pdf)
            .replace("{source_jsonl}", json.dumps(source_jsonl))
            .replace("{test_types}", json.dumps(test_types))
        )
        toml_path.write_text(toml, encoding="utf-8")

        # environment: the page itself
        shutil.copyfile(bench_dir / "pdfs" / pdf, task_dir / "environment" / "input.pdf")

        # tests: this page's upstream tests, verbatim, plus their source JSONL
        with (task_dir / "tests" / "tests.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for t in raw_tests:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        (task_dir / "tests" / "test_sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")

        # solution: reference markdown built from the tests
        (task_dir / "solution" / "reference.md").write_text(build_reference_markdown(raw_tests), encoding="utf-8", newline="\n")
        _fix_line_endings(task_dir)


def _fix_line_endings(task_dir: Path) -> None:
    """Shell scripts must keep LF endings even when generated on Windows."""
    for sh in task_dir.rglob("*.sh"):
        data = sh.read_bytes().replace(b"\r\n", b"\n")
        sh.write_bytes(data)
