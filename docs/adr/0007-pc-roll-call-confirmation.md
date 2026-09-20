# Player Characters confirm rolls; the server still owns the RNG

PC checks are a two-beat table ritual: the Game Master Runtime consults the BookIndex, issues a Roll Call, and waits. The targeted Player authorizes the roll in the UI; `DiceRng` on the server produces the total. Immediate `roll_dice` remains only for hidden GM/NPC rolls.

A Roll Call may carry alternative checks (Perception or Stealth). The Player chooses which one to confirm; the server still owns the RNG.

Confirming in the client (instead of rolling inside the first GM flight) preserves player agency at the cost of a second serialized flight and a blocked action queue while a Roll Call is pending. Client-side RNG was rejected so dice stay auditable and server-authoritative.
