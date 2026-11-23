#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/project-report"
RUNTIME_ROOT="${CODEX_PRIMARY_RUNTIME:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies}"
PYTHON_BIN="${PYTHON_BIN:-$RUNTIME_ROOT/python/bin/python3}"
PYTHON_PACKAGES="${PYTHON_PACKAGES:-$RUNTIME_ROOT/python/lib/python3.11/site-packages}"
DOCUMENT_SKILL_ROOT="${DOCUMENT_SKILL_ROOT:-$HOME/.codex/plugins/cache/openai-primary-runtime/documents/26.731.11130/skills/documents}"
RENDERER="${DOCX_RENDERER:-$DOCUMENT_SKILL_ROOT/render_docx.py}"
RENDER_DIR="${REPORT_RENDER_DIR:-$REPORT_DIR/rendered}"
PASS_ONE_DIR="$REPORT_DIR/.rendered-pass-one"
DOCX_PATH="$REPORT_DIR/FastClaw_Project_Report_Zheyu_Wang.docx"
PDF_PATH="$REPORT_DIR/FastClaw_Project_Report_Zheyu_Wang.pdf"
PAGE_MAP_PATH="$REPORT_DIR/page_map.json"
FINAL_PAGE_MAP_PATH="$REPORT_DIR/.page_map-final.json"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Bundled Python not found: $PYTHON_BIN" >&2
  exit 1
fi
if [[ ! -f "$RENDERER" ]]; then
  echo "DOCX renderer not found: $RENDERER" >&2
  exit 1
fi

cd "$ROOT_DIR"
go run ./project-report/analysis
rm -f "$PAGE_MAP_PATH" "$FINAL_PAGE_MAP_PATH"
PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" "$REPORT_DIR/build_report.py"

mkdir -p "$PASS_ONE_DIR"
find "$PASS_ONE_DIR" -maxdepth 1 -type f \( -name 'page-*.png' -o -name '*.pdf' \) -delete
PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" \
  "$RENDERER" "$DOCX_PATH" --output_dir "$PASS_ONE_DIR" --emit_pdf
PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" \
  "$REPORT_DIR/extract_page_map.py" "$PASS_ONE_DIR/$(basename "$PDF_PATH")" "$PAGE_MAP_PATH"

PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" "$REPORT_DIR/build_report.py"
mkdir -p "$RENDER_DIR"
find "$RENDER_DIR" -maxdepth 1 -type f \( -name 'page-*.png' -o -name '*.pdf' \) -delete
PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" \
  "$RENDERER" "$DOCX_PATH" --output_dir "$RENDER_DIR" --emit_pdf

cp "$RENDER_DIR/$(basename "$PDF_PATH")" "$PDF_PATH"
PYTHONPATH="$PYTHON_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" \
  "$REPORT_DIR/extract_page_map.py" "$PDF_PATH" "$FINAL_PAGE_MAP_PATH"
cmp "$PAGE_MAP_PATH" "$FINAL_PAGE_MAP_PATH"
rm -rf "$PASS_ONE_DIR" "$FINAL_PAGE_MAP_PATH"
printf 'DOCX: %s\nPDF:  %s\nQA:   %s\n' "$DOCX_PATH" "$PDF_PATH" "$RENDER_DIR"
