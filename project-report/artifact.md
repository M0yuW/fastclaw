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

The existing DOCX, PDF, rendered pages, and image assets are retained only as
historical local artifacts. They have not been regenerated or revalidated after
the current Markdown edits and must not be cited as the current submission.

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
- Stage 2 remains proposed/draft until its implementation and freeze gates pass
  and the protocol is explicitly changed to `frozen` before the first formal
  provider request.
- No API key, benchmark-tenant credential, or local credential-file content may
  enter a thesis source, manifest, generated document, or Git commit.
