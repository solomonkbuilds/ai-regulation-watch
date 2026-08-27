# AI Regulation Watch

An automated agent that monitors regulatory and standards bodies for changes and specifically flags updates related to AI disclosure obligations, AI risk management requirements, and AI development/model governance oversight.

## Why this exists

Regulatory standards (NIST, ISO, EU AI Act, and others) are increasingly
adding AI-specific provisions, but compliance teams have no automated way to detect when a standard changes and whether that change touches AI. This
project monitors a defined set of sources, detects meaningful changes, and
uses an LLM to classify and summarize whether each change is AI-relevant —
with its classification accuracy validated against a hand-labeled test set
(see [`docs/evaluation.md`](docs/evaluation.md)).

## Architecture

```
Sources → Ingestion → Change Detection → AI Classification → Storage → Dashboard / Alerts
```

1. **Ingestion** (`src/ingest.py`) — fetches each configured source (HTML or PDF) and normalizes it to plain text.
2. **Change detection** (`src/diff_detect.py`) — hashes and diffs the new
   content against the last stored snapshot; filters out trivial noise
   (e.g. a single date changing).
3. **Classification** (`src/classify.py`) — sends non-trivial diffs to Claude, which returns a structured summary + AI-relevance classification.
4. **Storage** (`src/storage.py`) — SQLite database of every source, snapshot,
   and detected change.
5. **Presentation** (`dashboard/app.py`) — Streamlit dashboard for browsing
   and filtering detected changes.

Automation runs on a daily schedule via GitHub Actions
(`.github/workflows/monitor.yml`), which commits the updated database back to the repo so the commit history itself becomes a visible audit trail of
regulatory changes over time.

## Monitored sources (MVP)

| Source | What it covers | Classified by Claude? |
|---|---|---|
| NIST AI Risk Management Framework | Voluntary US AI risk framework | Yes |
| ISO/IEC 42001:2023 | International AI management system standard | No — see below |

Add or remove sources in `config/sources.yaml` — no code changes required for a standard HTML source.

### Why ISO sources skip AI classification

iso.org's site terms explicitly prohibit using their content to train or
prompt AI/ML systems. This pipeline still monitors both ISO pages —
fetching, hashing, and diffing them like any other source — but deliberately **skips sending their diff text to the Claude API**. Detected changes on these sources are stored and surfaced in the dashboard flagged for manual review instead of an automated summary/classification.

This is enforced by a `skip_classification: true` flag per source in
`config/sources.yaml`, read by the orchestrator (`src/main.py`) independent
of any CLI flags — so it can't be accidentally overridden by a run
configuration. It's also a small but deliberate design choice worth calling
out: a compliance-monitoring tool that itself ignores a source's usage terms would be a bad look, so the pipeline is built to respect that constraint by default rather than as an afterthought.

Note also that ISO's public pages are marketing/overview pages, not the
purchasable standard text itself — so expect infrequent, high-level changes
(status, edition, related publications) rather than clause-level detail.
