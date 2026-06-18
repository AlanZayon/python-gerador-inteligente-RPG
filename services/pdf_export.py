"""PDF export for completed campaigns."""

import io
import logging
import os
import re
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.campaign_parse import parse_campaign

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _strip_md_to_html(content: str) -> str:
    return markdown.markdown(content, extensions=["extra"])


def _render_template(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("campaign_pdf.html")
    return template.render(**context)


def _build_pdf_context(content: str, title: str, language: str, meta: dict | None = None) -> dict:
    parsed = parse_campaign(content)
    meta = meta or {}
    sections = []
    for sec in parsed["sections"]:
        entry = dict(sec)
        entry["content_html"] = _strip_md_to_html(sec.get("content", ""))
        sections.append(entry)
    return {
        "title": title or parsed["title"],
        "language": language or "en",
        "complexity": meta.get("complexity", ""),
        "word_count": meta.get("word_count") or parsed["stats"]["wordCount"],
        "session_count": meta.get("session_count") or parsed["stats"]["sessionCount"],
        "quality_score": meta.get("quality_score"),
        "book_signals": meta.get("book_signals") or [],
        "sections": sections,
    }


def _pdf_from_html(html: str) -> bytes | None:
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception as exc:
        logger.warning("WeasyPrint failed, trying xhtml2pdf: %s", exc)
    try:
        from xhtml2pdf import pisa

        buf = io.BytesIO()
        pisa.CreatePDF(html, dest=buf)
        if buf.tell() > 0:
            return buf.getvalue()
    except Exception as exc:
        logger.warning("xhtml2pdf failed: %s", exc)
    return None


def campaign_to_pdf_bytes(title: str, language: str, body_html: str, subtitle: str = "") -> bytes | None:
    safe_title = re.sub(r"<[^>]+>", "", title)[:120]
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ margin: 2cm; }}
body {{ font-family: Georgia, 'Times New Roman', serif; color: #1a1520; line-height: 1.55; }}
.cover {{ text-align: center; padding: 80px 40px 40px; border-bottom: 3px double #9a7b1c; margin-bottom: 32px; }}
.cover h1 {{ color: #9a7b1c; font-size: 28px; margin: 0 0 12px; }}
.cover p {{ color: #6b6570; font-size: 14px; }}
h1, h2, h3 {{ color: #9a7b1c; page-break-after: avoid; }}
h2 {{ border-bottom: 1px solid #e0d8c8; padding-bottom: 4px; margin-top: 24px; }}
blockquote {{ border-left: 3px solid #9a7b1c; padding-left: 12px; color: #4a4450; }}
.footer {{ margin-top: 40px; font-size: 10px; color: #8a8494; text-align: center; }}
</style></head><body>
<div class="cover">
  <h1>{safe_title}</h1>
  <p>{subtitle or 'Arcane Forge Campaign Manuscript'}</p>
  <p>Language: {language}</p>
</div>
{body_html}
<p class="footer">Generated with Arcane Forge — for personal tabletop use.</p>
</body></html>"""
    return _pdf_from_html(html)


def campaign_markdown_to_pdf(
    content: str,
    title: str,
    language: str,
    meta: dict | None = None,
) -> bytes | None:
    ctx = _build_pdf_context(content, title, language, meta)
    html = _render_template(ctx)
    return _pdf_from_html(html)
