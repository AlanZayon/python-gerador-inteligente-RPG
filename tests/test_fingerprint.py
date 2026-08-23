"""Tests for perceptual PDF fingerprints."""

from PIL import Image, ImageDraw

from services.rag.fingerprint import (
    book_id_from_sha256,
    fingerprints_match,
    hash_image,
    hamming_distance,
    mean_hamming,
    page_count_compatible,
    sample_page_indices,
    text_sha256,
)


def _block_image(color: str = "black") -> Image.Image:
    img = Image.new("RGB", (128, 128), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, 96, 96), fill=color)
    return img


def test_sample_page_indices_small_book():
    assert sample_page_indices(4) == [0, 1, 2, 3]


def test_sample_page_indices_includes_first_and_last():
    idxs = sample_page_indices(40, max_pages=6)
    assert idxs[0] == 0
    assert idxs[-1] == 39
    assert len(idxs) == 6


def test_hash_image_is_deterministic():
    img = _block_image()
    first = hash_image(img)
    second = hash_image(img)
    assert first == second
    assert set(first) == {"ahash", "dhash", "phash", "whash"}
    assert all(len(v) == 16 for v in first.values())


def test_identical_images_zero_hamming():
    img = _block_image()
    hashes = hash_image(img)
    dist = mean_hamming([{"page": 0, **hashes}], [{"page": 0, **hashes}])
    assert dist == 0
    assert fingerprints_match(
        {"page_count": 10, "pages": [{"page": 0, **hashes}]},
        {"page_count": 10, "pages": [{"page": 0, **hashes}]},
    )


def test_different_images_are_not_a_match():
    a = hash_image(_block_image("black"))
    b = hash_image(_block_image("white"))
    other = Image.new("RGB", (128, 128), "navy")
    draw = ImageDraw.Draw(other)
    draw.ellipse((4, 4, 124, 124), fill="orange")
    c = hash_image(other)
    dist = mean_hamming([{"page": 0, **a}], [{"page": 0, **c}])
    assert dist is not None
    assert dist > 8
    assert not fingerprints_match(
        {"page_count": 12, "pages": [{"page": 0, **a}]},
        {"page_count": 12, "pages": [{"page": 0, **c}]},
        threshold=8,
    )
    assert hamming_distance(a["phash"], b["phash"]) >= 0


def test_page_count_incompatible_rejects_match():
    hashes = hash_image(_block_image())
    assert not page_count_compatible(10, 100)
    assert not fingerprints_match(
        {"page_count": 10, "pages": [{"page": 0, **hashes}]},
        {"page_count": 100, "pages": [{"page": 0, **hashes}]},
    )


def test_book_id_and_text_hash():
    assert book_id_from_sha256("abcdef1234567890ffff") == "bk_abcdef1234567890"
    assert text_sha256("Hello   world") == text_sha256("Hello world")
    assert text_sha256("Hello world") != text_sha256("Hello worlds")
