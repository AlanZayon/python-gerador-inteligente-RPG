"""Localized campaign section labels and detection aliases.

Covers every language the generator accepts: en, pt, es, fr, de, it, ja, ko, zh, ru.
"""

from __future__ import annotations

import re

LANGS = ("en", "pt", "es", "fr", "de", "it", "ja", "ko", "zh", "ru")

LABELS: dict[str, dict[str, str]] = {
    "overview": {
        "en": "Overview",
        "pt": "Visão Geral",
        "es": "Visión general",
        "fr": "Aperçu",
        "de": "Überblick",
        "it": "Panoramica",
        "ja": "概要",
        "ko": "개요",
        "zh": "概览",
        "ru": "Обзор",
    },
    "hook": {
        "en": "Starting Hook",
        "pt": "Gancho Inicial",
        "es": "Gancho inicial",
        "fr": "Accroche",
        "de": "Einstieg",
        "it": "Gancio iniziale",
        "ja": "導入",
        "ko": "도입",
        "zh": "开场钩子",
        "ru": "Завязка",
    },
    "session": {
        "en": "Session",
        "pt": "Sessão",
        "es": "Sesión",
        "fr": "Session",
        "de": "Sitzung",
        "it": "Sessione",
        "ja": "セッション",
        "ko": "세션",
        "zh": "回合",
        "ru": "Сессия",
    },
    "npcs": {
        "en": "Important NPCs",
        "pt": "PNJs Importantes",
        "es": "PNJs importantes",
        "fr": "PNJ importants",
        "de": "Wichtige NSCs",
        "it": "PNG importanti",
        "ja": "重要NPC",
        "ko": "주요 NPC",
        "zh": "重要NPC",
        "ru": "Важные NPC",
    },
    "enemies": {
        "en": "Enemies and Creatures",
        "pt": "Inimigos e Criaturas",
        "es": "Enemigos y criaturas",
        "fr": "Ennemis et créatures",
        "de": "Gegner und Kreaturen",
        "it": "Nemici e creature",
        "ja": "敵とクリーチャー",
        "ko": "적과 생물",
        "zh": "敌人与生物",
        "ru": "Враги и существа",
    },
    "puzzles": {
        "en": "Campaign Challenges and Puzzles",
        "pt": "Desafios e Enigmas",
        "es": "Desafíos y enigmas",
        "fr": "Défis et énigmes",
        "de": "Herausforderungen und Rätsel",
        "it": "Sfide ed enigmi",
        "ja": "挑戦と謎",
        "ko": "도전과 수수께끼",
        "zh": "挑战与谜题",
        "ru": "Испытания и загадки",
    },
    "endings": {
        "en": "Possible Endings",
        "pt": "Finais Possíveis",
        "es": "Finales posibles",
        "fr": "Fins possibles",
        "de": "Mögliche Enden",
        "it": "Finali possibili",
        "ja": "可能な結末",
        "ko": "가능한 결말",
        "zh": "可能的结局",
        "ru": "Возможные концовки",
    },
    "maps": {
        "en": "Maps and Locations",
        "pt": "Mapas e Locais",
        "es": "Mapas y lugares",
        "fr": "Cartes et lieux",
        "de": "Karten und Orte",
        "it": "Mappe e luoghi",
        "ja": "地図と場所",
        "ko": "지도와 장소",
        "zh": "地图与地点",
        "ru": "Карты и локации",
    },
    "rewards": {
        "en": "Rewards",
        "pt": "Recompensas",
        "es": "Recompensas",
        "fr": "Récompenses",
        "de": "Belohnungen",
        "it": "Ricompense",
        "ja": "報酬",
        "ko": "보상",
        "zh": "奖励",
        "ru": "Награды",
    },
    "objectives": {
        "en": "Session Objectives",
        "pt": "Objetivos da Sessão",
        "es": "Objetivos de la sesión",
        "fr": "Objectifs de la session",
        "de": "Sitzungsziele",
        "it": "Obiettivi della sessione",
        "ja": "セッションの目的",
        "ko": "세션 목표",
        "zh": "回合目标",
        "ru": "Цели сессии",
    },
}

