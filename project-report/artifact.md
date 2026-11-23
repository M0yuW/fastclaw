# FastClaw Project Report Template Contract

## Reference

- Reference DOCX: `/Users/wangzheyu/Downloads/ieee_financial_analysis_assistant_verified.docx`
- SHA-256: `1a4982799fc15fe2f1ccc8ae73f72a812612499467b3e6f59a84062ae5569fdc`
- Reference render: `/tmp/fastclaw-report-template-render`
- Reference page count: 8 (template only; final report length is content-driven)
- Section count: 1

## Page System

- US Letter portrait, 8.5 × 11 inches.
- Margins: 0.60 inches left/right, 0.75 inches top/bottom.
- Single continuous body column.
- Header distance and footer distance follow the retained reference section.
- The fictional conference header and IEEE copyright footer are not fidelity
  requirements. They must be replaced because this is a university project
  report, not an accepted IEEE publication.

## Typography

- Primary family: Times New Roman.
- Title: centered, 24 pt, bold, approximately 12 pt before and 6 pt after.
- Author: centered, 11 pt.
- Affiliation and email: centered, 9 pt, italic.
- Abstract and index terms: 9 pt, justified; labels bold italic.
- Level-1 section headings: centered, 10 pt, bold, uppercase Roman numbering.
- Level-2 headings: left aligned, 10 pt, bold italic, alphabetic numbering.
- Level-3 headings: left aligned, 9.5–10 pt, italic.
- Body: 10 pt, justified, single spacing, approximately 6 pt after.
- Captions: centered, 8.5–9 pt.
- References: 9 pt, justified, 0.18 inch hanging indent.

## Tables and Figures

- Tables use explicit widths within the 7.30-inch usable page width.
- Header cells use a light gray fill and bold text.
- Numeric columns are centered; narrative columns are left aligned.
- No fixed row heights.
- Figures are centered high-resolution PNGs with captions immediately below.
- Captions and figures should remain together where pagination allows.

## Content Flow

1. Title, author, affiliation, abstract, and index terms.
2. Introduction and contributions.
3. Background and design requirements.
4. FastClaw system architecture.
5. Agent runtime execution mechanism.
6. Financial research application.
7. Evaluation methodology.
8. Experimental results and discussion.
9. Security, limitations, and future work.
10. Conclusion and references.

## Editable Slots

- Replace all retained body text. The reference contains placeholders and
  unverified architecture and benchmark claims.
- Replace the title and author block.
- Replace both retained tables with evidence-backed runtime and test tables.
- Add architecture, turn-sequence, and finance-workflow figures.
- Remove all fictional OpenClaw, RAG, Redis, Qdrant, gVisor, proprietary
  RCQ-500, FinQA score, throughput, and red-team result claims that are not
  implemented or evidenced in the current FastClaw repository.
- Preserve the reference page size, margins, general hierarchy, font family,
  compact academic rhythm, and caption treatment.

## Authoritative Technical Evidence

- Repository branch: `codex/finance-agent-runtime`, based on `m0yuw-project`.
- Source architecture: `cmd/fastclaw`, `internal/gateway`, `internal/agent`,
  `internal/bus`, `internal/taskqueue`, `internal/provider`,
  `internal/session`, `internal/store`, `internal/plugin`, `internal/eval`.
- Financial application: `plugins/finance-tools`, `FINANCE-RUNTIME.md`,
  `evals/multiagent-finance-workflow.yaml`.
- Historical runtime experiment reports: `runtime-pilot.json` and
  `runtime-pilot-optimized-v2.json`.
- Frozen financial confirmation: `finance-runtime-formal-r5.json`, suite
  `evals/multiagent-finance-runtime.yaml`, and narrative report
  `evals/finance-runtime-formal-r5.md`.
- Review evidence: `CLAUDE-REVIEW-FINDINGS-finance-runtime-2026-08-01.md`
  and `CLAUDE-REVIEW-RESOLUTION-finance-runtime-2026-08-01.md`.
- Test evidence is regenerated from the dirty review-remediation tree before
  the DOCX/PDF artifacts are accepted; stale coverage percentages are not used.

## Fidelity Gates

- Retained reference remains byte-for-byte unchanged.
- Final document uses no fictional conference or copyright claim.
- No placeholder text remains.
- No claim is presented as an official BFCL, τ-bench, SWE-bench, or
  MultiAgentBench score.
- Historical two-baseline runtime metrics are explicitly labelled and not
  compared directly with the current four-mode attempt-cost definition.
- Financial evaluation is described as evidence-handling and orchestration
  evaluation, not return prediction or alpha measurement.
- Every page must render without clipping, overlap, orphaned captions, or
  unreadable tables.

## Final Generated Artifacts

- DOCX: `FastClaw_Project_Report_Zheyu_Wang.docx`, 20 rendered pages,
  SHA-256 `c42d1403d28fdefcc0524833fb6d02eeaa663276cbed255da9451d61649bdad5`.
- PDF: `FastClaw_Project_Report_Zheyu_Wang.pdf`, 20 US Letter pages,
  SHA-256 `98f8f5ad540b1271435ffef9268fd6460b85d2eb3d446b98e9482f17bbe3edba`.
- Visual QA: every final PDF page inspected; no clipping, overlap, unreadable
  table, orphaned caption, or forced blank page remained.
