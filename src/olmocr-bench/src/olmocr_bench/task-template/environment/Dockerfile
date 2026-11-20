FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Agent environment: only the page to transcribe. The grader lives in its own image
# (tests/Dockerfile) and never shares a container with the agent.
WORKDIR /workspace

# The single-page PDF to transcribe.
COPY input.pdf /workspace/input.pdf
