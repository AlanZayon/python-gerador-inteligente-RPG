"""Input validation helpers."""

import re
import uuid

SUPPORTED_LANGUAGES = frozenset(
    {"pt", "en", "es", "fr", "de", "it", "ja", "ko", "zh", "ru"}
)
SUPPORTED_COMPLEXITIES = frozenset({"simples", "mediana", "complexa"})
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_job_id(job_id: str) -> bool:
    if not job_id or not UUID_PATTERN.match(job_id):
        return False
    try:
        uuid.UUID(job_id)
        return True
    except ValueError:
        return False


def validate_language(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES


def validate_complexity(complexity: str) -> bool:
    return complexity in SUPPORTED_COMPLEXITIES


def validate_pdf_magic_bytes(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
        return header == b"%PDF-"
    except OSError:
        return False
