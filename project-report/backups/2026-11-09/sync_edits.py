from pathlib import Path
from docx import Document
root = Path(__file__).resolve().parents[2]
old = (Path(__file__).parent / 'fastclaw_project_report.md').read_text()
new = (root / 'fastclaw_project_report.md').read_text()
doc = Document(root / 'FastClaw_Project_Report_Zheyu_Wang.docx')
oldp = next(p for p in old.split('\n\n') if p.startswith('The fixed benchmark evidence'))
newp = next(p for p in new.split('\n\n') if p.startswith('The preliminary fixed-evidence benchmark and synthetic'))
added = next(p for p in new.split('\n\n') if p.startswith('A separate Python prototype'))
counts = [0,0,0]
for p in doc.paragraphs:
    for run in p.runs:
        if 'Faculty of Science and Technology' in run.text:
            run.text = run.text.replace('Faculty of Science and Technology', 'Faculty of Information Science and Computing')
            counts[0] += 1
    if p.text == oldp:
        p.runs[0].text = newp
        for r in p.runs[1:]: r.text = ''
        counts[1] += 1
    if p.text == 'Longer-term engineering and evaluation work includes:':
        q = p.insert_paragraph_before(added, style=p.style)
        counts[2] += 1
assert counts == [1,1,1], counts
doc.save(root / 'FastClaw_Project_Report_Zheyu_Wang.docx')
print(counts)
