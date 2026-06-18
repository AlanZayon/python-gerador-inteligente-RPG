from services.book_analysis import split_text_chunks
from services.campaign_quality import validate_campaign, word_count
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


def test_validate_campaign_min_words():
    short = "# Overview\nSession 1\n"
    passed, issues, score = validate_campaign(short, "mediana")
    assert not passed
    assert score < 100


def test_word_count():
    assert word_count("hello world test") == 3
