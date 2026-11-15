## SecureReviewer → Harbor Adapter

## Overview

SecureReviewer evaluates **secure code review**: given a code change (a diff hunk from a real
open-source pull request), write a review comment that identifies the security issue it introduces.
Each review has four parts, R = (ST, D, I, A): **Security type** (one of 7 categories), **Description**,
**Impact** and **Advice**. Reviews are scored against an expert-refined reference with **SecureBLEU**,
the paper's metric that combines BLEU-4 per section with security-keyword overlap.

- **Source:** [SIMIAO515/SecureReviewer](https://github.com/SIMIAO515/SecureReviewer) (ICSE 2026);
  paper [arXiv:2510.26457](https://arxiv.org/abs/2510.26457).
- **License:** the upstream repository does not include a license file; the data is derived from the
  CodeReviewer dataset (Microsoft).
- **Size:** the test split (`dataset/test.jsonl`) has 300 items: 261 with a security issue and 39 labelled
  `No Issue`.
- **This adapter:** **261 Harbor tasks, one per test item with a security issue.** SecureBLEU's
  `process_jsonl` skips every item whose reference is `No Issue`, so those 39 items never contribute to
  the benchmark score and are left out. Task ids are the 0-based line number in `test.jsonl`, e.g.
  `test-000` (registry name `securereviewer/securereviewer__test-000`).
- **Main adaptation:** upstream, a model is prompted once per item and its output is parsed into the four
  sections. In Harbor, an agent receives the same prompt with the diff (also at `/workspace/patch.diff`)
  and writes the review to `/workspace/review.txt`. Grading runs the upstream `SecureBleu.py`
  unmodified.

## What is SecureReviewer?

SecureReviewer (Liu et al., ICSE 2026) builds a dataset of security-related code review comments mined
from CodeReviewer and refined into the (ST, D, I, A) format; the test split was manually refined by
security experts. The security types are Input Validation, Exception Handling, Type and Data Handling,
Concurrency, Access Control and Information Security, Error State Management and Resource Management.

**SecureBLEU** scores one item as `0.5 × weighted BLEU + 0.5 × 100 × keyword overlap`:
- weighted BLEU = 0.3 × (exact security-type match ? 100 : 0) + 0.3 × BLEU(description) +
  0.2 × BLEU(impact) + 0.2 × BLEU(advice);
- keyword overlap = how many of the security keywords (type-specific and common lists, matched with WordNet
  lemmas/synonyms) and `code` spans in each reference section also appear in the predicted section;
- a prediction of `No Issue` for an item with an issue scores 0.

The benchmark score is the mean over items (`Average BLEU score` printed by `evaluate/SecureBleu.py`).

## Adapter Features

- **Pinned data**: `dataset/test.jsonl` is downloaded from upstream commit `86df98bf` (or pass
  `--data-file`).
- **Upstream scorer, unmodified**: the task image fetches `evaluate/SecureBleu.py` from the same pinned
  commit. `tests/grade.py` parses the review with the upstream `parse_security_review` (copied verbatim
  from `infer/test.py`), writes a one-line `result.jsonl` and executes `SecureBleu.py` on it.
- **Reward**: `reward = SecureBLEU / 100` for the item, so **Harbor's mean reward × 100 is the upstream
  benchmark score** (every item is weighted equally upstream too). `/logs/verifier/details.json` also holds
  the parsed review, the type match and the scorer's log.
- **Hidden reference**: the reference review is only uploaded at verification time (`tests/reference.json`).
- **Oracle**: writes the expert-refined reference comment (`solution/review.txt`).

## Generated Task Structure

```
securereviewer/
├── test-{index}/
│   ├── task.toml                 # name securereviewer/securereviewer__test-{index}; source index + type in [metadata]
│   ├── instruction.md            # upstream review prompt + the diff + output format
│   ├── environment/
│   │   ├── Dockerfile            # python:3.11 + nltk 3.9.1 (+ WordNet, POS tagger) + pinned SecureBleu.py
│   │   └── patch.diff            # the code change
│   ├── solution/
│   │   ├── solve.sh              # copies review.txt to /workspace/review.txt
│   │   └── review.txt            # reference review comment
│   └── tests/
│       ├── test.sh               # runs grade.py, always rewrites reward.json
│       ├── grade.py              # parse review + run upstream SecureBleu.py on this item
│       └── reference.json        # reference fields for this item
```

Adapter code:

```
src/securereviewer/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_securereviewer.yaml
└── src/securereviewer/
    ├── __init__.py
    ├── adapter.py        # download + task generation
    ├── main.py           # CLI
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile
        ├── solution/solve.sh
        └── tests/{test.sh, grade.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
# Oracle agent (reference solutions)
harbor run -d securereviewer/securereviewer

# A specific agent and model
harbor run -d securereviewer/securereviewer -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating tasks into datasets/securereviewer
harbor run -c src/securereviewer/run_securereviewer.yaml                     # oracle
harbor run -c src/securereviewer/run_securereviewer.yaml -a <agent> -m "<model>"
harbor run -p datasets/securereviewer -a <agent> -m "<model>"

# Resume a previously started job
harbor job resume -p jobs/<job-name>
```

### Running Individual Trial

```bash
harbor trial start -p datasets/securereviewer/test-000
harbor trial start -p datasets/securereviewer/test-000 -a <agent> -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/securereviewer
uv sync
uv run securereviewer --output-dir ../../datasets/securereviewer
```

Flags:
- `--output-dir` — where to write tasks (default `datasets/securereviewer` at the repo root)
- `--limit N` — only the first N tasks
- `--overwrite` — replace existing task directories
- `--task-ids ID [ID ...]` — only these task ids (e.g. `test-000`)
- `--data-file PATH` — use a local copy of `dataset/test.jsonl` instead of downloading the pinned one

## Comparison with Original Benchmark (Parity)

_Parity experiments have not been run yet; the plan (agents, models, runs) is being agreed with the
Harbor team._ Results will be reported as mean ± sample SEM of the SecureBLEU score over ≥2 runs per side.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | SecureBLEU (mean over items) | TBD | 261 (100% of scored items) | TBD | TBD |

Reproduction (the agent/runner settings will be filled in once the parity plan is agreed):

```bash
# Original side: SIMIAO515/SecureReviewer at commit 86df98bf8e0a4057cb4d89490cde400359af290d
git clone https://github.com/SIMIAO515/SecureReviewer && cd SecureReviewer && git checkout 86df98bf8e0a4057cb4d89490cde400359af290d
# Generate predictions for dataset/test.jsonl into evaluate/result.jsonl
# (fields "Security Type", "Description", "Impact", "Advice"; see infer/test.py)
cd evaluate && python SecureBleu.py

# Harbor side (from the adapters repo root)
cd src/securereviewer && uv run securereviewer --output-dir ../../datasets/securereviewer && cd ../..
harbor run -c src/securereviewer/run_securereviewer.yaml -a <agent> -m "<model>"
# SecureBLEU = mean reward x 100
```

## Notes & Caveats

- **Oracle ceiling is below 100.** The reference review gets BLEU 100 on every section and the exact
  type, but the keyword-overlap half of SecureBLEU averages six ratios with fixed weights, and a ratio is
  0 (not skipped) when the reference section has no keywords or no `code` spans to match. So even the
  reference scores below 100 on most items: the oracle's mean SecureBLEU is **80.73** (5 of 261 items reach
  100; minimum 52.5). In the Harbor oracle run (261 trials, 0 exceptions, mean reward 0.807), every task's
  reward equals that item's maximum achievable score, computed by running `SecureBleu.py` on the reference
  review outside Harbor.
- **`No Issue` items are excluded** (39 of 300), because SecureBLEU never scores them.
- **Missing sections**: if a section header is missing, the section is scored as empty (upstream stores
  `None`, which crashes `SecureBleu.py`); a missing Security type counts as `No Issue` (score 0), as in
  `infer/test.py`. An empty or missing `review.txt` scores 0.
- `Error State Management` has no type-specific keyword list in `SecureBleu.py` (its list is named
  `State Management`), so only the common keywords count for those 46 items. This is upstream behaviour
  and is kept.
- **nltk version**: upstream does not pin nltk; the image uses nltk 3.9.1 with the `wordnet`, `omw-1.4` and
  `averaged_perceptron_tagger_eng` data.

## Installation / Prerequisites

- Docker installed and running
- Harbor CLI: `uv tool install harbor`
- Adapter environment:
  ```bash
  cd src/securereviewer
  uv sync
  ```
- API keys for the agent/model you run (exported as environment variables)

## Troubleshooting

- **`UnicodeEncodeError` from `harbor` on Windows consoles:** set `PYTHONUTF8=1`.
- **`Resource ... not found` from nltk in the verifier:** the nltk data is baked into the image under
  `/usr/share/nltk_data`; rebuild the image if it was built from an older Dockerfile.

## Citation

```bibtex
@misc{liu2025securereviewer,
      title={{SecureReviewer: Enhancing Large Language Models for Secure Code Review through Secure-aware Fine-tuning}},
      author={Fang Liu and Simiao Liu and Yinghao Zhu and Xiaoli Lian and Li Zhang},
      year={2025},
      eprint={2510.26457},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2510.26457},
}
```

## Authors & Contributions

This adapter is developed and maintained by [Yi Lu](mailto:81632945+YiDanielLu@users.noreply.github.com).

**Issues and Contributions:**
- Submit issues and pull requests to the adapters repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
