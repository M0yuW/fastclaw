#!/usr/bin/env python3
"""Generate editable, article-ready SVG candidates without changing the report."""

from html import escape
from pathlib import Path


OUT = Path(__file__).resolve().parent
INK = "#183047"
MUTED = "#52677a"
TEAL = "#087e79"
BLUE = "#386895"
AMBER = "#ac7323"
LINE = "#ccdae4"
PALE = "#f4f8fa"


class Figure:
    def __init__(self, title, subtitle, width=1600, height=900):
        self.width, self.height = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
            '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7.2" refY="4.5" '
            'orient="auto"><path d="M1 1 L7.5 4.5 L1 8" fill="none" stroke="#607b8c" '
            'stroke-width="1.5"/></marker></defs>',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<style>text{font-family:Inter,Arial,sans-serif;fill:#183047} '
            '.title{font-size:32px;font-weight:700;letter-spacing:-.3px} '
            '.subtitle{font-size:17px;fill:#52677a} '
            '.label{font-size:21px;font-weight:700} .body{font-size:16px;fill:#52677a} '
            '.micro{font-size:14px;fill:#52677a} .smallhead{font-size:16px;font-weight:700} '
            '.phase{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:#386895}</style>',
        ]
        self.text(65, 71, title, "title")
        self.text(65, 104, subtitle, "subtitle")
        self.line(65, 130, width - 65, 130, stroke=LINE, arrow=False)

    def text(self, x, y, value, cls="body", anchor="start", fill=None):
        style = f' style="fill:{fill}"' if fill else ""
        self.parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{style}>{escape(value)}</text>')

    def rect(self, x, y, w, h, fill=PALE, stroke=LINE, radius=17, sw=1.5):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def line(self, x1, y1, x2, y2, stroke="#607b8c", arrow=True, dash=None, sw=2):
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        dotted = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                          f'stroke="{stroke}" stroke-width="{sw}"{marker}{dotted}/>')

    def poly(self, points, stroke="#607b8c", arrow=True, dash=None, sw=2):
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        dotted = f' stroke-dasharray="{dash}"' if dash else ""
        coords = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(f'<polyline points="{coords}" fill="none" stroke="{stroke}" '
                          f'stroke-width="{sw}" stroke-linejoin="round"{marker}{dotted}/>')

    def card(self, x, y, w, h, title, lines=(), color=TEAL, fill=PALE):
        self.rect(x, y, w, h, fill=fill)
        self.rect(x, y, 7, h, fill=color, stroke=color, radius=3, sw=0)
        self.text(x + 27, y + 37, title, "label")
        for i, line in enumerate(lines):
            self.text(x + 27, y + 66 + i * 25, line, "body")

    def save(self, name):
        self.parts.append("</svg>")
        (OUT / name).write_text("\n".join(self.parts) + "\n", encoding="utf-8")


def architecture():
    f = Figure("Auditable multi-agent runtime", "Logical boundaries of the single-Gateway implementation")
    f.text(65, 174, "EXTERNAL INGRESS", "phase")
    for i, (title, detail) in enumerate([
        ("Web / API", "Chat and programmatic calls"),
        ("Channels", "Bots and webhooks"),
        ("Scheduled", "Cron-triggered tasks"),
    ]):
        f.card(65 + i * 495, 195, 455, 92, title, [detail], BLUE)
    f.line(800, 289, 800, 323)
    f.card(355, 325, 890, 96, "Identity + tenant scope", ["Resolve user and target agent · enforce ACL · bind trusted execution context"], BLUE)
    f.line(800, 423, 800, 454)
    f.rect(65, 457, 1470, 220, fill="#f6f9fa", stroke="#9ab6c4", radius=21)
    f.text(94, 489, "GATEWAY PROCESS · VOLATILE CONTROL PLANE", "phase")
    f.card(95, 510, 425, 135, "MessageBus", ["Ingress / outbound normalization", "Correlated internal request–reply"], TEAL, "#ffffff")
    f.card(588, 510, 425, 135, "TaskQueue", ["Per-chat FIFO · bounded root admission", "Cancellation and timeout"], TEAL, "#ffffff")
    f.card(1081, 510, 425, 135, "Agent runtime", ["Prompt + provider + tool loop", "Policy and terminal event contract"], TEAL, "#ffffff")
    f.line(522, 579, 583, 579)
    f.line(1015, 579, 1076, 579)
    f.card(65, 739, 445, 108, "Model providers", ["Streaming LLM calls and usage"], BLUE)
    f.card(578, 739, 445, 108, "Tools + plugins + sandbox", ["Filtered actions and trusted scope"], AMBER)
    f.card(1091, 739, 445, 108, "Persistence + telemetry", ["SQL, workspace, sessions, traces"], BLUE)
    f.line(1294, 678, 1294, 734)
    f.line(800, 678, 800, 734)
    f.poly([(1294, 678), (288, 678), (288, 734)], arrow=True)
    f.save("01-runtime-architecture.svg")


