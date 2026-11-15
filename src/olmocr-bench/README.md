## olmOCR-Bench → Harbor Adapter

## Overview

olmOCR-Bench evaluates document OCR / PDF linearization: converting a single PDF page into clean,
naturally ordered text (Markdown, with LaTeX math and HTML tables). Instead of comparing against a
gold transcription with edit distance, every page carries a set of small, machine-checkable
**unit tests** (text present / absent, reading order, table cell relationships, math equivalence)
written and verified by the benchmark authors.

- **Source:** AllenAI, [olmOCR](https://github.com/allenai/olmocr) (`olmocr/bench`), data on Hugging Face
  [`allenai/olmOCR-bench`](https://huggingface.co/datasets/allenai/olmOCR-bench); paper
  [arXiv:2502.18443](https://arxiv.org/abs/2502.18443).
- **License:** dataset ODC-BY-1.0; olmocr code Apache-2.0.
- **Size:** 1,403 single-page PDFs and 7,019 unit tests in 7 test files (`arxiv_math`,
  `old_scans_math`, `table_tests`, `old_scans`, `headers_footers`, `multi_column`, `long_tiny_text`):
  3,385 math, 1,061 order, 1,020 table, 823 absent, 721 present, and 9 explicit `baseline`
  (blank-page) tests. `benchmark.py` also adds one `baseline` test to every page that lacks one.
- **This adapter:** **1,403 Harbor tasks — one per PDF page** (every page of the benchmark is
  included). Task ids are the sanitized PDF path, e.g. `arxiv_math/2503.04048_pg46.pdf` →
  `arxiv-math-2503-04048-pg46` (registry name `allenai/olmocr-bench__arxiv-math-2503-04048-pg46`).
- **Main adaptation:** the original benchmark is run by sending a rendered page to an OCR model or VLM
  and storing its Markdown output. In Harbor, an agent receives the PDF in a container and must write
  `/workspace/output.md`; the instruction reuses olmOCR's own transcription prompt
  (`build_openai_silver_data_prompt_v3_simple`). Grading uses the upstream test code unmodified.

## What is olmOCR-Bench?

olmOCR-Bench was released with olmOCR (AllenAI, 2025) to measure how faithfully OCR systems and
vision-language models turn PDF pages into plain text. Pages are drawn from arXiv math papers, old
scanned documents (with and without math), tables, pages with headers/footers, multi-column layouts and
long pages of tiny text. Each test is binary; a test passes if the majority of a page's repeated
generations pass it. The reported **overall score is the mean of the per-file pass rates** of the
seven test files and the `baseline` group (`python -m olmocr.bench.benchmark`), with a bootstrap 95%
confidence interval.

## Adapter Features

- **Pinned, automatic data download** of `allenai/olmOCR-bench` (Hugging Face revision
  `54a96a6f…`) via `huggingface_hub`, or `--data-dir` for a local copy.
- **One task per page**: the PDF is baked into the image at `/workspace/input.pdf`; the page's tests are
  only uploaded at verification time (`tests/tests.jsonl`), so agents never see them.
- **Upstream grader, unmodified**: the task image installs `olmocr` with `--no-deps` from the pinned
  upstream commit `f7cfe4c2` plus the `olmocr[bench]` libraries the tests import (rapidfuzz,
  fuzzysearch, beautifulsoup4, lxml, playwright + Chromium for KaTeX math rendering).
  `tests/run_olmocr_tests.py` mirrors `benchmark.py`'s per-test loop for one page and one repeat,
  including the auto-added `BaselineTest`.
- **Rewards**: `reward.json` holds `reward`, the fraction of the page's tests passed. Per-test results
  with their source test file are written to `/logs/verifier/test_results.json`.
- **Official metric**: `uv run olmocr-bench-aggregate <job-dir>` recomputes olmOCR-Bench's overall score
  (mean of per-JSONL pass rates) and per-file and per-test-type breakdowns from a Harbor job.
- **Oracle**: olmOCR-Bench has no gold transcriptions, so `solution/reference.md` is built from each
  page's tests (`oracle.py`): present texts verbatim, order snippets emitted twice, exact LaTeX in
  display delimiters, and one small HTML table per table test.
- Docker layers are shared by all tasks (only the final `COPY input.pdf` differs).

## Generated Task Structure

```
olmocr-bench/
├── {task_id}/
│   ├── task.toml                 # name allenai/olmocr-bench__{task_id}, source PDF/test files in [metadata]
│   ├── instruction.md            # olmOCR transcription prompt + I/O paths
│   ├── environment/
│   │   ├── Dockerfile            # python:3.11 + pinned olmocr grader + Chromium
│   │   └── input.pdf             # the page to transcribe
│   ├── solution/
│   │   ├── solve.sh              # copies reference.md to /workspace/output.md
│   │   └── reference.md          # reference transcription built from the tests
│   └── tests/
│       ├── test.sh               # runs the grader, always rewrites reward.json
│       ├── run_olmocr_tests.py   # single-page port of benchmark.py's evaluation loop
│       ├── tests.jsonl           # this page's upstream tests, verbatim
│       └── test_sources.json     # test id -> source JSONL file (for the official aggregation)
```

Adapter code:

```
src/olmocr-bench/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_olmocr-bench.yaml
└── src/olmocr_bench/
    ├── __init__.py
    ├── adapter.py        # download + task generation
    ├── oracle.py         # reference Markdown from unit tests
    ├── aggregate.py      # official olmOCR-Bench score from a Harbor job
    ├── main.py           # CLI
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        └── tests/{test.sh, run_olmocr_tests.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle agent (reference solutions)
harbor run -d allenai/olmocr-bench

# A specific agent and model
harbor run -d allenai/olmocr-bench -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating tasks into datasets/olmocr-bench
harbor run -c src/olmocr-bench/run_olmocr-bench.yaml                     # oracle
harbor run -c src/olmocr-bench/run_olmocr-bench.yaml -a <agent> -m "<model>"
harbor run -p datasets/olmocr-bench -a <agent> -m "<model>"

# Official olmOCR-Bench score for a finished job
cd src/olmocr-bench && uv run olmocr-bench-aggregate ../../jobs/<job-name> --expected-tasks 1403

# Resume a previously started job
harbor job resume -p jobs/<job-name>
```

### Running Individual Trial

```bash
harbor trial start -p datasets/olmocr-bench/arxiv-math-2503-04048-pg46
harbor trial start -p datasets/olmocr-bench/arxiv-math-2503-04048-pg46 -a <agent> -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/olmocr-bench
uv sync
uv run olmocr-bench --output-dir ../../datasets/olmocr-bench
```

Flags:
- `--output-dir` — where to write tasks (default `datasets/olmocr-bench` at the repo root)
- `--limit N` — only the first N tasks (sorted by task id)
- `--overwrite` — replace existing task directories
- `--task-ids ID [ID ...]` — only these task ids (or original PDF paths such as `tables/xyz_pg4.pdf`)
- `--data-dir PATH` — use a local copy of olmOCR-bench instead of downloading the pinned revision

## Comparison with Original Benchmark (Parity)

_Parity experiments have not been run yet; the plan (agents, models, runs) is being agreed with the
Harbor team._ Results will be reported as mean ± sample SEM of the official olmOCR-Bench overall score
over ≥2 runs per side.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | overall score (mean of per-JSONL pass rates) | TBD | 1403 (100%) | TBD | TBD |

Reproduction (the agent/runner settings will be filled in once the parity plan is agreed):

```bash
# Original side: allenai/olmocr at commit f7cfe4c22098b154c76b6ec950d1c0a464eecf8d
git clone https://github.com/allenai/olmocr && cd olmocr && git checkout f7cfe4c22098b154c76b6ec950d1c0a464eecf8d
pip install -e .[bench] && playwright install chromium
huggingface-cli download --repo-type dataset --revision 54a96a6fb6a2bd3b297e59869491db4d3625b711 \
  allenai/olmOCR-bench --local-dir ./olmOCR-bench
python -m olmocr.bench.convert <runner> --dir ./olmOCR-bench/bench_data
python -m olmocr.bench.benchmark --dir ./olmOCR-bench/bench_data

# Harbor side (from the adapters repo root)
cd src/olmocr-bench && uv run olmocr-bench --output-dir ../../datasets/olmocr-bench && cd ../..
harbor run -c src/olmocr-bench/run_olmocr-bench.yaml -a <agent> -m "<model>"
cd src/olmocr-bench && uv run olmocr-bench-aggregate ../../jobs/<job-name> --expected-tasks 1403
```

Harbor's own job summary reports the mean per-task `reward` (every page weighted equally). The
number comparable to the original benchmark is the `olmocr-bench-aggregate` overall score.

## Notes & Caveats

- **Metric difference:** Harbor's default aggregate is the mean per-page pass fraction; olmOCR-Bench's
  headline number is the mean of per-test-file pass rates. Use `olmocr-bench-aggregate` for comparisons.
- **Repeats:** olmOCR-Bench can grade several repeated generations per page (majority vote). The
  Harbor adapter grades one output per trial (equivalent to `--repeats 1`, the default of
  `olmocr.bench.convert`).
- **Explicit baseline tests:** 9 pages ship their own `baseline` test (e.g. blank-page checks, or
  `tables/9e6a5b213e4fd5906842ebe6b0c5538e9e7b_pg12.pdf`, whose expected table text is Japanese and whose
  baseline disables the CJK-character check). As in `benchmark.py`, no default baseline is added to
  those pages.
- **Absent tests on empty output:** as upstream, an empty `output.md` still passes `absent` tests
  (only the baseline fails), so empty answers get partial credit on header/footer pages.
- **Math tests** need headless Chromium (KaTeX rendering); it is installed in the task image. Every
  task image is about 1 GB, but the layers are shared across tasks. Under load, Chromium
  occasionally crashes on launch (4 of 1,403 pages in our first full oracle run). Upstream
  `benchmark.py` would abort on that; the Harbor grader relaunches the renderer and retries (up to 3
  times, Playwright errors only), so a browser crash never becomes a 0 score.
- The `olmocr` package is installed from the GitHub tarball of a pinned commit, because the latest
  PyPI release (0.4.27) predates the bench's `table_parsing.py`.

## Installation / Prerequisites

- Docker installed and running
- Harbor CLI: `uv tool install harbor`
- Adapter environment:
  ```bash
  cd src/olmocr-bench
  uv sync
  ```
- About 400 MB of disk for the Hugging Face download and about 400 MB for generated tasks
  (most of it is the PDFs). Optional: set `HF_TOKEN` for faster downloads.
- API keys for the agent/model you run (exported as environment variables)

## Troubleshooting

- **`UnicodeEncodeError` from `harbor` on Windows consoles:** set `PYTHONUTF8=1`.
- **Math tests fail with "Couldn't find a tree builder … xml":** `lxml` is missing from the grading
  environment (it is part of `olmocr[bench]`).
- **Slow first build:** the first task builds the shared Chromium layer; later tasks reuse it. Keep
  `force_build: false`.

## Citation

```bibtex
@misc{olmocrbench,
      title={{olmOCR: Unlocking Trillions of Tokens in PDFs with Vision Language Models}},
      author={Jake Poznanski and Jon Borchardt and Jason Dunkelberger and Regan Huff and Daniel Lin and Aman Rangapur and Christopher Wilhelm and Kyle Lo and Luca Soldaini},
      year={2025},
      eprint={2502.18443},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2502.18443},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yi Lu](mailto:81632945+YiDanielLu@users.noreply.github.com).

**Issues and Contributions:**
- Submit issues and pull requests to the adapters repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
