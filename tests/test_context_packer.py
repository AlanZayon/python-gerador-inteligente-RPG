"""Tests for quality-first RAG context packing."""

from services.rag.context_packer import extract_key_terms, pack_lanes


def _chunk(cid: int, text: str, score: float, tokens: int, lane: str) -> dict:
    return {
        "chunk_id": cid,
        "text": text,
        "score": score,
        "token_count": tokens,
        "lane": lane,
    }


def test_pack_lanes_keeps_all_four_bands():
    lanes = {
        "setting": [_chunk(0, "The city of Valdris drowns beneath the tide.", 0.9, 40, "setting")],
        "mechanics": [_chunk(1, "Ability checks use a Difficulty Class of 15.", 0.8, 40, "mechanics")],
        "lore": [_chunk(2, "The Sahuagin Court rules the coral trenches.", 0.85, 40, "lore")],
        "theme": [_chunk(3, "A sunken vault of the First Tide is stirring.", 0.95, 40, "theme")],
    }
    packed = pack_lanes(lanes, complexity="simples", floor=50, ceiling=400)
    ctx = packed["book_context"]
    assert "Setting and tone" in ctx
    assert "Mechanics" in ctx
    assert "Locations, factions, creatures" in ctx
    assert "Theme-relevant excerpts" in ctx
    assert "Valdris" in ctx
    assert "Sahuagin" in ctx
    assert packed["lanes_used"]["setting"] >= 1
    assert packed["lanes_used"]["mechanics"] >= 1
    assert packed["lanes_used"]["lore"] >= 1
    assert packed["lanes_used"]["theme"] >= 1
    assert packed["chunks_used"] == 4


def test_pack_lanes_dedups_near_identical_chunks():
    same = "Valdris is a drowned city of coral palaces and old magic."
    lanes = {
        "setting": [_chunk(0, same, 0.9, 80, "setting")],
        "mechanics": [_chunk(1, "Roll a d20 and add proficiency.", 0.7, 20, "mechanics")],
        "lore": [_chunk(2, same + " The palaces glow.", 0.6, 80, "lore")],
        "theme": [_chunk(3, "Theme: rising waters threaten the last spire.", 0.8, 30, "theme")],
    }
    packed = pack_lanes(lanes, complexity="simples", floor=20, ceiling=400)
    assert packed["book_context"].count("drowned city") == 1


def test_pack_lanes_never_drops_a_covered_lane_for_ceiling():
    lanes = {
        "setting": [_chunk(0, "Setting lore " + ("world " * 20), 0.5, 40, "setting")],
        "mechanics": [_chunk(1, "Mechanics block " + ("rule " * 20), 0.4, 40, "mechanics")],
        "lore": [_chunk(2, "Lore block " + ("place " * 20), 0.3, 40, "lore")],
        "theme": [
            _chunk(3, "Theme A " + ("hook " * 20), 0.99, 40, "theme"),
            _chunk(4, "Theme B extra " + ("more " * 40), 0.2, 200, "theme"),
        ],
    }
    packed = pack_lanes(lanes, complexity="simples", floor=50, ceiling=200)
    assert packed["lanes_used"]["setting"] >= 1
    assert packed["lanes_used"]["mechanics"] >= 1
    assert packed["lanes_used"]["lore"] >= 1
    assert packed["lanes_used"]["theme"] >= 1
    assert packed["token_count"] <= 200
    assert packed["lanes_used"]["theme"] == 1


def test_extract_key_terms_from_capitalized_names():
    terms = extract_key_terms("The city of Valdris fights the Sahuagin Court near Emberfall.")
    assert "Valdris" in terms
    assert "Sahuagin" in terms


def test_extract_key_terms_ignores_packer_headings():
    terms = extract_key_terms(
        "## Setting and tone\n### Excerpt 1\nThe city of Valdris drowns.\n"
        "Algumas campanhas. Assim o Mestre. Forgotten Realms names stay."
    )
    assert "Valdris" in terms
    assert "Setting" not in terms
    assert "Excerpt" not in terms
    assert "Algumas" not in terms
    assert "Mestre" not in terms
