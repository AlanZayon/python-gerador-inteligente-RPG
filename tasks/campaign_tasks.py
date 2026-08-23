"""
Campaign generation pipeline — multi-pass, book-aware, quality-validated.
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime
from urllib.parse import urlparse

import fitz
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

from services.book_analysis import format_inspired_block
from services.campaign_quality import validate_campaign
from services.job_status import mark_failed, mark_processing, save_result, save_status
from services.llm_client import (
    complete,
    is_configured,
    model_flash,
    model_for_complexity,
)
from services.prompt_templates import build_campaign_prompt, build_expand_retry_prompt
from services.s3_storage import upload_content_to_s3, generate_presigned_url
from services.sheet_extraction import (
    extract_pdf_text,
    parse_character_sheet,
    format_sheets_for_prompt,
    extract_character_names,
)
from services.sheet_validation import validate_sheets_json_size

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CAMPAIGN_FOLDER = "campaigns/"

PROGRESS_STAGES = {
    "download": (5, "Downloading your rulebook..."),
    "validate": (10, "Validating PDF pages..."),
    "fingerprint": (18, "Fingerprinting your rulebook..."),
    "extract": (22, "Extracting text from PDF..."),
    "sheets": (28, "Reading character sheets..."),
    "analyze": (40, "Indexing and retrieving from your book..."),
    "outline": (55, "Building campaign outline..."),
    "generate": (75, "Weaving your campaign..."),
    "validate_out": (90, "Validating campaign quality..."),
    "upload": (100, "Saving your campaign..."),
}


class GenerationFailedError(Exception):
    pass


def is_llm_configured() -> bool:
    return is_configured()


def is_gemini_configured() -> bool:
    """Backward-compatible alias for is_llm_configured."""
    return is_configured()


def _update_progress(job_id: str, stage: str) -> None:
    percent, message = PROGRESS_STAGES.get(stage, (50, "Processing..."))
    mark_processing(job_id, message, progress_percent=percent)


def _model_tier(model_name: str) -> str:
    name = (model_name or "").lower()
    if any(token in name for token in ("lite", "haiku", "nano", "flash-lite")):
        return "lite"
    if any(token in name for token in ("pro", "opus", "sonnet")):
        return "pro"
    return "flash"


def _call_llm(model_name: str, prompt: str) -> str:
    return complete(prompt, model=model_name)


def download_file_from_s3(file_url, job_id):
    temp_dir = os.path.join(tempfile.gettempdir(), f"rpg_job_{job_id}")
    os.makedirs(temp_dir, exist_ok=True)
    parsed_url = urlparse(file_url)
    filename = os.path.basename(parsed_url.path)
    local_path = os.path.join(temp_dir, secure_filename(filename))
    response = requests.get(file_url, stream=True, timeout=60)
    response.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return local_path


def cleanup_temp_files(file_path):
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
    except Exception as exc:
        logger.warning("Cleanup failed: %s", exc)


def validate_pdf(file_path):
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        if page_count == 0:
            return False, "Empty PDF"
        if page_count > 500:
            return False, "PDF too large (max 500 pages)"
        return True, "OK"
    except Exception:
        return False, "Corrupted or unreadable PDF"


def extract_text_from_pdf(file_path):
    try:
        full_text = ""
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                full_text += f"\n--- Página {page_num + 1} ---\n{page.get_text()}"
        return full_text
    except Exception as exc:
        logger.error("Text extraction failed: %s", exc)
        return ""


def get_complexity_guidelines(complexity):
    guidelines = {
        "simple": "- 1-2 sessions of 3-4 hours\n- Linear story, 2-3 encounters\n- 1-2 NPCs, 1 main location",
        "medium": "- 3-4 sessions\n- Branching choices, 4-6 encounters\n- 3-5 NPCs, 2-3 locations",
        "complex": "- 5+ sessions\n- Non-linear arcs, 8+ encounters\n- 6+ NPCs, 4+ locations, multiple endings",
    }
    complexity_map = {"simples": "simple", "mediana": "medium", "complexa": "complex"}
    english = complexity_map.get(complexity.lower(), complexity.lower())
    return guidelines.get(english, guidelines["medium"])


def format_campaign_output(content, complexity, language, title=None, inspired_block=""):
    complexity_map = {"simples": "simple", "mediana": "medium", "complexa": "complex"}
    english = complexity_map.get(complexity.lower(), complexity.lower())
    session_counts = {"simple": "1-2", "medium": "3-4", "complex": "5+"}
    display = {"simple": "Simple", "medium": "Medium", "complex": "Complex"}.get(
        english, english.capitalize()
    )
    title_line = f"# {title}" if title else ""
    return f"""# RPG Campaign — {display.upper()}
{title_line}
**Duration**: {session_counts.get(english, "3-4")} sessions
**Language**: {language}
**Generated**: {datetime.now().strftime("%m/%d/%Y %H:%M")}
{inspired_block}
---

