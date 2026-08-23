from services.book_analysis import split_text_chunks
from tasks.campaign_tasks import generate_fallback_campaign


def test_generate_fallback_campaign_simples():
    content = generate_fallback_campaign("simples", "en")
    assert "Whispering" in content or "Cellar" in content
    assert "Simple" in content or "SIMPLE" in content


def test_generate_fallback_campaign_complexa():
    content = generate_fallback_campaign("complexa", "en")
    assert "Archive" in content or "Echoes" in content


def test_split_text_chunks():
    long_text = "x" * 25000
    chunks = split_text_chunks(long_text, chunk_size=8000)
    assert len(chunks) >= 3
