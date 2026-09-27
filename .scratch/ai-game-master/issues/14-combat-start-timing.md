# 14: Combat start timing (initiative first)

**What to build:** The GM must open a Combat Encounter at the right moment. When a Player declares violence against a creature and no encounter is active, the flight goes `lookup_rules` → `begin_combat` → initiative Roll Calls → attacks on turn. The server rejects attack/damage Roll Calls outside an encounter so the GM cannot resolve a whole fight (capture, death) from one cinematic roll.

**Blocked by:** 13 — Light Combat Tracker

**Status:** resolved

- [x] `looks_like_hostile_violence` / `looks_like_attack_or_damage_roll` / `looks_like_initiative_roll` heuristics (EN/PT) in `services/play/gm/combat.py`
- [x] `request_roll` returns `combat_required` (no encounter) or `initiative_required` (acting Combatant has no initiative) for attack/damage checks
- [x] Live prompt: START / DO NOT START / ORDER rules; roll resolution may not end a fight while combat is null
- [x] `combat_policy` injected into the GM input on hostile turns and out-of-combat attack resolutions
- [x] Tool loop runs `begin_combat` alongside `lookup_rules` and feeds combat gate errors back to the model for another round
- [x] Tests for heuristics, gate, policy injection, and recovery

## Answer

Initiative-first combat: hostile declarations get a `combat_policy` advisory, and attack/damage Roll Calls are server-gated on an active encounter with initiative set (ADR 0008).