def delegation():
    f = Figure("Correlated delegation and bounded execution", "A single root task delegates parallel specialist work without taking another root slot", 1800, 985)
    lanes = [("Client", 155), ("Gateway / queue", 445), ("Coordinator", 735),
             ("Model provider", 1025), ("MessageBus", 1315), ("Specialists", 1605)]
    for name, x in lanes:
        f.rect(x - 119, 166, 238, 56, fill="#eaf2f5", stroke=LINE, radius=12)
        f.text(x, 201, name, "smallhead", "middle")
        f.line(x, 225, x, 896, stroke="#b6c9d3", arrow=False, dash="5 6", sw=1.5)
    events = [
        (155, 445, 266, "authenticated request"),
        (445, 735, 326, "admit root; per-chat FIFO"),
        (735, 1025, 389, "call model with filtered tools"),
        (1025, 735, 449, "delegate batch plan"),
        (735, 1315, 509, "internal calls; inherit root ID"),
        (1315, 1605, 569, "fan out ×3 in parallel"),
        (1605, 1315, 652, "correlated replies"),
        (1315, 735, 711, "release waiters; cycle guard"),
        (735, 1025, 771, "synthesize evidence"),
        (1025, 735, 818, "final answer + usage"),
        (735, 445, 856, "terminal event + trace"),
        (445, 155, 893, "response"),
    ]
    for start, end, y, label in events:
        f.line(start + (8 if end > start else -8), y, end + (-12 if end > start else 12), y)
        f.text((start + end) / 2, y - 11, label, "micro", "middle")
    f.rect(1452, 582, 306, 47, fill="#e9f6f2", stroke="#b6d7ce", radius=10)
    f.text(1605, 612, "trend · accounting · risk", "micro", "middle", TEAL)
    f.save("02-delegation-sequence.svg")


def finance():
    f = Figure("Evidence-grounded financial research workflow", "Deterministic data and state controls surround model-assisted interpretation")
    cards = [
        (65, "Dated sources", ["SEC filings / market data", "source, locator, as-of time"], BLUE),
        (380, "Deterministic tools", ["Extract, validate, calculate", "screen / risk / event identity"], TEAL),
        (695, "Evidence packet", ["Typed facts + completeness", "provenance + missingness"], TEAL),
        (1010, "Research agents", ["Synthesize + challenge", "cite support and uncertainty"], AMBER),
    ]
    for x, title, lines, color in cards:
        f.card(x, 255, 270, 160, title, lines, color)
    for x in [342, 657, 972]:
        f.line(x, 335, x + 31, 335)
    f.line(1284, 335, 1360, 335)
    f.card(1364, 255, 170, 160, "Decision", ["Human review", "No auto-trade"], BLUE)
    f.card(65, 539, 696, 160, "Versioned thesis ledger", ["Immutable reviews · optimistic version checks", "Catalysts, invalidations, counterevidence"], TEAL)
    f.card(837, 539, 697, 160, "Watchlist and deduplicated alerts", ["Stable event fingerprint · occurrence count", "Human-confirmed change of research status"], TEAL)
    f.poly([(1145, 417), (1145, 492), (413, 492), (413, 533)], stroke=TEAL)
    f.poly([(1145, 492), (1185, 492), (1185, 533)], stroke=TEAL)
    f.rect(65, 762, 1470, 72, fill="#f5f8fa", stroke=LINE, radius=12)
    f.text(800, 807, "Boundary: traceable research output is not factual certification, investment advice, or order execution.", "body", "middle")
    f.save("03-finance-workflow.svg")


def experiment():
    f = Figure("Matched-model Team / Solo comparison", "Same SEC corpus, task, scoring rules and DeepSeek V4 Flash model allocation")
    f.card(450, 168, 700, 110, "Shared experimental input", ["Source-locked SEC records · one question · one oracle · randomized mode order"], BLUE)
    f.poly([(800, 280), (800, 314), (417, 314), (417, 345)], arrow=True)
    f.poly([(800, 314), (1183, 314), (1183, 345)], arrow=True)
    f.rect(65, 349, 705, 382, fill="#f5f9fb", stroke="#9fc0d1", radius=20)
    f.text(100, 388, "SOLO STAGED · FLASH ONLY", "phase")
    f.card(100, 410, 635, 70, "Retrieve evidence", [], BLUE, "#ffffff")
    f.line(417, 482, 417, 505)
    f.card(100, 508, 635, 105, "Three sequential perspectives", ["Trend → accounting → risk, one after another"], BLUE, "#ffffff")
    f.line(417, 615, 417, 637)
    f.card(100, 640, 635, 65, "Synthesize report", [], BLUE, "#ffffff")
    f.rect(830, 349, 705, 382, fill="#f3faf7", stroke="#9bd2bf", radius=20)
    f.text(865, 388, "TEAM SHARED RETRIEVAL · FLASH ONLY", "phase")
    f.card(865, 410, 635, 70, "Retrieve once; share bounded packet", [], TEAL, "#ffffff")
    f.line(1182, 482, 1182, 511)
    for i, label in enumerate(["Trend", "Accounting", "Risk"]):
        f.card(865 + 218 * i, 514, 199, 87, label, ["parallel specialist"], TEAL, "#ffffff")
    f.poly([(975, 604), (975, 627), (1182, 627)], arrow=False)
    f.poly([(1399, 604), (1399, 627), (1182, 627)], arrow=False)
    f.line(1182, 603, 1182, 636)
    f.card(865, 640, 635, 65, "Coordinator synthesis", [], TEAL, "#ffffff")
    f.line(417, 732, 417, 765)
    f.line(1182, 732, 1182, 765)
    f.rect(190, 767, 1220, 79, fill="#f5f8fa", stroke=LINE, radius=14)
    f.text(800, 802, "Paired outcomes: strict pass · evidence recall · grounding · wall-clock latency", "smallhead", "middle")
    f.text(800, 828, "Also report tokens, frozen-price cost and infrastructure errors; source/oracle audit remains a freeze gate.", "micro", "middle")
    f.save("04-matched-model-experiment.svg")


if __name__ == "__main__":
    architecture()
    delegation()
    finance()
    experiment()
    print("Generated 4 SVG candidates in", OUT)
