# 05: GameSession lobby (invite → claim → start)

**What to build:** Host creates a GameSession for a Campaign and gets an invite code. 2–4 Clerk users join, each claims one unique Character, mark ready, and the host starts. At most one active GameSession per Campaign; Start is blocked until claims and party size rules pass. Host can end the session.

**Blocked by:** 04 — Create Campaign from Job

**Status:** resolved

- [x] Host can create a GameSession in LOBBY with an invite code
- [x] Players join via invite while authenticated; duplicates and capacity rules are enforced
- [x] Character claim is unique; Start requires 2–4 Players each with a claimed Character
- [x] Only one non-ended/active GameSession per Campaign at a time
- [x] Host can end a GameSession; lobby UI (or thin client) shows invite, roster, ready, start
- [x] Play Application tests cover join/claim/start/end and rejection cases
