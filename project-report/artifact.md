# FastClaw Project Report Artifact Status

## Authority

This file is an archival status note, not an authoritative source for thesis
claims, page count, layout constants, repository state, or experiment results.
The previous version described a superseded 20-page build and stale artifact
hashes. Those values have been intentionally removed rather than carried into
the current content-editing phase.

Until the Markdown content is frozen, use the following evidence hierarchy:

1. `fastclaw_project_report.md` for the current thesis text and claim wording;
2. the frozen experiment JSON, suite, source lock, and secret-free manifests for
   experimental facts;
3. repository source and tests for implementation claims; and
4. `build_report.py` for document-generation settings.

The DOCX was regenerated from the Markdown on 2026-10-23 after the preliminary
thesis actionability correction was documented and visually checked from a
temporary render. The PDF in this directory was not regenerated and remains historical;
do not cite it as the current submission. The Markdown remains authoritative
while content is being edited.

## Content Freeze Rule

Do not update page counts, typography claims, or DOCX/PDF hashes here while the
thesis content is changing. After the Markdown is frozen, the document build
must regenerate the artifacts, render every page, verify visual integrity, and
create a machine-generated manifest containing the actual page count, source
hash, artifact hashes, build environment, and build timestamp.

## Experiment Boundaries

- `finance-runtime-formal-r5.json` is a fixed-evidence, one-repetition,
  post-fix confirmation with a dirty execution tree; its exact provider
  trajectory is not reproducible from the recorded HEAD alone.
- The retained SEC retrieval result is a one-case descriptive pilot, not a
  confirmatory study.
- Stage 2A v2 main and all-Flash experiments are completed and retained in their
  result directories; the optional 24-observation all-Pro ablation was not run.
- The single live Nasdaq Skill-to-ledger observation is exploratory. Its raw
  score was `needs_review` because of two scorer false negatives; the retained
  read-only adjudication verifies the execution path, provenance, arithmetic,
  and ledger write. It does not certify prose or investment value. The
  price-only thesis was historically returned as available without a decision
  hold, so it must not be treated as actionable evidence. A later deterministic
  serializer correction returns `research_only` for preliminary theses, but
  has not been tested in a new model-backed workflow panel.
- No API key, benchmark-tenant credential, or local credential-file content may
  enter a thesis source, manifest, generated document, or Git commit.
