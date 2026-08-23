"""Normalize LLM campaign markdown into a stable heading schema for the UI."""

from __future__ import annotations

import re

from services.campaign_i18n import (
    INSPIRED_RE,
    KNOWN_SECTION_RE,
    SESSION_NUMBER_RE,
    detect_pattern,
    lang_code,
    section_label,
)

WRAPPER_TITLE = re.compile(r"^RPG Campaign\b", re.IGNORECASE)
GENERATED_FOOTER = re.compile(
    r"\n---\s*\n+\*Generated from your uploaded rulebook\..*$",
    re.IGNORECASE | re.DOTALL,
)
META_LINE = re.compile(
    r"^\*\*(Duration|Language|Generated)\*\*\s*:",
    re.IGNORECASE,
)
KNOWN_SECTION = KNOWN_SECTION_RE
SECTION_KEYS = (
    "overview",
    "hook",
    "npcs",
    "enemies",
    "puzzles",
    "endings",
    "maps",
    "rewards",
)


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text, flags=re.I)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def clean_heading_text(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^\*{1,2}(.+?)\*{1,2}$", r"\1", text)
    text = re.sub(r"^`(.+?)`$", r"\1", text)
    return text.strip()


def extract_campaign_title(content: str) -> str:
    titles = [clean_heading_text(t) for t in re.findall(r"^#\s+(.+)$", content or "", re.MULTILINE)]
    for cleaned in titles:
        if WRAPPER_TITLE.match(cleaned) or KNOWN_SECTION.match(cleaned):
            continue
        return cleaned
    for cleaned in titles:
        if not WRAPPER_TITLE.match(cleaned):
            return cleaned
    return "Campaign"


def _session_parts(text: str) -> tuple[str, str, str] | None:
    match = SESSION_NUMBER_RE.search(text)
    if not match:
        return None
    num = next((g for g in match.groups() if g), "1")
    rest = text[match.end() :].strip(" :.—–-")
    optional = ""
    opt_m = re.match(r"\(([^)]+)\)\s*[:.\-—–]?\s*(.*)$", rest)
    if opt_m:
        optional = opt_m.group(1)
        rest = (opt_m.group(2) or "").strip()
    return num, optional, rest


def _canon_h2(text: str, language: str) -> str | None:
    """Canonical H2 text, empty string to drop the section, or None to keep as-is."""
    if INSPIRED_RE.search(text):
        return ""
    parts = _session_parts(text)
    if parts:
        num, optional, rest = parts
        label = section_label("session", language)
        suffix = f" ({optional})" if optional else ""
        if rest:
            return f"{label} {num}{suffix}: {rest}"
        return f"{label} {num}{suffix}"
    for key in SECTION_KEYS:
        detect_key = "npc" if key == "npcs" else key
        if re.match(rf"^(?:{detect_pattern(detect_key)})", text, re.IGNORECASE):
            extra = text.split(":", 1)[1].strip() if ":" in text else ""
            base = section_label(key, language)
            return f"{base}: {extra}" if extra else base
    return None


def normalize_campaign_markdown(content: str, language: str = "en") -> str:
    """Force a single H1 title, H2 sections, H3 beats, and drop wrapper chrome."""
    if not (content or "").strip():
        return content or ""

    text = GENERATED_FOOTER.sub("", _strip_fences(content))
    language = lang_code(language)
    title = extract_campaign_title(text)

    out: list[str] = []
    emitted_title = False
    skip_block = False

    for line in text.replace("\r\n", "\n").split("\n"):
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if not heading:
            if skip_block:
                continue
            if not out and (not line.strip() or META_LINE.match(line) or line.strip() == "---"):
                continue
            out.append(line)
            continue

        raw = clean_heading_text(heading.group(2))
        level = min(len(heading.group(1)), 3)

        if WRAPPER_TITLE.match(raw):
            skip_block = False
            continue

        if level == 1:
            if raw == title:
                if not emitted_title:
                    out.append(f"# {title}")
                    emitted_title = True
                skip_block = False
                continue
            if KNOWN_SECTION.match(raw) or SESSION_NUMBER_RE.search(raw):
                level = 2
            else:
                level = 2

        if level == 2:
            canon = _canon_h2(raw, language)
            if canon == "":
                skip_block = True
                continue
            skip_block = False
            heading_text = canon if canon is not None else raw
            out.append(f"## {heading_text}")
            continue

        skip_block = False
        out.append(f"{'#' * level} {raw}")

    if not emitted_title:
        out.insert(0, f"# {title}")
        out.insert(1, "")

    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out).strip())
    return cleaned + "\n"
