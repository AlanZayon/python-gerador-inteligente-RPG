"""Player-agency helpers — GM must not invent unrequested PC voluntary acts."""

from __future__ import annotations

import re


_VOLUNTARY = re.compile(
    r"\b(draws?|charges?|attacks?|casts?|sneaks?|opens?|closes?|says?|shouts?|"
    r"runs?|flees?|strikes?|fires?|shoots?|grabs?|takes?|decides?|chooses?)\b",
    re.I,
)


def scrub_unsolicited_pc_actions(
    narration: str,
    *,
    actor_name: str | None,
    other_names: list[str],
    player_action: str,
) -> str:
    """Drop sentences that attribute voluntary acts to other PCs not in the action text."""
    text = (narration or "").strip()
    if not text or not other_names:
        return text

    action_l = (player_action or "").lower()
    actor_l = (actor_name or "").lower()
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        s = sentence.strip()
        if not s:
            continue
        lower = s.lower()
        drop = False
        for name in other_names:
            n = (name or "").strip()
            if not n:
                continue
            nl = n.lower()
            if nl in action_l:
                continue
            if nl == actor_l:
                continue
            if nl in lower and _VOLUNTARY.search(lower):
                drop = True
                break
        if not drop:
            kept.append(s)
    if kept:
        return " ".join(kept)
    return "The table waits for the others to declare their own actions."
