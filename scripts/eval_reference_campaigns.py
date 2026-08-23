"""Score (and optionally generate) campaigns for the four reference PDFs.

Dry-run (no LLM):
    python scripts/eval_reference_campaigns.py

Live generation (requires 9router + embeddings):
    python scripts/eval_reference_campaigns.py --live
    python scripts/eval_reference_campaigns.py --live --resume
    python scripts/eval_reference_campaigns.py --live --complexities simples
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from services.campaign_eval import evaluate_rubric, format_rubric_report
from services.campaign_pipeline import generate_campaign_markdown
from services.llm_client import complete, is_configured, model_for_complexity
from services.prompt_templates import build_campaign_prompt
from services.rag.context_packer import pack_campaign_context
from services.rag.indexer import ensure_indexed
from services.rag.retrieval import retrieve
from services.system_detect import detect_system_heuristic
from tasks.campaign_tasks import get_complexity_guidelines

logger = logging.getLogger("eval_reference")

REFERENCE_BOOKS = [
    {
        "id": "blood_honor",
        "preset": "blood_honor",
        "pdf": "blood-honor-um-jogo-de-tragedia-samurai-biblioteca-elfica.pdf",
        "theme": "clan honor and a debt that cannot be paid in gold",
    },
    {
        "id": "dnd5e",
        "preset": "dnd5e",
        "pdf": "dampd-5e---livro-do-jogador-2024.pdf",
        "theme": "a coastal city bargaining with something under the tide",
    },
    {
        "id": "gurps",
        "preset": "gurps",
        "pdf": "GURPS_Lite_Fourth_Edition.pdf",
        "theme": "a frontier town where every advantage has a visible cost",
    },
    {
        "id": "fragged",
        "preset": "fragged",
        "pdf": "pdfcoffee.com_fragged-empire-pdf-free.pdf",
        "theme": "scavengers, remnant corporations, and a ship that should not still fly",
    },
]

COMPLEXITIES = ("simples", "mediana", "complexa")
OUT_DIR = ROOT / "examples" / "eval_runs"


def _fixture_markdown(book_id: str, complexity: str) -> str:
    return f"""# Fixture {book_id} {complexity}

## Overview
This fixture exists so the matrix can be scored without an LLM.
Premise, conflict, and stakes are named so the rubric has signal.
If the players wait, the front advances.

## Starting Hook
A named NPC (Kira Voss) offers two approaches: talk or sneak. Failure floods the dock.

## Session 1: Opening Pressure
**Objectives:** Survive the first choice. Find three clues (ledger, salt, witness).
DC 14 check or 3d6 skill roll. If they fail, the clock ticks.

## Session 2: Escalation
Consequences of session 1 change who holds the key.

## Session 3: Crisis
Only used when complexity is not simples.

## Important NPCs
### Kira Voss
**Role:** patron. Want: keep the crew. Secret: she opened the vent.
### Radek
**Role:** rival.

## Enemies and Creatures
Named opposition tied to a faction.

## Campaign Challenges and Puzzles
Three-clue mystery. Social, stealth, and force options.

## Possible Endings
- If they deal: the faction owns the dock.
- If they refuse: the ship leaves without them.

## Maps and Locations
Dry Dock Seven. The Court Stairs.