{content}

---

*Generated from your uploaded rulebook. Review balance for your table.*
"""


def generate_fallback_campaign(complexity, language):
    """Offline template — only when 9router is not configured."""
    from deep_translator import GoogleTranslator

    base = {
        "simples": "# The Whispering Cellar\n\nA one-shot mystery beneath an old mill...",
        "mediana": "# The Shattered Crown\n\nA 4-session succession crisis in a border kingdom...",
        "complexa": "# Echoes of the Deep Archive\n\nA 6-session planar library arc...",
    }
    content = base.get(complexity, base["mediana"])
    if language != "en":
        try:
            content = GoogleTranslator(source="auto", target=language).translate(content)
        except Exception:
            pass
    return format_campaign_output(content, complexity, language)


def _process_character_sheets(
    job_id: str,
    sheet_s3_keys: list[str],
    system_preset: str | None,
) -> tuple[list[dict], str, list[str]]:
    """Download, extract, and parse character sheet PDFs."""
    sheets: list[dict] = []
    for i, s3_key in enumerate(sheet_s3_keys):
        file_url = generate_presigned_url(s3_key)
        local_path = download_file_from_s3(file_url, f"{job_id}_sheet_{i}")
        try:
            text = extract_pdf_text(local_path)
            if not text or len(text.strip()) < 20:
                mark_failed(job_id, f"Insufficient text in character sheet {i + 1}.")
                cleanup_temp_files(local_path)
                return [], "", []
            parsed = parse_character_sheet(text, system_preset)
            sheets.append(parsed)
        finally:
            cleanup_temp_files(local_path)

    size_err = validate_sheets_json_size(sheets)
    if size_err:
        mark_failed(job_id, size_err)
        return [], "", []

    sheets_json = json.dumps(sheets, ensure_ascii=False)
    from services.jobs_db import update_job_character_sheets

    update_job_character_sheets(job_id, sheets_json)
    sheets_block = format_sheets_for_prompt(sheets)
    names = extract_character_names(sheets)
    return sheets, sheets_block, names


def _prompt_kwargs(
    book_context: str,
    target_language: str,
    campaign_complexity: str,
    guidelines: str,
    system_preset: str | None,
    party_level: str,
    tone: str,
    theme: str,
    character_sheets: str,
    pass_type: str,
    outline: str = "",
) -> dict:
    return {
        "book_context": book_context,
        "target_language": target_language,
        "complexity": campaign_complexity,
        "guidelines": guidelines,
        "system_preset": system_preset,
        "party_level": party_level,
        "tone": tone,
        "theme": theme,
        "pass_type": pass_type,
        "outline": outline,
        "character_sheets": character_sheets,
    }


def _generate_campaign_content(
    book_bible: dict,
    book_context: str,
    target_language: str,
    campaign_complexity: str,
    system_preset: str | None,
    party_level: str = "",
    tone: str = "",
    theme: str = "",
    job_id: str | None = None,
    character_sheets: str = "",
    character_names: list[str] | None = None,
) -> tuple[str, dict]:
    """Multi-pass generation. Returns (markdown, metadata)."""
    if not is_configured():
        raise GenerationFailedError("AI generation unavailable — credits will be refunded")

    model_name = model_for_complexity(campaign_complexity)
    guidelines = get_complexity_guidelines(campaign_complexity)
    key_terms = book_bible.get("key_terms") or []
    meta = {
        "generation_source": "9router",
        "model_tier": _model_tier(model_name),
        "book_signals": key_terms[:5],
    }

    if job_id:
        _update_progress(job_id, "outline")

    if campaign_complexity == "complexa":
        outline_prompt = build_campaign_prompt(
            **_prompt_kwargs(
                book_context,
                target_language,
                campaign_complexity,
                guidelines,
                system_preset,
                party_level,
                tone,
                theme,
                character_sheets,
                "outline",
            )
        )
        outline = _call_llm(model_name, outline_prompt)
        if job_id:
            _update_progress(job_id, "generate")
        expand_prompt = build_campaign_prompt(
            **_prompt_kwargs(
                book_context,
                target_language,
                campaign_complexity,
                guidelines,
                system_preset,
                party_level,
                tone,
                theme,
                character_sheets,
                "expand",
                outline=outline,
            )
        )
        content = _call_llm(model_name, expand_prompt)
    elif campaign_complexity == "mediana":
        if job_id:
            _update_progress(job_id, "generate")
        outline_prompt = build_campaign_prompt(
            **_prompt_kwargs(
                book_context,
                target_language,
                campaign_complexity,
                guidelines,
                system_preset,
                party_level,
                tone,
                theme,
                character_sheets,
                "outline",
            )
        )
        outline = _call_llm(model_name, outline_prompt)
        expand_prompt = build_campaign_prompt(
            **_prompt_kwargs(
                book_context,
                target_language,
                campaign_complexity,
                guidelines,
                system_preset,
                party_level,
                tone,
                theme,
                character_sheets,
                "expand",
                outline=outline,
            )
        )
        content = _call_llm(model_name, expand_prompt)
    else:
        if job_id:
            _update_progress(job_id, "generate")
        prompt = build_campaign_prompt(
            **_prompt_kwargs(
                book_context,
                target_language,
                campaign_complexity,
                guidelines,
                system_preset,
                party_level,
                tone,
                theme,
                character_sheets,
                "full",
            )
        )
        content = _call_llm(model_name, prompt)

    if job_id:
        _update_progress(job_id, "validate_out")

    passed, issues, score = validate_campaign(
        content,
        campaign_complexity,
        character_names=character_names,
        key_terms=key_terms,
    )
    meta["quality_score"] = score
    if not passed:
        logger.info("Quality retry for job: %s", issues)
        retry_prompt = build_expand_retry_prompt(
            content, issues, target_language, key_terms=key_terms
        )
        content = _call_llm(model_name, retry_prompt)
        passed, issues, score = validate_campaign(
            content,
            campaign_complexity,
            character_names=character_names,
            key_terms=key_terms,
        )
        meta["quality_score"] = score
        if not passed:
            raise GenerationFailedError(
                f"Campaign quality below threshold: {'; '.join(issues)}"
            )

    inspired = format_inspired_block(book_bible)
    meta["word_count"] = len(content.split())
    meta["session_count"] = content.lower().count("session") + content.lower().count("sessão")
    formatted = format_campaign_output(
        content, campaign_complexity, target_language, inspired_block=inspired
    )
    return formatted, meta


def save_campaign_to_s3(campaign_content, original_filename):
    base_name = os.path.splitext(secure_filename(original_filename))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    campaign_filename = f"campaign_{base_name}_{timestamp}.md"
    return upload_content_to_s3(campaign_content, campaign_filename)


def process_campaign_generation(
    job_id,
    file_url,
    filename,
    target_language,
    campaign_complexity,
    system_preset=None,
    party_level="",
    tone="",
    theme="",
    use_character_sheets=False,
    sheet_s3_keys=None,
):
    local_file_path = None
    timings: dict[str, int] = {}
    sheet_s3_keys = sheet_s3_keys or []
    character_sheets_block = ""
    character_names: list[str] = []

    try:
        t0 = time.time()
        _update_progress(job_id, "download")
        local_file_path = download_file_from_s3(file_url, job_id)
        timings["download_ms"] = int((time.time() - t0) * 1000)

        t0 = time.time()
        _update_progress(job_id, "validate")
        is_valid, validation_msg = validate_pdf(local_file_path)
        timings["validate_ms"] = int((time.time() - t0) * 1000)
        if not is_valid:
            mark_failed(job_id, validation_msg)
            cleanup_temp_files(local_file_path)
            return None

        t0 = time.time()
        _update_progress(job_id, "fingerprint")
        from services.rag.indexer import ensure_indexed
        from services.rag.context_packer import pack_campaign_context

        try:
            indexed = ensure_indexed(local_file_path, source_filename=filename)
        except ValueError as exc:
            mark_failed(job_id, str(exc))
            cleanup_temp_files(local_file_path)
            return None
        timings["fingerprint_ms"] = int((time.time() - t0) * 1000)

        if use_character_sheets and sheet_s3_keys:
            t0 = time.time()
            _update_progress(job_id, "sheets")
            _sheets, character_sheets_block, character_names = _process_character_sheets(
                job_id, sheet_s3_keys, system_preset
            )
            if not _sheets:
                cleanup_temp_files(local_file_path)
                return None
            timings["sheets_ms"] = int((time.time() - t0) * 1000)

        t0 = time.time()
        _update_progress(job_id, "analyze")
        packed = pack_campaign_context(
            indexed["book_id"],
            theme=theme,
            hook=theme,
            system_preset=system_preset,
            complexity=campaign_complexity,
        )
        if packed["chunks_used"] <= 0:
            mark_failed(job_id, "Could not retrieve usable context from the rulebook.")
            cleanup_temp_files(local_file_path)
            return None
        book_bible = {
            "key_terms": packed["key_terms"],
            "setting": packed.get("setting") or "",
            "book_id": indexed["book_id"],
            "book_context": packed["book_context"][:12000],
        }
        timings["analyze_ms"] = int((time.time() - t0) * 1000)

        t0 = time.time()
        if not is_configured():
            mark_failed(
                job_id,
                "AI generation unavailable. Your credits have been refunded.",
            )
            cleanup_temp_files(local_file_path)
            return None

        campaign_content, gen_meta = _generate_campaign_content(
            book_bible=book_bible,
            book_context=packed["book_context"],
            target_language=target_language,
            campaign_complexity=campaign_complexity,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            job_id=job_id,
            character_sheets=character_sheets_block,
            character_names=character_names or None,
        )
        timings["generate_ms"] = int((time.time() - t0) * 1000)

        t0 = time.time()
        _update_progress(job_id, "upload")
        upload_result = save_campaign_to_s3(campaign_content, filename)
        timings["upload_ms"] = int((time.time() - t0) * 1000)

        cleanup_temp_files(local_file_path)

        result = {
            "campaign_url": upload_result["file_url"],
            "s3_key": upload_result["s3_key"],
            "preview": campaign_content[:500] + "..." if len(campaign_content) > 500 else campaign_content,
            "file_size": len(campaign_content),
            "timings": timings,
            "book_bible": book_bible,
            "book_id": indexed["book_id"],
            "index_reused": bool(indexed.get("index_reused")),
            "chunks_used": packed["chunks_used"],
            **gen_meta,
        }
        save_status(job_id, "completed", result)
        save_result(job_id, result)
        logger.info("Job %s completed (quality=%s)", job_id, gen_meta.get("quality_score"))
        return result

    except GenerationFailedError as exc:
        logger.error("Generation failed for job %s: %s", job_id, exc)
        mark_failed(job_id, str(exc))
        cleanup_temp_files(local_file_path if local_file_path else None)
        return None
    except Exception as exc:
        logger.error("Job %s error: %s", job_id, exc)
        mark_failed(job_id, str(exc))
        cleanup_temp_files(local_file_path if local_file_path else None)
        return None


def regenerate_section(
    book_bible: dict,
    current_content: str,
    section: str,
    instructions: str,
    target_language: str,
    system_preset: str | None = None,
) -> str:
    """Regenerate a campaign section (1 credit)."""
    model_name = model_flash()
    book_context = ""
    if isinstance(book_bible, dict):
        book_context = book_bible.get("book_context") or json.dumps(book_bible)[:8000]
    else:
        book_context = str(book_bible)[:8000]
    prompt = f"""You are an RPG campaign designer.

BOOK CONTEXT:
{book_context}

CURRENT CAMPAIGN:
{current_content[:20000]}

TASK: Regenerate or expand the section "{section}".
Additional instructions: {instructions}

Output ONLY the new/expanded section in markdown, in {target_language}.
System: {system_preset or 'generic'}
Reuse names and terms from the book context.
"""
    return _call_llm(model_name, prompt)
