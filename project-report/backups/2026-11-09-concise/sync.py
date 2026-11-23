from pathlib import Path
from difflib import SequenceMatcher
from docx import Document
root=Path(__file__).resolve().parents[2]
old=(Path(__file__).parent/'fastclaw_project_report.md').read_text().split('\n\n')
new=(root/'fastclaw_project_report.md').read_text().split('\n\n')
doc=Document(root/'FastClaw_Project_Report_Zheyu_Wang.docx')
count=0
for tag,a,b,c,d in SequenceMatcher(None,old,new).get_opcodes():
    if tag=='equal': continue
    assert tag=='replace' and b-a==d-c==1,(tag,a,b,c,d)
    target=old[a].replace('`','')
    matches=[p for p in doc.paragraphs if p.text==target]
    assert len(matches)==1,target[:80]
    p=matches[0]
    p.runs[0].text=new[c].replace('`','')
    for r in p.runs[1:]: r.text=''
    count+=1
doc.save(root/'FastClaw_Project_Report_Zheyu_Wang.docx')
print('Updated paragraphs:',count)
