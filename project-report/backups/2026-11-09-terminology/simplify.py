from pathlib import Path
from docx import Document
root=Path(__file__).resolve().parents[2]
# Mechanical terminology normalization, with longer phrases applied first.
replacements=[
('model-comparison using the same model','comparison using the same model'),
('A separate supplementary comparison using the same model holds the model family and tier fixed','A supplementary comparison holds the model family and tier fixed'),
('High quality under case rubric','High quality'),
('Under the later frozen rubric, an answer rated high quality under the case-specific rubric requires','To be rated high quality under the case-specific rubric, an answer requires'),
('a matched all-Flash comparison','a comparison of Solo and Team using the same model'),
('matched all-Flash comparison','comparison using the same model'),
('model-matched all-Flash comparison','comparison using the same model'),
('capacity-matched all-Flash subset','comparison using the same model'),
('matched all-Flash study','study using the same model for both modes'),
('Same-model all-Flash Team and Solo comparison','Team and Solo comparison using the same model'),
('Matched All Flash Comparison','Solo and Team Comparison Using the Same Model'),
('All-Flash comparison','Comparison using the same model'),
('all-Flash comparison','comparison using the same model'),
('all-Flash supplement','supplementary comparison using the same model'),
('all-Flash subset','subset using the same model'),
('all-Flash pairs','pairs using the same model'),
('all-Flash selected reports','selected reports for the same-model comparison'),
('24-observation all-Pro ablation','24-observation comparison using Pro for every model call'),
('The executed Stage 2A v2 suite','The SEC study'),
('The executed Stage 2A v2 main study','The SEC main study'),
('Stage 2A v2 main-study results','SEC main-study results'),
('the Stage 2A v2 and','the SEC main study and'),
('repeated Stage 2A study','repeated SEC study'),
('a high-within-case answer','an answer rated high quality under the case-specific rubric'),
('a high-within-case local score','a high-quality rating under the case-specific rubric'),
('High within case','High quality under case rubric'),
('mechanical passes','passes on the workflow execution checks'),
('Mechanical completion','Workflow completion'),
('mechanical results','automated check results'),
('Its mechanical classifier','Its automated execution checker'),
('a separate mini-panel','a separate three-company study'),
('A separate mini-panel','A separate three-company study'),
('prospective mini-panel','prospective three-company study'),
('six mini-panel answers','six answers from the three-company study'),
('Six-session mini-panel outcomes','Results of the six-session study'),
('source-bound arithmetic review guard','check that validates calculations against the supplied source values'),
('a source-bound arithmetic guard','a check that validates calculations against the supplied source values'),
('a matched-model comparison of Solo and Team execution','a comparison of Solo and Team execution using the same model'),
('with repeated, source-locked workloads','with repeated tasks using fixed source documents'),
('source-locked archived SEC records','archived SEC records fixed before evaluation'),
('24 source-locked SEC configurations','24 SEC task configurations using fixed source documents'),
('this source-locked oracle','these reference answers derived from fixed source documents'),
('Source-locked event-to-thesis panel','Event review study using fixed source documents'),
('selected real-source analyses','selected analyses of public financial disclosures'),
('Tool-backed financial workflows','Financial workflows that execute tools'),
('The local LLM-as-judge rubric','The LLM-assisted assessment rubric'),
]
def transform(text):
    for a,b in replacements: text=text.replace(a,b)
    return text
md=root/'fastclaw_project_report.md'
before=md.read_text()
after=transform(before)
doc=Document(root/'FastClaw_Project_Report_Zheyu_Wang.docx')
def paragraphs(container):
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells: yield from paragraphs(cell)
count=0
for p in paragraphs(doc):
    new=transform(p.text)
    if new!=p.text:
        # Retain unchanged run formatting where the phrase fits in a run.
        if ''.join(transform(r.text) for r in p.runs)==new:
            for r in p.runs: r.text=transform(r.text)
        else:
            p.runs[0].text=new
            for r in p.runs[1:]: r.text=''
        count+=1
md.write_text(after)
doc.save(root/'FastClaw_Project_Report_Zheyu_Wang.docx')
print('Changed Word paragraphs/cells:',count)
