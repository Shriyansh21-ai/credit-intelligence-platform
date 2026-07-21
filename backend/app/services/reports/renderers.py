"""Report renderers.

Each renderer takes a normalised report document and returns
``(bytes, content_type, extension)``. Formats:
    json  — structured data (dict, returned directly by the service)
    html  — styled, printable HTML (always available)
    pdf   — reportlab (available in this environment)
    csv   — flat CSV, opens in Excel (stdlib)
    rtf   — Rich Text, opens in Word (stdlib)
"""

from __future__ import annotations

import csv
import html
import io
from typing import Any, Dict, List, Tuple

# reportlab is optional; PDF degrades to HTML bytes if it is unavailable.
try:  # pragma: no cover - import guard
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    _HAS_REPORTLAB = True
except Exception:  # pragma: no cover
    _HAS_REPORTLAB = False


def available_formats() -> Dict[str, bool]:
    return {
        "json": True,
        "html": True,
        "csv": True,
        "rtf": True,
        "pdf": _HAS_REPORTLAB,
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def _section_html(section: Dict[str, Any]) -> str:
    heading = html.escape(str(section.get("heading", "")))
    kind = section.get("kind")
    parts = [f"<h2>{heading}</h2>"]
    if kind == "kv":
        parts.append("<table class='kv'>")
        for item in section.get("items", []):
            parts.append(
                f"<tr><th>{html.escape(str(item.get('label','')))}</th>"
                f"<td>{html.escape(str(item.get('value','')))}</td></tr>"
            )
        parts.append("</table>")
    elif kind == "table":
        parts.append("<table class='data'>")
        cols = section.get("columns", [])
        parts.append("<tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in cols) + "</tr>")
        for row in section.get("rows", []):
            parts.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>")
        parts.append("</table>")
    else:  # text
        parts.append(f"<p>{html.escape(str(section.get('text','')))}</p>")
    return "\n".join(parts)


def render_html(doc: Dict[str, Any]) -> Tuple[bytes, str, str]:
    body = "\n".join(_section_html(s) for s in doc.get("sections", []))
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(doc.get('title',''))}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;color:#1a1a1a;margin:40px;}}
h1{{font-size:22px;margin-bottom:2px;}}
.subtitle{{color:#666;margin-bottom:20px;}}
h2{{font-size:15px;border-bottom:2px solid #ddd;padding-bottom:4px;margin-top:24px;}}
table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px;}}
th,td{{border:1px solid #ccc;padding:6px 8px;text-align:left;}}
table.kv th{{width:220px;background:#f5f5f5;}}
table.data th{{background:#f0f4f8;}}
.footer{{margin-top:30px;color:#999;font-size:11px;}}
</style></head><body>
<h1>{html.escape(doc.get('title',''))}</h1>
<div class="subtitle">{html.escape(doc.get('subtitle',''))} &middot; Generated {html.escape(doc.get('generated_at',''))}</div>
{body}
<div class="footer">Confidential — AI Credit Decision Platform</div>
</body></html>"""
    return page.encode("utf-8"), "text/html", "html"


# --------------------------------------------------------------------------
# CSV (Excel-openable)
# --------------------------------------------------------------------------

def render_csv(doc: Dict[str, Any]) -> Tuple[bytes, str, str]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([doc.get("title", "")])
    writer.writerow([doc.get("subtitle", ""), "Generated", doc.get("generated_at", "")])
    writer.writerow([])
    for section in doc.get("sections", []):
        writer.writerow([section.get("heading", "")])
        kind = section.get("kind")
        if kind == "kv":
            for item in section.get("items", []):
                writer.writerow([item.get("label", ""), item.get("value", "")])
        elif kind == "table":
            writer.writerow(section.get("columns", []))
            for row in section.get("rows", []):
                writer.writerow(row)
        else:
            writer.writerow([section.get("text", "")])
        writer.writerow([])
    return buf.getvalue().encode("utf-8"), "text/csv", "csv"


# --------------------------------------------------------------------------
# RTF (Word-openable)
# --------------------------------------------------------------------------

def _rtf_escape(text: Any) -> str:
    s = str(text)
    s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return s.replace("\n", "\\par ")


def render_rtf(doc: Dict[str, Any]) -> Tuple[bytes, str, str]:
    parts = [r"{\rtf1\ansi\deff0"]
    parts.append(r"{\b\fs32 " + _rtf_escape(doc.get("title", "")) + r"}\par")
    parts.append(r"{\i " + _rtf_escape(doc.get("subtitle", "")) +
                 " - Generated " + _rtf_escape(doc.get("generated_at", "")) + r"}\par\par")
    for section in doc.get("sections", []):
        parts.append(r"{\b\fs24 " + _rtf_escape(section.get("heading", "")) + r"}\par")
        kind = section.get("kind")
        if kind == "kv":
            for item in section.get("items", []):
                parts.append(_rtf_escape(item.get("label", "")) + ": " +
                             _rtf_escape(item.get("value", "")) + r"\par")
        elif kind == "table":
            parts.append(_rtf_escape(" | ".join(str(c) for c in section.get("columns", []))) + r"\par")
            for row in section.get("rows", []):
                parts.append(_rtf_escape(" | ".join(str(c) for c in row)) + r"\par")
        else:
            parts.append(_rtf_escape(section.get("text", "")) + r"\par")
        parts.append(r"\par")
    parts.append("}")
    return "\n".join(parts).encode("utf-8"), "application/rtf", "rtf"


# --------------------------------------------------------------------------
# PDF (reportlab)
# --------------------------------------------------------------------------

def render_pdf(doc: Dict[str, Any]) -> Tuple[bytes, str, str]:
    if not _HAS_REPORTLAB:
        # Graceful degradation: hand back HTML bytes labelled as such.
        data, _ct, _ext = render_html(doc)
        return data, "text/html", "html"

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, title=doc.get("title", "Report"))
    styles = getSampleStyleSheet()
    flow: List[Any] = [
        Paragraph(html.escape(doc.get("title", "")), styles["Title"]),
        Paragraph(
            f"{html.escape(doc.get('subtitle',''))} &middot; Generated {html.escape(doc.get('generated_at',''))}",
            styles["Normal"],
        ),
        Spacer(1, 16),
    ]
    for section in doc.get("sections", []):
        flow.append(Paragraph(html.escape(str(section.get("heading", ""))), styles["Heading2"]))
        kind = section.get("kind")
        if kind == "kv":
            data = [[str(i.get("label", "")), str(i.get("value", ""))] for i in section.get("items", [])]
            if data:
                table = Table(data, colWidths=[160, 320])
                table.setStyle(_table_style(header=False))
                flow.append(table)
        elif kind == "table":
            data = [[str(c) for c in section.get("columns", [])]]
            data += [[str(c) for c in row] for row in section.get("rows", [])]
            if len(data) > 0:
                table = Table(data, repeatRows=1)
                table.setStyle(_table_style(header=True))
                flow.append(table)
        else:
            flow.append(Paragraph(html.escape(str(section.get("text", ""))), styles["Normal"]))
        flow.append(Spacer(1, 12))

    pdf.build(flow)
    return buf.getvalue(), "application/pdf", "pdf"


def _table_style(header: bool):
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4f8")))
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    else:
        style.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")))
        style.append(("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"))
    return TableStyle(style)


RENDERERS = {
    "html": render_html,
    "csv": render_csv,
    "rtf": render_rtf,
    "pdf": render_pdf,
}
