# Stage 2 freeze audit

Two reviewers independently work in `reviewer-a.csv` and `reviewer-b.csv`; each row contains the task context needed for review. `audit-tasks.csv` is the immutable shared task set.

- Source tasks include the claimed excerpt and SEC URL. Transcribe the independently verified value, unit, basis, and period into `independent_result`.
- Calculation tasks include input facts and the operation but hide the expected result. Record the arithmetic and rounded result in `independent_result`.
- Evidence-group tasks include record locators and text previews. Record `VALID` or list suspect record IDs in `independent_result`.
- Allowed verdicts are `PASS`, `FAIL`, and `NOT_ASSESSABLE`; add a concise note for any non-PASS verdict.
- Do not open `machine-reference.csv` until both reviewer files are complete. Any disagreement, failure, or not-assessable item requires documented adjudication before freeze.
- 中文审阅界面可直接用浏览器打开 `review.html`。页面含按任务类型展开的字段说明，草稿只保存在浏览器本地，并可导出兼容的 reviewer CSV。
