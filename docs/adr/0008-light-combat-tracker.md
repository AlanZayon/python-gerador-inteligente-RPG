# Light combat tracker; book owns procedures

Combat at the table is a **light tracker** in Campaign State (combatants, initiative, turn pointer, optional HP/resources), not a multi-system combat engine. Attack, damage, initiative, and death procedures come from the uploaded BookIndex via `lookup_rules` and LLM interpretation. The server owns dice (`DiceRng` / Roll Call) and persists tracker mutations through GM Tools (`begin_combat`, `apply_harm`, `next_turn`, …).

A full rules DSL or hard-coded hit-vs-AC pipeline was rejected so any uploaded system can drive fights without compiling system logic into Python. Voice Direction still must not mutate combat or Campaign State.

Combat is **initiative first**: once violence against a creature is declared, the GM must `lookup_rules` → `begin_combat` → roll initiative → attack on turn. The server enforces this by rejecting attack/damage Roll Calls with `combat_required` when no Combat Encounter is active, and with `initiative_required` while the acting Combatant has no initiative. Recognising an attack is a keyword heuristic on the Roll Call's skill/reason (EN/PT), not a rules model; a one-shot cinematic attack outside the tracker was rejected because it let the GM resolve whole fights (capture, death) from a single roll.
