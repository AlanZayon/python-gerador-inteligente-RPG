"""Planner -> writer -> rubric -> selective revision pipeline."""

from __future__ import annotations

import logging
from typing import Any, Callable

from services.campaign_eval import OVERALL_THRESHOLD, evaluate_rubric, rubric_as_100
from services.campaign_i18n import section_label
from services.campaign_schema import (
    PLAN_JSON_INSTRUCTIONS,
    canonical_complexity,
    state_digest,
    name_registry,
    normalize_plan,
    parse_json_object,
    plan_is_structurally_complete,
    session_brief,
    spec_for,
)
from services.prompt_templates import (
    build_campaign_prompt,
    build_overview_prompt,
    build_plan_prompt,
    build_revise_prompt,
    build_session_prompt,
    build_support_prompt,
)

logger = logging.getLogger(__name__)

MAX_PLAN_ATTEMPTS = 2
MAX_REVISION_PASSES = 2
RetrieveFn = Callable[[str], str]
LlmFn = Callable[[str], str]


def _labels(language: str) -> dict[str, str]:
    return {
        "overview": section_label("overview", language),
        "hook": section_label("hook", language),
        "session": section_label("session", language),
        "npcs": section_label("npcs", language),
        "enemies": section_label("enemies", language),
        "puzzles": section_label("puzzles", language),
        "endings": section_label("endings", language),
        "maps": section_label("maps", language),
        "rewards": section_label("rewards", language),
        "objectives": section_label("objectives", language),
    }


def _split_h2(markdown: str) -> list[tuple[str, str]]:
    text = markdown or ""
    parts = re_split_h2(text)
    return parts


def re_split_h2(text: str) -> list[tuple[str, str]]:
    import re

    chunks = re.split(r"(?m)^##\s+", text)
    if not chunks:
        return []
    preamble = chunks[0]
    sections: list[tuple[str, str]] = []
    if preamble.strip() and not preamble.strip().startswith("#"):
        sections.append(("", preamble.strip()))
    elif preamble.strip().startswith("#"):
        sections.append(("#", preamble.strip()))
    for chunk in chunks[1:]:
        heading, _, body = chunk.partition("\n")
        sections.append((heading.strip(), body.strip()))
    return sections


def assemble_markdown(pieces: list[str]) -> str:
    body = "\n\n".join(p.strip() for p in pieces if p and p.strip())
    return body.strip() + "\n"


def _plan_from_llm(
    llm_fn: LlmFn,
    plan_prompt: str,
    complexity: str,
) -> dict[str, Any] | None:
    raw = llm_fn(plan_prompt)
    parsed = parse_json_object(raw)
    state = normalize_plan(parsed, complexity)
    if state is None:
        logger.info("Plan JSON parse failed")
        return None
    ok, issues = plan_is_structurally_complete(state, complexity)
    if not ok:
        logger.info("Plan incomplete: %s", issues)
        retry = llm_fn(
            plan_prompt
            + "\n\nYour previous JSON missed: "
            + "; ".join(issues)
            + "\nReturn corrected JSON only."
        )
        state = normalize_plan(parse_json_object(retry), complexity)
        if state is None:
            return None
        ok, issues = plan_is_structurally_complete(state, complexity)
        if not ok:
            logger.info("Plan still incomplete: %s", issues)
    return state


def _splice_section(markdown: str, heading: str, new_body: str) -> str:
    import re

    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*\n.*?(?=^##\s+|\Z)"
    )
    replacement = new_body.strip() + "\n\n"
    if pattern.search(markdown or ""):
        return pattern.sub(replacement, markdown, count=1)
    return (markdown or "").rstrip() + "\n\n" + replacement