## Rewards
A named key and a debt.
"""


def _weak_categories(scores: dict[str, float], floor: float = 6.0) -> list[str]:
    return [name for name, value in scores.items() if float(value) < floor]


def _named_items(values: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in values or []:
        if isinstance(item, dict) and str(item.get("name") or "").strip():
            items.append({"name": str(item.get("name")).strip()})
        elif isinstance(item, str) and item.strip():
            items.append({"name": item.strip()})
    return items


def _state_from_meta(gen_meta: dict | None) -> dict[str, Any] | None:
    if not isinstance(gen_meta, dict):
        return None
    names = gen_meta.get("names")
    if not isinstance(names, dict):
        return None
    return {
        "npcs": _named_items(names.get("npcs")),
        "factions": _named_items(names.get("factions")),
        "locations": _named_items(names.get("locations")),
        "fronts": _named_items(names.get("fronts")),
        "grounded_terms": [t for t in (names.get("terms") or []) if str(t).strip()],
    }


def _write_matrix(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _generate_live(book: dict, complexity: str, packed: dict, preset: str) -> tuple[str, dict]:
    guidelines = get_complexity_guidelines(complexity)
    book_id = packed["book_id"] if "book_id" in packed else None

    def llm_fn(prompt: str) -> str:
        return complete(prompt, model=model_for_complexity(complexity))

    def retrieve_fn(query: str) -> str:
        if not book_id:
            return ""
        chunks = retrieve(book_id, theme=query, hook=book["theme"], top_k=3)
        return "\n\n".join((c.get("text") or "") for c in chunks[:3])

    fallback = build_campaign_prompt(
        book_context=packed["book_context"],
        target_language="en",
        complexity=complexity,
        guidelines=guidelines,
        system_preset=preset,
        theme=book["theme"],
        pass_type="full",
    )
    return generate_campaign_markdown(
        book_context=packed["book_context"],
        key_terms=packed.get("key_terms") or [],
        target_language="en",
        complexity=complexity,
        guidelines=guidelines,
        system_preset=preset,
        theme=book["theme"],
        llm_fn=llm_fn,
        retrieve_fn=retrieve_fn,
        fallback_full_prompt=fallback,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reuse markdown files already on disk")
    parser.add_argument(
        "--complexities",
        default=",".join(COMPLEXITIES),
        help="Comma-separated: simples,mediana,complexa",
    )
    parser.add_argument("--books", default="", help="Comma-separated book ids")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    wanted_complexity = tuple(
        item.strip() for item in args.complexities.split(",") if item.strip() in COMPLEXITIES
    ) or COMPLEXITIES
    wanted_books = {item.strip() for item in args.books.split(",") if item.strip()}

    if args.live and not is_configured():
        print("9router is not configured (NINEROUTER_KEY). Aborting live run.")
        return 2

    index_cache: dict[str, dict] = {}
    pack_cache: dict[tuple[str, str], dict] = {}
    rows: list[dict] = []

    books = [b for b in REFERENCE_BOOKS if not wanted_books or b["id"] in wanted_books]
    for book in books:
        pdf = ROOT / book["pdf"]
        snippet = ""
        indexed = None
        if pdf.exists():
            try:
                import fitz

                doc = fitz.open(pdf)
                snippet = "".join(doc[i].get_text() for i in range(min(4, len(doc))))
                doc.close()
            except Exception as exc:
                snippet = str(exc)
        detected = detect_system_heuristic(snippet) or detect_system_heuristic(book["pdf"])
        preset = detected or book["preset"]

        if args.live:
            if not pdf.exists():
                print(f"MISSING PDF {book['pdf']}")
                continue
            if book["id"] not in index_cache:
                logger.info("Indexing %s", book["pdf"])
                indexed = ensure_indexed(str(pdf), source_filename=book["pdf"])
                index_cache[book["id"]] = indexed
                logger.info("Indexed %s as %s", book["id"], indexed.get("book_id"))
            indexed = index_cache[book["id"]]

        for complexity in wanted_complexity:
            cell_id = f"{book['id']}_{complexity}"
            md_path = OUT_DIR / f"{cell_id}.md"
            meta_path = OUT_DIR / f"{cell_id}.meta.json"
            markdown = ""
            gen_meta: dict = {}
            error = None

            if args.live:
                try:
                    if args.resume and md_path.exists() and md_path.stat().st_size > 400:
                        markdown = md_path.read_text(encoding="utf-8")
                        gen_meta = {"pipeline": "resumed"}
                        if meta_path.exists():
                            try:
                                loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                                if isinstance(loaded, dict):
                                    gen_meta = loaded
                                    gen_meta.setdefault("pipeline", "resumed")
                            except json.JSONDecodeError:
                                pass
                        logger.info("Resume %s", cell_id)
                    else:
                        pack_key = (book["id"], complexity)
                        if pack_key not in pack_cache:
                            packed = pack_campaign_context(
                                indexed["book_id"],
                                theme=book["theme"],
                                hook=book["theme"],
                                system_preset=preset,
                                complexity=complexity,
                            )
                            packed["book_id"] = indexed["book_id"]
                            pack_cache[pack_key] = packed
                        packed = pack_cache[pack_key]
                        logger.info("Generating %s (chunks=%s)", cell_id, packed.get("chunks_used"))
                        markdown, gen_meta = _generate_live(book, complexity, packed, preset)
                        md_path.write_text(markdown, encoding="utf-8")
                        meta_path.write_text(
                            json.dumps(gen_meta, indent=2, default=str),
                            encoding="utf-8",
                        )
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    logger.exception("Failed %s", cell_id)
                    markdown = markdown or f"# Generation failed\n\n{error}\n\n{traceback.format_exc()[-1500:]}"
                    md_path.write_text(markdown, encoding="utf-8")
            else:
                markdown = _fixture_markdown(book["id"], complexity)

            key_terms = []
            packed_for_terms = pack_cache.get((book["id"], complexity))
            if packed_for_terms:
                key_terms = packed_for_terms.get("key_terms") or []
            try:
                rubric = evaluate_rubric(
                    markdown,
                    complexity=complexity,
                    key_terms=key_terms or [book["id"]],
                    state=_state_from_meta(gen_meta),
                )
            except Exception as exc:
                error = error or f"{type(exc).__name__}: {exc}"
                logger.exception("Rubric failed %s", cell_id)
                rubric = {
                    "scores": {
                        "narrative": 0,
                        "gameplay": 0,
                        "npcs": 0,
                        "world": 0,
                        "content": 0,
                        "consistency": 0,
                        "gm_utility": 0,
                    },
                    "overall": 0.0,
                    "passed": False,
                    "word_count": 0,
                    "session_count": 0,
                }
            weak = _weak_categories(rubric["scores"])
            row = {
                "book": book["id"],
                "pdf_present": pdf.exists(),
                "detected_system": detected,
                "preset_used": preset,
                "complexity": complexity,
                "live": bool(args.live),
                "pipeline": (gen_meta or {}).get("pipeline"),
                "overall": rubric["overall"],
                "passed": rubric["passed"] and not error,
                "scores": rubric["scores"],
                "weak_categories": weak,
                "word_count": rubric.get("word_count"),
                "session_count": rubric.get("session_count"),
                "error": error,
                "markdown_path": str(md_path) if args.live else None,
            }
            rows.append(row)
            flag = "FAIL" if error or weak or not rubric["passed"] else "PASS"
            print(
                f"{flag:4} {book['id']:12} {complexity:8} "
                f"detect={detected!s:12} overall={rubric['overall']:.2f} "
                f"weak={weak or '-'}"
            )
            print(format_rubric_report(rubric))
            print("-", flush=True)
            if args.live:
                _write_matrix(OUT_DIR / "live_matrix.json", rows)

    out = OUT_DIR / ("live_matrix.json" if args.live else "reference_matrix.json")
    _write_matrix(out, rows)
    weak_rows = [r for r in rows if r.get("weak_categories") or not r.get("passed")]
    print("wrote", out)
    print(f"cells={len(rows)} weak_or_failed={len(weak_rows)}")
    return 0 if not (args.live and any(r.get("error") for r in rows)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
