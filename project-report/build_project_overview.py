from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


REPORT_DIR = Path(__file__).resolve().parent
SOURCE = REPORT_DIR / "Agent_Runtime_Project_Overview.md"
OUTPUT = REPORT_DIR / "Agent_Runtime_Project_Overview.docx"


def build() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.76)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.83)
    section.right_margin = Inches(0.83)

    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.1

    title_style = document.styles["Title"]
    title_style.font.name = "Aptos Display"
    title_style.font.size = Pt(17)
    title_style.font.bold = True
    title_style.font.color.rgb = None
    title_style.paragraph_format.space_after = Pt(6)
    title_border = title_style._element.pPr.find(qn("w:pBdr"))
    if title_border is not None:
        title_style._element.pPr.remove(title_border)

    heading_style = document.styles["Heading 2"]
    heading_style.font.name = "Aptos Display"
    heading_style.font.size = Pt(11.5)
    heading_style.font.bold = True
    heading_style.font.color.rgb = None
    heading_style.paragraph_format.space_before = Pt(9)
    heading_style.paragraph_format.space_after = Pt(3)

    for line in lines:
        if not line:
            continue
        if line.startswith("# "):
            document.add_paragraph(line[2:], style="Title")
        elif line.startswith("## "):
            document.add_paragraph(line[3:], style="Heading 2")
        elif "  |  " in line:
            paragraph = document.add_paragraph(line)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.runs[0].font.size = Pt(9)
            paragraph.paragraph_format.space_after = Pt(9)
        else:
            document.add_paragraph(line)

    document.core_properties.title = "Design and Evaluation of an Auditable Agent Runtime"
    document.core_properties.subject = "One page project overview for academic review"
    document.core_properties.author = "Zheyu Wang"
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
