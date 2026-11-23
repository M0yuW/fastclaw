from pathlib import Path
from docx import Document
root = Path(__file__).resolve().parents[2]
path = root / 'FastClaw_Project_Report_Zheyu_Wang.docx'
doc = Document(path)
sentence = ' Local deterministic tests cover pausing and continuation; deciding when to ask remains model-driven, and this mechanism was not included in the earlier application experiments.'
count = 0
for p in doc.paragraphs:
    if sentence in p.text:
        text = p.text.replace(sentence, '')
        p.runs[0].text = text
        for run in p.runs[1:]: run.text = ''
        count += 1
assert count == 1
doc.save(path)
