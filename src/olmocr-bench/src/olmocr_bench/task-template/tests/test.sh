#!/bin/bash
# Grade /workspace/output.md with the upstream olmOCR-Bench unit tests for this page.
set -u

mkdir -p /logs/verifier
# Never trust a reward file left behind by the agent.
rm -f /logs/verifier/reward.json /logs/verifier/reward.txt

python3 /tests/run_olmocr_tests.py \
  --md /workspace/output.md \
  --tests /tests/tests.jsonl \
  --sources /tests/test_sources.json \
  --out-dir /logs/verifier
status=$?

if [ $status -ne 0 ] || [ ! -s /logs/verifier/reward.json ]; then
  echo "Grader failed (exit $status); writing reward 0"
  echo '{"reward": 0.0}' > /logs/verifier/reward.json
  exit 1
fi
exit 0
