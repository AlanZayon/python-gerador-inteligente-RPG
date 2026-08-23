# System documentation

This folder is the canonical description of the **backend**: a Flask API, Redis worker, RAG index, and plan → write → score → revise campaign pipeline. A Vue UI exists only as a **demonstration harness** (upload, poll, download). It is not the product.

| Language | Start here |
|---|---|
| Português | [pt/README.md](pt/README.md) |
| English | [en/README.md](en/README.md) |

Evidence (screenshots, excerpts, traces) lives in [`evidence/`](evidence/README.md). Markdown chapters already point at those filenames — drop files in place and the docs render.

Do **not** commit rulebook PDFs or full generated campaigns. Keep them on disk locally; cite them from `examples/eval_runs/` in the evidence slots.
