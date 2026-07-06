"""RAG endpoints — no auth (dev/MVP). Integrate with worker later."""

import logging
import os
import re
import tempfile

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from services.rag.faiss_store import BookIndexNotFoundError, get_book_meta, index_exists
from services.rag.generator import generate_campaign
from services.rag.indexer import index_book
from services.rag.llama_client import LlamaServerError, LlamaServerUnavailable
from services.rag.pdf_text import extract_text_from_pdf
from services.validation import validate_pdf_magic_bytes

logger = logging.getLogger(__name__)

rag_bp = Blueprint("rag", __name__)

_BOOK_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _valid_book_id(book_id: str) -> bool:
    return bool(book_id and _BOOK_ID_RE.match(book_id))


@rag_bp.route("/index", methods=["POST"])
def rag_index():
    """
    Index a PDF for RAG (offline-style, via HTTP convenience).

    multipart: file (PDF), book_id (string), force (optional, "true")
    """
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    book_id = (request.form.get("book_id") or "").strip()
    if not _valid_book_id(book_id):
        return jsonify({"error": "book_id must be 1-64 alphanumeric chars, _ or -"}), 400

    pdf_file = request.files["file"]
    if not pdf_file.filename:
        return jsonify({"error": "empty filename"}), 400

    force = request.form.get("force", "").lower() in ("true", "1", "yes")

    suffix = os.path.splitext(secure_filename(pdf_file.filename))[1] or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        pdf_file.save(tmp.name)
        tmp.close()

        if not validate_pdf_magic_bytes(tmp.name):
            return jsonify({"error": "invalid PDF file"}), 400

        result = index_book(
            tmp.name,
            book_id,
            force=force,
            source_filename=pdf_file.filename,
        )
        status = 200 if result.get("skipped") else 201
        return jsonify(result), status
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("RAG index failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


@rag_bp.route("/generate-campaign", methods=["POST"])
def rag_generate_campaign():
    """
    Generate campaign via RAG + LLaMA (sync).

    JSON body preferred. Multipart also accepted with sheet_files[].
    """
    data = request.get_json(silent=True) or {}

    if not data and request.form:
        data = {
            "book_id": request.form.get("book_id"),
            "theme": request.form.get("theme"),
            "hook": request.form.get("hook", ""),
            "target_language": request.form.get("target_language", "pt"),
            "system_preset": request.form.get("system_preset", "generic"),
            "tone": request.form.get("tone", ""),
            "party_level": request.form.get("party_level", ""),
            "complexity": request.form.get("complexity", "mediana"),
        }

    book_id = (data.get("book_id") or "").strip()
    theme = (data.get("theme") or "").strip()

    if not _valid_book_id(book_id):
        return jsonify({"error": "valid book_id is required"}), 400
    if not theme:
        return jsonify({"error": "theme is required"}), 400

    character_sheets: list[str] = list(data.get("character_sheets") or [])

    # Optional multipart sheet PDFs — PyMuPDF only, no AI parsing
    if "sheet_files" in request.files:
        for sheet in request.files.getlist("sheet_files"):
            if not sheet.filename:
                continue
            suffix = os.path.splitext(secure_filename(sheet.filename))[1] or ".pdf"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                sheet.save(tmp.name)
                tmp.close()
                text = extract_text_from_pdf(tmp.name)
                if text.strip():
                    character_sheets.append(text.strip())
            finally:
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)

    try:
        result = generate_campaign(
            book_id=book_id,
            theme=theme,
            hook=data.get("hook", ""),
            target_language=data.get("target_language", "pt"),
            system_preset=data.get("system_preset", "generic"),
            tone=data.get("tone", ""),
            party_level=data.get("party_level", ""),
            complexity=data.get("complexity", "mediana"),
            character_sheets=character_sheets or None,
        )
        return jsonify(result), 200
    except BookIndexNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except LlamaServerUnavailable as exc:
        return jsonify({"error": str(exc)}), 503
    except LlamaServerError as exc:
        return jsonify({"error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("RAG generation failed")
        return jsonify({"error": str(exc)}), 500


@rag_bp.route("/books/<book_id>", methods=["GET"])
def rag_book_status(book_id: str):
    """Return index metadata for a book_id."""
    if not _valid_book_id(book_id):
        return jsonify({"error": "invalid book_id"}), 400

    if not index_exists(book_id):
        return jsonify({"error": f"No index for book_id={book_id}"}), 404

    meta = get_book_meta(book_id)
    return jsonify({"book_id": book_id, "indexed": True, **meta}), 200