DETECT: dict[str, tuple[str, ...]] = {
    "overview": (
        "overview",
        "visão geral",
        "visao geral",
        "resumo",
        "sinopse",
        "visión general",
        "vision general",
        "sinopsis",
        "resumen",
        "aperçu",
        "apercu",
        "synopsis",
        "résumé",
        "vue d'ensemble",
        "überblick",
        "uberblick",
        "zusammenfassung",
        "panoramica",
        "introduzione",
        "概要",
        "あらすじ",
        "概述",
        "概览",
        "简介",
        "개요",
        "개관",
        "обзор",
        "введение",
    ),
    "hook": (
        "starting hook",
        "opening hook",
        "gancho inicial",
        "hook inicial",
        "gancho",
        "accroche",
        "mise en bouche",
        "einstieg",
        "aufhänger",
        "gancio iniziale",
        "gancho inicial",
        "導入",
        "導入部",
        "도입",
        "开场",
        "钩子",
        "завязка",
        "крючок",
    ),
    "session": (
        "session",
        "sessão",
        "sessao",
        "sesión",
        "sesion",
        "séance",
        "seance",
        "sitzung",
        "abenteuer",
        "sessione",
        "セッション",
        "세션",
        "回合",
        "会话",
        "сессия",
    ),
    "npc": (
        "important npcs",
        "important npc",
        "npcs",
        "npc",
        "pnjs importantes",
        "pnj importantes",
        "pnjs",
        "pnj",
        "personagens importantes",
        "personagens",
        "personagem",
        "personajes",
        "personnages",
        "charaktere",
        "wichtige nscs",
        "nscs",
        "nsc",
        "png importanti",
        "personaggi",
        "nichtspieler",
        "重要npc",
        "主要 npc",
        "주요 npc",
        "등장인물",
        "비플레이어",
        "非玩家",
        "角色",
        "キャラクター",
        "非プレイヤー",
        "персонажи",
        "персонаж",
        "важные npc",
        "нпс",
        "нип",
    ),
    "enemies": (
        "enemies",
        "creatures",
        "inimigos",
        "criaturas",
        "enemigos",
        "criaturas",
        "ennemis",
        "créatures",
        "creatures",
        "gegner",
        "kreaturen",
        "nemici",
        "creature",
        "敵",
        "クリーチャー",
        "적",
        "생물",
        "敌人",
        "生物",
        "враги",
        "существа",
    ),
    "puzzles": (
        "puzzles",
        "puzzle",
        "challenges",
        "desafios",
        "enigmas",
        "desafíos",
        "enigmas",
        "défis",
        "énigmes",
        "herausforderungen",
        "rätsel",
        "sfide",
        "enigmi",
        "謎",
        "挑戦",
        "수수께끼",
        "도전",
        "谜题",
        "挑战",
        "загадки",
        "испытания",
    ),
    "endings": (
        "possible endings",
        "endings",
        "finais",
        "finales",
        "fins possibles",
        "fins",
        "enden",
        "finali",
        "結末",
        "결말",
        "结局",
        "концовки",
        "финалы",
    ),
    "maps": (
        "maps and locations",
        "locations",
        "maps",
        "mapas e locais",
        "mapas",
        "locais",
        "lugares",
        "cartes",
        "lieux",
        "karten",
        "orte",
        "mappe",
        "luoghi",
        "地図",
        "場所",
        "지도",
        "장소",
        "地图",
        "地点",
        "карты",
        "локации",
    ),
    "rewards": (
        "rewards",
        "treasure",
        "recompensas",
        "tesouro",
        "recompensas",
        "tesoro",
        "récompenses",
        "tresor",
        "belohnungen",
        "schatz",
        "ricompense",
        "tesoro",
        "報酬",
        "보상",
        "奖励",
        "награды",
        "сокровища",
    ),
    "inspired": (
        "inspired by your book",
        "inspired by",
        "inspirado no seu livro",
        "inspirado",
        "inspirado en",
        "inspiré",
        "inspiriert",
        "ispirato",
        "インスパイア",
        "영감",
        "灵感",
        "вдохновлено",
    ),
}


