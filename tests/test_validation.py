import tempfile
import os

from services.validation import (
    is_valid_job_id,
    validate_complexity,
    validate_language,
    validate_pdf_magic_bytes,
)


def test_valid_job_id():
    assert is_valid_job_id("3e6a6f6e-0d41-4f15-b1e9-bf8a80fd497b")
    assert not is_valid_job_id("not-a-uuid")
    assert not is_valid_job_id("")


def test_validate_language():
    assert validate_language("pt")
    assert validate_language("en")
    assert not validate_language("xx")


def test_validate_complexity():
    assert validate_complexity("simples")
    assert validate_complexity("mediana")
    assert validate_complexity("complexa")
    assert not validate_complexity("hard")


def test_validate_pdf_magic_bytes():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"%PDF-1.4 fake content")
        path = f.name
    try:
        assert validate_pdf_magic_bytes(path)
    finally:
        os.remove(path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"NOTPDF")
        path = f.name
    try:
        assert not validate_pdf_magic_bytes(path)
    finally:
        os.remove(path)
