from pathlib import Path
from docx import Document
import shutil
root = Path(__file__).resolve().parents[2]
path = root / 'FastClaw_Project_Report_Zheyu_Wang.docx'
shutil.copy2(path, Path(__file__).parent / 'report.before-clarification-move.docx')
doc = Document(path)
text = next(p for p in (root / 'fastclaw_project_report.md').read_text().split('\n\n') if p.startswith('An additional session-control mechanism'))
old = next(p for p in doc.paragraphs if p.text.startswith('A separate Python prototype'))
style = old.style
old._element.getparent().remove(old._element)
anchor = next(p for p in doc.paragraphs if p.text == 'Runtime Invariants and Repair Algorithms')
anchor.insert_paragraph_before(text, style=style)
doc.save(path)
