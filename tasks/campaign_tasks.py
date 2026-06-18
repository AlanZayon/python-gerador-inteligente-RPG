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
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

from services.book_analysis import build_book_bible, format_inspired_block
from services.campaign_quality import validate_campaign
from services.job_status import mark_failed, mark_processing, save_result, save_status
from services.prompt_templates import build_campaign_prompt, build_expand_retry_prompt
from services.s3_storage import upload_content_to_s3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CAMPAIGN_FOLDER = "campaigns/"
GEMINI_MAX_INPUT_CHARS = int(os.getenv("GEMINI_MAX_INPUT_CHARS", "15000"))
GEMINI_RETRY_ATTEMPTS = int(os.getenv("GEMINI_RETRY_ATTEMPTS", "3"))
GEMINI_MODEL_LITE = os.getenv("GEMINI_MODEL_LITE", "gemini-2.5-flash-lite")
GEMINI_MODEL_FLASH = os.getenv("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
GEMINI_MODEL_PRO = os.getenv("GEMINI_MODEL_PRO", "gemini-2.5-flash")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CONFIGURED = bool(
    GEMINI_API_KEY and GEMINI_API_KEY != "sua_chave_aqui" and len(GEMINI_API_KEY) > 10
)

if GEMINI_CONFIGURED:
    genai.configure(api_key=GEMINI_API_KEY)

PROGRESS_STAGES = {
    "download": (5, "Downloading your rulebook..."),
    "validate": (10, "Validating PDF pages..."),
    "extract": (15, "Extracting text from PDF..."),
    "analyze": (30, "Analyzing your book..."),
    "outline": (50, "Building campaign outline..."),
    "generate": (75, "Weaving your campaign..."),
    "validate_out": (90, "Validating campaign quality..."),
    "upload": (100, "Saving your campaign..."),
}


class GenerationFailedError(Exception):
    pass


def is_gemini_configured() -> bool:
    return GEMINI_CONFIGURED


def _update_progress(job_id: str, stage: str) -> None:
    percent, message = PROGRESS_STAGES.get(stage, (50, "Processing..."))
    mark_processing(job_id, message, progress_percent=percent)


def _model_for_complexity(complexity: str) -> str:
    mapping = {
        "simples": GEMINI_MODEL_LITE,
        "mediana": GEMINI_MODEL_FLASH,
        "complexa": GEMINI_MODEL_PRO,
    }
    return mapping.get(complexity, GEMINI_MODEL_FLASH)


def _model_tier(model_name: str) -> str:
    if "lite" in model_name:
        return "flash-lite"
    if "pro" in model_name:
        return "pro"
    return "flash"


def _call_gemini(model_name: str, prompt: str) -> str:
    model = genai.GenerativeModel(model_name)
    last_error = None
    for attempt in range(1, GEMINI_RETRY_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            if not response.candidates:
                raise ValueError("Empty response from Gemini")
            text = response.text
            if not text or not text.strip():
                raise ValueError("Empty text from Gemini")
            return text
        except Exception as exc:
            last_error = exc
            wait = 2**attempt
            logger.warning("Gemini attempt %s failed: %s. Retrying in %ss...", attempt, exc, wait)
            time.sleep(wait)
    raise last_error


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
    """Offline template — only when Gemini is not configured."""
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


def _generate_campaign_content(
    book_bible: dict,
    book_text: str,
    target_language: str,
    campaign_complexity: str,
    system_preset: str | None,
    party_level: str = "",
    tone: str = "",
    theme: str = "",
    job_id: str | None = None,
) -> tuple[str, dict]:
    """Multi-pass generation. Returns (markdown, metadata)."""
    if not GEMINI_CONFIGURED:
        raise GenerationFailedError("AI generation unavailable — credits will be refunded")

    model_name = _model_for_complexity(campaign_complexity)
    guidelines = get_complexity_guidelines(campaign_complexity)
    meta = {
        "generation_source": "gemini",
        "model_tier": _model_tier(model_name),
        "book_signals": book_bible.get("key_terms", [])[:5],
    }

    if job_id:
        _update_progress(job_id, "outline")

    if campaign_complexity == "complexa":
        outline_prompt = build_campaign_prompt(
            book_bible=book_bible,
            target_language=target_language,
            complexity=campaign_complexity,
            guidelines=guidelines,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            pass_type="outline",
        )
        outline = _call_gemini(model_name, outline_prompt)
        if job_id:
            _update_progress(job_id, "generate")
        expand_prompt = build_campaign_prompt(
            book_bible=book_bible,
            target_language=target_language,
            complexity=campaign_complexity,
            guidelines=guidelines,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            pass_type="expand",
            outline=outline,
        )
        content = _call_gemini(model_name, expand_prompt)
    elif campaign_complexity == "mediana":
        if job_id:
            _update_progress(job_id, "generate")
        outline_prompt = build_campaign_prompt(
            book_bible=book_bible,
            target_language=target_language,
            complexity=campaign_complexity,
            guidelines=guidelines,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            pass_type="outline",
        )
        outline = _call_gemini(model_name, outline_prompt)
        expand_prompt = build_campaign_prompt(
            book_bible=book_bible,
            target_language=target_language,
            complexity=campaign_complexity,
            guidelines=guidelines,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            pass_type="expand",
            outline=outline,
        )
        content = _call_gemini(model_name, expand_prompt)
    else:
        if job_id:
            _update_progress(job_id, "generate")
        prompt = build_campaign_prompt(
            book_bible=book_bible,
            target_language=target_language,
            complexity=campaign_complexity,
            guidelines=guidelines,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            pass_type="full",
        )
        content = _call_gemini(model_name, prompt)

    if job_id:
        _update_progress(job_id, "validate_out")

    passed, issues, score = validate_campaign(content, campaign_complexity)
    meta["quality_score"] = score
    if not passed:
        logger.info("Quality retry for job: %s", issues)
        retry_prompt = build_expand_retry_prompt(content, issues, target_language)
        content = _call_gemini(model_name, retry_prompt)
        passed, issues, score = validate_campaign(content, campaign_complexity)
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
):
    local_file_path = None
    timings: dict[str, int] = {}

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
        _update_progress(job_id, "extract")
        book_text = extract_text_from_pdf(local_file_path)
        timings["extract_ms"] = int((time.time() - t0) * 1000)

        if not book_text or len(book_text.strip()) < 100:
            mark_failed(job_id, "Insufficient text extracted from PDF.")
            cleanup_temp_files(local_file_path)
            return None

        t0 = time.time()
        _update_progress(job_id, "analyze")
        bible_model = GEMINI_MODEL_LITE if GEMINI_CONFIGURED else None
        book_bible = build_book_bible(book_text, model_name=bible_model or GEMINI_MODEL_LITE)
        timings["analyze_ms"] = int((time.time() - t0) * 1000)

        t0 = time.time()
        if not GEMINI_CONFIGURED:
            mark_failed(
                job_id,
                "AI generation unavailable. Your credits have been refunded.",
            )
            cleanup_temp_files(local_file_path)
            return None

        campaign_content, gen_meta = _generate_campaign_content(
            book_bible=book_bible,
            book_text=book_text,
            target_language=target_language,
            campaign_complexity=campaign_complexity,
            system_preset=system_preset,
            party_level=party_level,
            tone=tone,
            theme=theme,
            job_id=job_id,
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
    model_name = GEMINI_MODEL_FLASH
    prompt = f"""You are an RPG campaign designer.

BOOK ANALYSIS:
{json.dumps(book_bible)[:8000]}

CURRENT CAMPAIGN:
{current_content[:20000]}

TASK: Regenerate or expand the section "{section}".
Additional instructions: {instructions}

Output ONLY the new/expanded section in markdown, in {target_language}.
System: {system_preset or 'generic'}
"""
    return _call_gemini(model_name, prompt)
