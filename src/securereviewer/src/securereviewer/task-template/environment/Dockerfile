FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/usr/share/nltk_data

# SecureBLEU dependencies (used by the verifier): nltk tokenizer, WordNet synonyms/lemmatizer
# and the perceptron POS tagger.
RUN pip install nltk==3.9.1 && \
    python -m nltk.downloader -d /usr/share/nltk_data wordnet omw-1.4 averaged_perceptron_tagger_eng

# SecureReviewer's scoring script, unmodified, from the pinned upstream commit.
ARG SECUREREVIEWER_COMMIT=86df98bf8e0a4057cb4d89490cde400359af290d
ADD https://raw.githubusercontent.com/SIMIAO515/SecureReviewer/${SECUREREVIEWER_COMMIT}/evaluate/SecureBleu.py /opt/securereviewer/SecureBleu.py

WORKDIR /workspace
COPY patch.diff /workspace/patch.diff
