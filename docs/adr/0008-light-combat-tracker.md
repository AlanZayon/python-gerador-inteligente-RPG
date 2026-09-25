# Light combat tracker; book owns procedures

Combat at the table is a **light tracker** in Campaign State (combatants, initiative, turn pointer, optional HP/resources), not a multi-system combat engine. Attack, damage, initiative, and death procedures come from the uploaded BookIndex via `lookup_rules` and LLM interpretation. The server owns dice (`DiceRng` / Roll Call) and persists tracker mutations through GM Tools (`begin_combat`, `apply_harm`, `next_turn`, …).

A full rules DSL or hard-coded hit-vs-AC pipeline was rejected so any uploaded system can drive fights without compiling system logic into Python. Voice Direction still must not mutate combat or Campaign State.
