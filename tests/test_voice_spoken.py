"""Optional JSON spoken content — no regex of tags in prose."""

from services.voice.spoken import parse_spoken_content


def test_plain_text_is_unchanged():
    text, speaker, direction = parse_spoken_content(
        "A porta começa a se abrir lentamente..."
    )
    assert text == "A porta começa a se abrir lentamente..."
    assert speaker == "gm"
    assert direction is None


def test_json_object_extracts_text_and_tags():
    raw = (
        '{"text": "A porta começa a se abrir...", '
        '"speaker": "villain", '
        '"voice_direction": {"tags": ["[slowly]", "[whispers]"]}}'
    )
    text, speaker, direction = parse_spoken_content(raw)
    assert text == "A porta começa a se abrir..."
    assert speaker == "villain"
    assert direction is not None
    assert direction.tags == ["[slowly]", "[whispers]"]


def test_does_not_parse_tags_out_of_prose():
    text, speaker, direction = parse_spoken_content("[whispers] Stay quiet.")
    assert text == "[whispers] Stay quiet."
    assert speaker == "gm"
    assert direction is None


def test_invalid_json_object_treated_as_prose():
    text, speaker, direction = parse_spoken_content("{not json}")
    assert text == "{not json}"
    assert direction is None