def lang_code(language: str | None) -> str:
    code = (language or "en").lower().replace("_", "-").split("-")[0]
    return code if code in LABELS["overview"] else "en"


def section_label(key: str, language: str | None) -> str:
    table = LABELS[key]
    return table.get(lang_code(language), table["en"])


def _pattern(terms: tuple[str, ...]) -> str:
    parts = [re.escape(t) for t in sorted(set(terms), key=len, reverse=True)]
    return "|".join(parts)


def detect_pattern(key: str) -> str:
    return _pattern(DETECT[key])


OVERVIEW_RE = re.compile(detect_pattern("overview"), re.IGNORECASE)
HOOK_RE = re.compile(detect_pattern("hook"), re.IGNORECASE)
NPC_RE = re.compile(detect_pattern("npc"), re.IGNORECASE)
SESSION_WORD_RE = re.compile(detect_pattern("session"), re.IGNORECASE)
INSPIRED_RE = re.compile(detect_pattern("inspired"), re.IGNORECASE)
ENEMIES_RE = re.compile(detect_pattern("enemies"), re.IGNORECASE)
PUZZLES_RE = re.compile(detect_pattern("puzzles"), re.IGNORECASE)
ENDINGS_RE = re.compile(detect_pattern("endings"), re.IGNORECASE)
MAPS_RE = re.compile(detect_pattern("maps"), re.IGNORECASE)
REWARDS_RE = re.compile(detect_pattern("rewards"), re.IGNORECASE)

SESSION_NUMBER_RE = re.compile(
    rf"(?:{detect_pattern('session')})\s*#?\s*(\d+)"
    r"|第\s*(\d+)\s*(?:セッション|話|回|节|節|幕)?"
    r"|제\s*(\d+)\s*세션?",
    re.IGNORECASE,
)

KNOWN_SECTION_RE = re.compile(
    rf"^(?:{detect_pattern('overview')}|{detect_pattern('hook')}|"
    rf"{detect_pattern('session')}|{detect_pattern('npc')}|"
    rf"{detect_pattern('enemies')}|{detect_pattern('puzzles')}|"
    rf"{detect_pattern('endings')}|{detect_pattern('maps')}|"
    rf"{detect_pattern('rewards')}|{detect_pattern('inspired')}|"
    r"character archetypes|arquétipos)",
    re.IGNORECASE,
)


def count_sessions(text: str) -> int:
    nums: list[int] = []
    for match in SESSION_NUMBER_RE.finditer(text or ""):
        for group in match.groups():
            if group:
                nums.append(int(group))
                break
    if nums:
        return max(nums)
    return len(
        re.findall(
            rf"^#+\s*(?:{detect_pattern('session')})\b",
            text or "",
            re.IGNORECASE | re.MULTILINE,
        )
    )


def markdown_schema(language: str = "en") -> str:
    ov = section_label("overview", language)
    hook = section_label("hook", language)
    sess = section_label("session", language)
    npcs = section_label("npcs", language)
    enemies = section_label("enemies", language)
    puzzles = section_label("puzzles", language)
    endings = section_label("endings", language)
    maps = section_label("maps", language)
    objectives = section_label("objectives", language)
    return (
        "REQUIRED MARKDOWN SCHEMA (the UI breaks if you deviate):\n"
        f"# {{Campaign Title}}\n"
        f"## {ov}\n"
        f"## {hook}\n"
        f"## {sess} 1: {{Title}}\n"
        f"**{objectives}:**\n- ...\n"
        f"### Scene / Encounter headings\n"
        f"## {sess} 2: {{Title}}\n"
        f"## {npcs}\n"
        f"### {{NPC Name}}\n"
        f"**Role:** one line\n"
        f"## {enemies}\n"
        f"## {puzzles}\n"
        f"## {endings}\n"
        f"## {maps}\n"
        "Rules: exactly one H1 (the title); H2 only for those sections; "
        "H3 for scenes, encounters, NPC names, endings, and maps; "
        "never wrap heading text in **bold**; never wrap the document in a code fence; "
        "markdown tables for stat blocks; blockquotes for spoken dialogue."
    )
