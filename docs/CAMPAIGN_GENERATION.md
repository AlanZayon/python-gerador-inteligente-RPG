# Campaign generation

This note is a **pointer**. The full bilingual system manual is:

- Portuguese: [docs/pt/README.md](pt/README.md)
- English: [docs/en/README.md](en/README.md)

Pipeline in one sentence: PDF → fingerprint/FAISS → packed lanes → JSON campaign plan (Campaign State) → overview + per-session write + appendix → heuristic rubric → selective H2 revision → structural validator → S3.

Why not a multi-agent crew: the critic is a **deterministic rubric + bounded splice**, which is cheaper to test than extra LLM roles. JSON plan failure falls back to the legacy full-manuscript prompt so jobs still complete.

Live eval (four books × three complexities) and evidence slots: [docs/pt/08-avaliacao.md](pt/08-avaliacao.md) · [docs/en/08-evaluation.md](en/08-evaluation.md) · [docs/evidence/README.md](evidence/README.md).
