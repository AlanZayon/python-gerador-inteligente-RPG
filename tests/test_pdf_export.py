"""Tests for PDF export (template render, optional PDF bytes)."""

from examples.campaign_samples import get_sample_campaign
from services.pdf_export import _build_pdf_context, _render_template


def test_pdf_context_from_sample():
    sample = get_sample_campaign("mediana", "en")
    ctx = _build_pdf_context(sample, "Test Campaign", "en", {"complexity": "mediana"})
    assert ctx["title"] == "Test Campaign"
    assert ctx["session_count"] >= 3
    assert len(ctx["sections"]) > 0


def test_pdf_template_renders_html():
    sample = get_sample_campaign("simples", "en")
    ctx = _build_pdf_context(sample, "Whispering Cellar", "en", {})
    html = _render_template(ctx)
    assert "Whispering Cellar" in html
    assert "session-card" in html or "section-heading" in html