def generate_campaign_markdown(
    *,
    book_context: str,
    key_terms: list[str],
    target_language: str,
    complexity: str,
    guidelines: str,
    system_preset: str | None,
    party_level: str = "",
    tone: str = "",
    theme: str = "",
    character_sheets: str = "",
    llm_fn: LlmFn,
    retrieve_fn: RetrieveFn | None = None,
    fallback_full_prompt: str = "",
) -> tuple[str, dict[str, Any]]:
    """Hierarchical generation with fallback to a single full prompt."""
    complexity = canonical_complexity(complexity)
    labels = _labels(target_language)
    meta: dict[str, Any] = {
        "pipeline": "plan-write-revise",
        "plan_used": False,
        "revision_passes": 0,
    }

    plan_prompt = build_plan_prompt(
        book_context=book_context,
        target_language=target_language,
        complexity=complexity,
        guidelines=guidelines,
        system_preset=system_preset,
        party_level=party_level,
        tone=tone,
        theme=theme,
        character_sheets=character_sheets,
        json_instructions=PLAN_JSON_INSTRUCTIONS,
    )
    state = None
    for _attempt in range(MAX_PLAN_ATTEMPTS):
        state = _plan_from_llm(llm_fn, plan_prompt, complexity)
        if state:
            break

    if state is None:
        meta["pipeline"] = "fallback-full"
        prompt = fallback_full_prompt or plan_prompt
        return llm_fn(prompt), meta

    meta["plan_used"] = True
    meta["title"] = state.get("title")
    digest = state_digest(state)
    if key_terms and not state.get("grounded_terms"):
        state["grounded_terms"] = key_terms[:10]
        digest = state_digest(state)

    overview = llm_fn(
        build_overview_prompt(
            digest=digest,
            book_context=book_context,
            target_language=target_language,
            system_preset=system_preset,
            overview_label=labels["overview"],
            hook_label=labels["hook"],
        )
    )

    previous = []
    session_parts: list[str] = []
    for session in state.get("sessions") or []:
        extra = ""
        if retrieve_fn:
            query = f"{session.get('title')} {' '.join(session.get('objectives') or [])}"
            try:
                extra = retrieve_fn(query) or ""
            except Exception as exc:
                logger.info("Session retrieve skipped: %s", exc)
        session_md = llm_fn(
            build_session_prompt(
                digest=digest,
                session_json=session_brief(session),
                previous_summary="\n".join(previous[-3:]),
                extra_context=extra,
                target_language=target_language,
                system_preset=system_preset,
                session_label=labels["session"],
                objectives_label=labels["objectives"],
            )
        )
        session_parts.append(session_md)
        previous.append(
            f"S{session.get('number')} {session.get('title')}: "
            + ", ".join(session.get("objectives") or [])
        )

    support = llm_fn(
        build_support_prompt(
            digest=digest,
            book_context=book_context,
            target_language=target_language,
            system_preset=system_preset,
            labels=labels,
        )
    )

    markdown = assemble_markdown([overview, *session_parts, support])
    rubric = evaluate_rubric(
        markdown, complexity=complexity, state=state, key_terms=key_terms
    )
    meta["rubric"] = rubric
    meta["quality_score"] = rubric_as_100(rubric)

    passes = 0
    while (not rubric["passed"]) and passes < MAX_REVISION_PASSES:
        passes += 1
        heading = labels["overview"]
        if "npcs" in rubric["weak_categories"]:
            heading = labels["npcs"]
        elif "gameplay" in rubric["weak_categories"] and session_parts:
            heading = f"{labels['session']} 1"
        sections = re_split_h2(markdown)
        body = ""
        match_heading = heading
        for h, b in sections:
            if h and heading.lower() in h.lower():
                match_heading, body = h, b
                break
        revised = llm_fn(
            build_revise_prompt(
                digest=digest,
                section_heading=match_heading or heading,
                section_body=body,
                issues=rubric["issues"],
                target_language=target_language,
                system_preset=system_preset,
            )
        )
        markdown = _splice_section(markdown, match_heading or heading, revised)
        rubric = evaluate_rubric(
            markdown, complexity=complexity, state=state, key_terms=key_terms
        )
        meta["rubric"] = rubric
        meta["quality_score"] = rubric_as_100(rubric)
    meta["revision_passes"] = passes
    meta["names"] = name_registry(state)
    meta["threshold"] = OVERALL_THRESHOLD
    return markdown, meta
