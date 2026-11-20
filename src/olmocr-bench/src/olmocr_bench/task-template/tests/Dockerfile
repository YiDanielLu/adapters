FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

# Verifier image (separate from the agent). It holds the upstream olmOCR-Bench test code
# (olmocr/bench/tests.py and helpers), installed unmodified from a pinned olmocr commit,
# plus the olmocr[bench] dependencies it imports. Chromium is needed by the KaTeX
# renderer behind the math tests. These layers are identical for every task, so Docker
# reuses them; only the final COPY of this page's tests differs.
ARG OLMOCR_COMMIT=f7cfe4c22098b154c76b6ec950d1c0a464eecf8d
RUN pip install \
      fuzzysearch==0.8.0 \
      rapidfuzz==3.14.3 \
      tqdm==4.67.1 \
      beautifulsoup4==4.13.5 \
      lxml==6.0.2 \
      playwright==1.55.0 \
    && pip install --no-deps "https://github.com/allenai/olmocr/archive/${OLMOCR_COMMIT}.tar.gz" \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# This page's tests and the grading scripts. The agent's /workspace/output.md arrives
# as a declared artifact (see task.toml).
COPY . /tests/
RUN chmod +x /tests/test.sh
